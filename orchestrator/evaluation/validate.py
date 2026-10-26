from __future__ import annotations

import csv
from collections import Counter
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
    screens = load_benchmark_ids()
    missing: list[dict] = []
    matrix = [r for r in rows if r["scenario"] in SCENARIOS and not r["preset"]]
    ablation = [r for r in rows if r["preset"]]
    b0 = [r for r in rows if r["scenario"] == "b0"]

    def keys(items, models, scenarios, presets=None):
        have = {(r["model"], r["scenario"], r["preset"], r["screen_id"], r["run_index"]) for r in items}
        want = []
        for model in models:
            for sc in scenarios:
                for preset in (presets or [""]):
                    for sid in screens:
                        for run in (1, 2, 3) if sc != "b0" else (1,):
                            tup = (model, sc, preset, sid, run)
                            if tup not in have and (model, sc if sc != "b0" else "b0", preset, sid, run) not in have:
                                want.append(tup)
        return have, want

    _, miss_m = keys(matrix, MODELS, SCENARIOS)
    _, miss_a = keys(ablation, MODELS, ("s4",), ["no_feedback_loop", "no_arch_constraint", "no_static_analysis"])
    have_b0 = {(r["screen_id"],) for r in b0}
    miss_b = [sid for sid in screens if (sid,) not in have_b0]
    for tup in miss_m:
        missing.append({"kind": "matrix", "model": tup[0], "scenario": tup[1], "screen_id": tup[3], "run_index": tup[4]})
    for tup in miss_a:
        missing.append({"kind": "ablation", "model": tup[0], "preset": tup[2], "screen_id": tup[3], "run_index": tup[4]})
    for sid in miss_b:
        missing.append({"kind": "b0", "screen_id": sid})

    dups = [k for k, n in Counter((r["model"], r["scenario"], r["preset"], r["screen_id"], r["run_index"]) for r in rows).items() if n > 1]
    emulator_n = sum(1 for r in rows if r.get("runtime_method") == "emulator")
    report = {
        "matrix_n": len(matrix),
        "matrix_expected": EXPECTED_MATRIX,
        "ablation_n": len(ablation),
        "ablation_expected": EXPECTED_ABLATION,
        "b0_n": len(b0),
        "b0_expected": EXPECTED_B0,
        "duplicates": len(dups),
        "emulator_share": emulator_n / len(rows) if rows else 0,
        "missing": len(missing),
    }
    out = (results_dir or RESULTS) / "missing_runs.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["kind", "model", "scenario", "preset", "screen_id", "run_index"])
        w.writeheader()
        for row in missing:
            w.writerow({k: row.get(k, "") for k in w.fieldnames})
    return report
