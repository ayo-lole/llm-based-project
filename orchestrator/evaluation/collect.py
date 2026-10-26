from __future__ import annotations

import json
from pathlib import Path

from orchestrator.config import RESULTS
from orchestrator.domain.rules import check_arch_rules
from orchestrator.domain.scoring import arch_score, mvvm_compliant
from orchestrator.infrastructure.dataset.benchmark_freeze import load_benchmark_ids


def collect_rows(results_dir: Path | None = None) -> list[dict]:
    root = results_dir or RESULTS
    try:
        bench = set(load_benchmark_ids())
    except FileNotFoundError:
        bench = None
    rows: list[dict] = []
    if not root.exists():
        return rows
    for path in root.rglob("*.json"):
        if "experiment_manifests" in path.parts or path.name.endswith(".tmp"):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        sid = data.get("screen_id")
        if not sid or not data.get("history"):
            continue
        if bench is not None and sid not in bench:
            continue
        last = data["history"][-1]
        code = data.get("code") or ""
        violations = check_arch_rules(code) if code else last.get("arch_violations", [])
        compile_d = last.get("compile", {})
        sa = last.get("static_analysis", {})
        ablation = (data.get("ablation") or {}).get("preset", "")
        rows.append(
            {
                "screen_id": sid,
                "model": data.get("model"),
                "scenario": data.get("scenario"),
                "preset": ablation,
                "run_index": data.get("run_index", 1),
                "converged": data.get("converged"),
                "iterations": data.get("iterations"),
                "compiled_ok": compile_d.get("compiled", False),
                "built_ok": compile_d.get("built", False),
                "runtime_ok": compile_d.get("runtime_ok", False),
                "runtime_method": compile_d.get("runtime_method", ""),
                "arch_violations": violations,
                "arch_score": arch_score(violations),
                "mvvm_compliant": mvvm_compliant(violations),
                "lint_count": sa.get("lint_count", 0),
                "detekt_count": sa.get("detekt_count", 0),
                "ktlint_count": sa.get("ktlint_count", 0),
                "generation_settings": data.get("generation_settings", {}),
                "source": str(path),
                "error_types": last.get("error_types", {}),
                "compile_s": last.get("compile_s", 0),
                "static_s": last.get("static_s", 0),
                "runtime_s": last.get("runtime_s", 0),
            }
        )
    return rows
