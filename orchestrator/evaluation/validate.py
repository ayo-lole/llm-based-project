from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from orchestrator.config import RESULTS
from orchestrator.domain.models import MODELS, SCENARIOS
from orchestrator.evaluation.collect import collect_rows
from orchestrator.infrastructure.dataset.benchmark_freeze import load_benchmark_ids

EXPECTED_MATRIX = 150 * 4 * 3 * 3
EXPECTED_ABLATION = 150 * 3 * 3 * 3
EXPECTED_B0 = 150


def validate(results_dir: Path | None = None) -> dict:
    rows = collect_rows(results_dir)
    checks: list[dict] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "ok": ok, "detail": detail})

    try:
        screens = load_benchmark_ids()
    except FileNotFoundError:
        screens = []
        add("benchmark_present", False, "benchmark_150.json missing")

    matrix = [r for r in rows if r["scenario"] in SCENARIOS and not r["preset"]]
    ablation = [r for r in rows if r["preset"]]
    b0 = [r for r in rows if r["scenario"] == "b0"]
    add("matrix_n", len(matrix) == EXPECTED_MATRIX, f"{len(matrix)} != {EXPECTED_MATRIX}")
    add("ablation_n", len(ablation) == EXPECTED_ABLATION, f"{len(ablation)} != {EXPECTED_ABLATION}")
    add("b0_n", len(b0) == EXPECTED_B0, f"{len(b0)} != {EXPECTED_B0}")

    mocks = [r for r in rows if r.get("is_mock")]
    add("no_is_mock", not mocks, f"{len(mocks)} mock records")
    skipped = [r for r in rows if r.get("runtime_method") in {"skipped", "structural"}]
    add("no_skipped_harness", not skipped, f"{len(skipped)} skipped/structural")
    mismatch = [r for r in rows if r.get("model_returned") and r.get("model_returned") != r.get("model_id")]
    add("model_returned_matches", not mismatch, f"{len(mismatch)} model_returned mismatches")
    length = [r for r in rows if r.get("finish_reason") == "length"]
    add("no_finish_reason_length", not length, f"{len(length)} truncated outputs")
    non_emu = [r for r in rows if r.get("runtime_method") != "emulator"]
    add("emulator_runtime", not non_emu, f"{len(non_emu)} non-emulator runtime verdicts")

    by_group: dict[tuple, dict[int, str]] = defaultdict(dict)
    for r in rows:
        if r["scenario"] == "b0":
            continue
        key = (r["model"], r["scenario"], r["preset"], r["screen_id"])
        by_group[key][int(r["run_index"])] = r.get("cache_key") or ""
    replays = 0
    for key, runs in by_group.items():
        if 1 in runs and 2 in runs and runs[2] and runs[2] == runs[1]:
            replays += 1
        if 1 in runs and 3 in runs and runs[3] and runs[3] == runs[1]:
            replays += 1
    add("runs_not_cache_replays", replays == 0, f"{replays} cache-replay collisions")

    missing: list[dict] = []
    have = {(r["model"], r["scenario"], r["preset"], r["screen_id"], r["run_index"]) for r in rows}
    for model in MODELS:
        for sc in SCENARIOS:
            for sid in screens:
                for run in (1, 2, 3):
                    if (model, sc, "", sid, run) not in have:
                        missing.append({"kind": "matrix", "model": model, "scenario": sc, "screen_id": sid, "run_index": run})
        for preset in ("no_feedback_loop", "no_arch_constraint", "no_static_analysis"):
            for sid in screens:
                for run in (1, 2, 3):
                    if (model, "s4", preset, sid, run) not in have:
                        missing.append({"kind": "ablation", "model": model, "preset": preset, "screen_id": sid, "run_index": run})
    for sid in screens:
        if ("b0", "b0", "", sid, 1) not in have:
            missing.append({"kind": "b0", "screen_id": sid})
    add("coverage", not missing, f"{len(missing)} missing cells")

    report = {
        "ok": all(c["ok"] for c in checks),
        "checks": checks,
        "matrix_n": len(matrix),
        "matrix_expected": EXPECTED_MATRIX,
        "ablation_n": len(ablation),
        "ablation_expected": EXPECTED_ABLATION,
        "b0_n": len(b0),
        "b0_expected": EXPECTED_B0,
        "missing": len(missing),
    }
    out = (results_dir or RESULTS) / "missing_runs.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["kind", "model", "scenario", "preset", "screen_id", "run_index"])
        w.writeheader()
        for row in missing:
            w.writerow({k: row.get(k, "") for k in w.fieldnames})
    check_path = (results_dir or RESULTS) / "validate_report.csv"
    with check_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["check", "ok", "detail"])
        w.writeheader()
        w.writerows(checks)
    return report
