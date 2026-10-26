from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from orchestrator.application.baseline_b0 import transpile
from orchestrator.application.migrate import K, migrate_screen
from orchestrator.application.ports import (
    Compiler,
    HarnessWriter,
    ResultStore,
    RuntimeChecker,
    ScreenRepository,
    StaticAnalyzer,
)
from orchestrator.domain.models import ABLATION_PRESETS, MODELS, SCENARIOS, IterationRecord, MigrationResult
from orchestrator.domain.rules import check_arch_rules
from orchestrator.domain.scoring import arch_score, classify_errors

Job = dict


def iter_jobs(
    models: tuple[str, ...] = MODELS,
    scenarios: tuple[str, ...] = SCENARIOS,
    screens: list[str] | None = None,
    n_runs: int = 3,
    presets: list[str] | None = None,
) -> list[Job]:
    screens = screens or []
    preset_list = presets if presets is not None else [None]
    jobs: list[Job] = []
    for model in models:
        for scenario in scenarios:
            for preset in preset_list:
                for run_index in range(1, n_runs + 1):
                    for sid in screens:
                        jobs.append(
                            {
                                "screen_id": sid,
                                "model": model,
                                "scenario": scenario,
                                "run_index": run_index,
                                "preset": preset,
                            }
                        )
    return jobs


def pending_jobs(jobs: list[Job], store: ResultStore) -> list[Job]:
    out = []
    for job in jobs:
        sub = job["preset"] or job["scenario"]
        if not store.exists(job["model"], sub, job["screen_id"], job["run_index"]):
            out.append(job)
    return out


def execute_job(job: Job, migrate_fn: Callable[[Job], MigrationResult]) -> MigrationResult:
    return migrate_fn(job)


def migrate_from_ports(
    job: Job,
    *,
    client,
    templates: dict[str, str],
    screens: ScreenRepository,
    writer: HarnessWriter,
    compiler: Compiler,
    analyzer: StaticAnalyzer,
    runtime: RuntimeChecker,
    store: ResultStore,
    harness_dir: Path | None,
    device_serial: str | None,
    skip_android_lint: bool,
    generation_settings: dict,
) -> MigrationResult:
    _ = skip_android_lint
    flags = ABLATION_PRESETS.get(job.get("preset") or "", {})
    scenario = job["scenario"]
    return migrate_screen(
        job["screen_id"],
        client,
        templates,
        screens,
        writer,
        compiler,
        analyzer,
        runtime,
        store,
        scenario=scenario,
        max_iter=K if scenario == "s4" else 1,
        skip_android_lint=False,
        ablation_label=job.get("preset"),
        run_index=job["run_index"],
        harness_dir=harness_dir,
        device_serial=device_serial,
        generation_settings=generation_settings,
        **flags,
    )


def run_b0_screens(
    screen_ids: list[str],
    screens: ScreenRepository,
    writer: HarnessWriter,
    compiler: Compiler,
    analyzer: StaticAnalyzer,
    runtime: RuntimeChecker,
    store: ResultStore,
    *,
    harness_dir: Path | None,
    skip_android_lint: bool,
    generation_settings: dict,
) -> int:
    _ = skip_android_lint
    n = 0
    for sid in screen_ids:
        if store.exists("b0", "b0", sid, 1):
            continue
        screen = screens.get(sid)
        code, unmapped = transpile(screen.xml)
        _path, n_stubs, entry = writer.write(code, harness_dir=harness_dir, screen_id=sid)
        if entry == "missing":
            from orchestrator.domain.models import CompileResult

            compile_res = CompileResult(False, False, False, errors=["No harness entry"])
        else:
            compile_res = compiler.assemble(harness_dir)
        sa = analyzer.analyze(harness_dir, skip_lint=False)
        rt = runtime.check(code, built=compile_res.built, harness_dir=harness_dir)
        compile_d = compile_res.to_dict()
        compile_d.update(rt.to_dict())
        compile_d["harness_entry"] = entry
        compile_d["unmapped"] = unmapped
        violations = check_arch_rules(code)
        history = [
            IterationRecord(
                iteration=1,
                compile=compile_d,
                static_analysis=sa.to_dict(),
                arch_violations=violations,
                arch_score=arch_score(violations),
                problems=compile_res.errors + violations,
                error_types=classify_errors(compile_res.errors + violations, code, screen.xml),
                resource_stubs=n_stubs,
                harness_entry=entry,
            )
        ]
        store.save(
            MigrationResult(
                screen_id=sid,
                model="b0",
                scenario="b0",
                code=code,
                converged=compile_res.built,
                iterations=1,
                xml=screen.xml,
                history=history,
                codes_per_iteration=[code],
                generation_settings=generation_settings,
            )
        )
        n += 1
    return n


def run_pool(payloads: list[dict], worker, workers: int) -> None:
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(worker, p) for p in payloads]
        for fut in as_completed(futs):
            fut.result()
