from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

from orchestrator.application.run_experiment import (
    iter_jobs,
    migrate_from_ports,
    pending_jobs,
    run_b0_screens,
    run_pool,
)
from orchestrator.config import (
    DEFAULT_N_RUNS,
    DEFAULT_WORKERS,
    GROUND_TRUTH,
    HARNESS,
    MODELS,
    RESULTS,
    SMOKE_RESULTS,
    generation_settings,
    load_templates,
)
from orchestrator.domain.models import ABLATION_PRESETS, SCENARIOS
from orchestrator.infrastructure.dataset.benchmark_freeze import freeze_benchmark, load_benchmark_ids
from orchestrator.infrastructure.dataset.ground_truth_select import select_ground_truth
from orchestrator.infrastructure.dataset.ground_truth_verify import verify_ground_truth
from orchestrator.infrastructure.dataset.screen_repository import FileScreenRepository
from orchestrator.infrastructure.dataset.sources import write_dataset_sources, write_third_party_notices
from orchestrator.infrastructure.harness.compiler import GradleCompiler
from orchestrator.infrastructure.harness.runtime_adb import AdbRuntimeChecker, adb_device_ready
from orchestrator.infrastructure.harness.static_analysis import GradleStaticAnalyzer
from orchestrator.infrastructure.harness.workers import make_workers, worker_dir
from orchestrator.infrastructure.harness.writer import FileHarnessWriter
from orchestrator.infrastructure.llm.openrouter import OpenRouterClient
from orchestrator.infrastructure.storage.call_log import JsonlCallLog
from orchestrator.infrastructure.storage.result_store import JsonResultStore


def _screens(limit: int | None) -> list[str]:
    ids = load_benchmark_ids()
    return ids[:limit] if limit else ids


def _store_for(args: argparse.Namespace) -> JsonResultStore:
    smoke = getattr(args, "limit", None) is not None or getattr(args, "n_runs", DEFAULT_N_RUNS) < 3
    return JsonResultStore(SMOKE_RESULTS if smoke else RESULTS)


def cmd_preflight(_args: argparse.Namespace) -> int:
    problems: list[str] = []
    if not (HARNESS / "gradlew.bat").exists() and not (HARNESS / "gradlew").exists():
        problems.append("harness Gradle wrapper missing")
    if not os.getenv("OPENROUTER_API_KEY"):
        problems.append("OPENROUTER_API_KEY empty")
    settings = generation_settings()
    if settings["max_tokens"] < 8192:
        problems.append("OPENROUTER_MAX_TOKENS must be 8192")
    if settings["prompt_template_version"] != "v1.1-thesis":
        problems.append("PROMPT_TEMPLATE_VERSION must be v1.1-thesis")
    from orchestrator.config import DATASET

    if not (DATASET / "benchmark_150.json").exists():
        problems.append("benchmark_150.json not frozen")
    if not (GROUND_TRUTH / "manual").exists():
        problems.append("ground_truth/manual missing")
    if not shutil.which("adb"):
        problems.append("adb not on PATH")
    elif not adb_device_ready():
        problems.append("no adb device attached")
    if problems:
        print("preflight FAIL")
        for p in problems:
            print(f" - {p}")
        return 1
    print("preflight OK")
    return 0


def cmd_mine(args: argparse.Namespace) -> int:
    import sys

    from orchestrator.infrastructure.dataset.mining import main as mine_main

    sys.argv = ["mine"]
    if args.repos:
        sys.argv += ["--repos", *args.repos]
    mine_main()
    return 0


def cmd_freeze(_args: argparse.Namespace) -> int:
    payload = freeze_benchmark(overwrite=False)
    print(f"froze {payload['count']} screens; funnel={payload['funnel']}; available={payload['available']}")
    return 0


def cmd_select_gt(_args: argparse.Namespace) -> int:
    out = select_ground_truth()
    print(f"selected {len(out['screens'])} screens")
    return 0


def cmd_verify_gt(_args: argparse.Namespace) -> int:
    data = verify_ground_truth()
    ok = sum(1 for s in data["screens"] if s.get("verified"))
    print(f"verified {ok}/{len(data['screens'])}")
    return 0 if ok == len(data["screens"]) else 1


def cmd_dataset_sources(_args: argparse.Namespace) -> int:
    p = write_dataset_sources()
    write_third_party_notices()
    print(p)
    return 0


def cmd_make_workers(args: argparse.Namespace) -> int:
    paths = make_workers(args.n, serials=getattr(args, "serials", None))
    print(f"created {len(paths)} workers")
    return 0


def _pool_worker(payload: dict) -> str:
    serials = payload.get("serials") or []
    worker = payload["worker"]
    serial = serials[worker] if worker < len(serials) else None
    harness = Path(payload["harness"]) if payload.get("harness") else HARNESS
    store = JsonResultStore(Path(payload["results_root"]) if payload.get("results_root") else RESULTS)
    client = OpenRouterClient(payload["model"], call_log=JsonlCallLog())
    migrate_from_ports(
        payload,
        client=client,
        templates=load_templates(),
        screens=FileScreenRepository(),
        writer=FileHarnessWriter(),
        compiler=GradleCompiler(),
        analyzer=GradleStaticAnalyzer(),
        runtime=AdbRuntimeChecker(),
        store=store,
        harness_dir=harness,
        device_serial=serial,
        skip_android_lint=False,
        generation_settings=generation_settings(),
    )
    return payload["screen_id"]


def cmd_run(args: argparse.Namespace) -> int:
    strict = not getattr(args, "no_strict", False)
    if not (HARNESS / "gradlew.bat").exists() and not (HARNESS / "gradlew").exists():
        raise RuntimeError("Harness unavailable")
    if strict and not adb_device_ready():
        raise RuntimeError("Strict mode: an API 34 emulator is required; runtime is not_evaluated without a device")
    kind = args.kind
    screens = _screens(args.limit)
    workers = args.workers
    serials = args.serials or []
    store = _store_for(args)
    if kind == "b0":
        n = run_b0_screens(
            screens,
            FileScreenRepository(),
            FileHarnessWriter(),
            GradleCompiler(),
            GradleStaticAnalyzer(),
            AdbRuntimeChecker(),
            store,
            harness_dir=HARNESS,
            skip_android_lint=False,
            generation_settings=generation_settings(),
        )
        print(f"b0 wrote {n} new records")
        return 0
    models = tuple(args.models) if args.models else MODELS
    unknown = [m for m in models if m not in MODELS]
    if unknown:
        raise RuntimeError(f"Unknown model(s) {unknown}; expected {MODELS}")
    if kind == "ablation":
        jobs = iter_jobs(models, ("s4",), screens, args.n_runs, list(ABLATION_PRESETS))
    else:
        jobs = iter_jobs(models, SCENARIOS, screens, args.n_runs, [None])
    pending = pending_jobs(jobs, store)
    print(f"{len(pending)} pending of {len(jobs)}")
    if workers <= 1:
        for job in pending:
            client = OpenRouterClient(job["model"], call_log=JsonlCallLog())
            migrate_from_ports(
                job,
                client=client,
                templates=load_templates(),
                screens=FileScreenRepository(),
                writer=FileHarnessWriter(),
                compiler=GradleCompiler(),
                analyzer=GradleStaticAnalyzer(),
                runtime=AdbRuntimeChecker(),
                store=store,
                harness_dir=HARNESS,
                device_serial=serials[0] if serials else None,
                skip_android_lint=False,
                generation_settings=generation_settings(),
            )
        return 0
    payloads = []
    for i, job in enumerate(pending):
        w = (i % workers) + 1
        payloads.append(
            {
                **job,
                "worker": w - 1,
                "harness": str(worker_dir(w)),
                "serials": serials,
                "results_root": str(store.root),
            }
        )
    run_pool(payloads, _pool_worker, workers)
    return 0


def cmd_collect(_args: argparse.Namespace) -> int:
    import json

    from orchestrator.evaluation.collect import collect_rows

    rows = collect_rows()
    dest = RESULTS / "collected.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"{len(rows)} rows -> {dest}")
    return 0


def cmd_validate(_args: argparse.Namespace) -> int:
    from orchestrator.evaluation.validate import validate

    report = validate()
    print(report)
    return 0 if report.get("ok") else 1


def cmd_stats(_args: argparse.Namespace) -> int:
    from orchestrator.evaluation.stats import run_stats

    print(run_stats())
    return 0


def cmd_labeling(args: argparse.Namespace) -> int:
    from orchestrator.evaluation.labeling import prepare, score

    if args.action == "prepare":
        print(prepare())
    else:
        print(score())
    return 0


def cmd_code_similarity(_args: argparse.Namespace) -> int:
    from orchestrator.evaluation.code_similarity import run_code_similarity

    print(run_code_similarity())
    return 0


def cmd_visual(_args: argparse.Namespace) -> int:
    from orchestrator.evaluation.visual_fidelity import run_visual_fidelity

    print(run_visual_fidelity())
    return 0


def cmd_figures(_args: argparse.Namespace) -> int:
    from orchestrator.evaluation.figures import run_figures

    print(run_figures())
    return 0


def _add_run_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--n-runs", type=int, default=DEFAULT_N_RUNS)
    parser.add_argument("--models", nargs="*")
    parser.add_argument("--serials", nargs="*")
    parser.add_argument("--no-strict", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m orchestrator",
        epilog="Command-line research pipeline only.",
    )
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("mine").set_defaults(func=cmd_mine)
    sub.add_parser("freeze-benchmark").set_defaults(func=cmd_freeze)
    sub.add_parser("select-ground-truth").set_defaults(func=cmd_select_gt)
    sub.add_parser("verify-ground-truth").set_defaults(func=cmd_verify_gt)
    sub.add_parser("dataset-sources").set_defaults(func=cmd_dataset_sources)
    sub.add_parser("preflight").set_defaults(func=cmd_preflight)
    mw = sub.add_parser("make-workers")
    mw.add_argument("n", type=int, nargs="?", default=DEFAULT_WORKERS)
    mw.add_argument("--serials", nargs="*")
    mw.set_defaults(func=cmd_make_workers)
    run = sub.add_parser("run")
    run.add_argument("kind", choices=["matrix", "ablation", "b0"])
    _add_run_flags(run)
    run.set_defaults(func=cmd_run)
    b0 = sub.add_parser("b0")
    _add_run_flags(b0)
    b0.set_defaults(func=cmd_run, kind="b0")
    sub.add_parser("collect").set_defaults(func=cmd_collect)
    sub.add_parser("validate").set_defaults(func=cmd_validate)
    sub.add_parser("stats").set_defaults(func=cmd_stats)
    lab = sub.add_parser("labeling")
    lab.add_argument("action", choices=["prepare", "score"])
    lab.set_defaults(func=cmd_labeling)
    sub.add_parser("code-similarity").set_defaults(func=cmd_code_similarity)
    sub.add_parser("visual-fidelity").set_defaults(func=cmd_visual)
    sub.add_parser("figures").set_defaults(func=cmd_figures)
    mine = [s for s in sub.choices.values() if s.prog.endswith("mine")][0]
    mine.add_argument("--repos", nargs="*")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
