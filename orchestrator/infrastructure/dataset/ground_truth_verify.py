from __future__ import annotations

import json

from orchestrator.config import GROUND_TRUTH, HARNESS
from orchestrator.domain.rules import check_arch_rules
from orchestrator.infrastructure.harness.compiler import GradleCompiler
from orchestrator.infrastructure.harness.runtime_adb import AdbRuntimeChecker
from orchestrator.infrastructure.harness.writer import FileHarnessWriter


def verify_ground_truth() -> dict:
    sel_path = GROUND_TRUTH / "selection.json"
    data = json.loads(sel_path.read_text(encoding="utf-8"))
    writer = FileHarnessWriter()
    compiler = GradleCompiler()
    runtime = AdbRuntimeChecker()
    for item in data["screens"]:
        path = GROUND_TRUTH / item["reference"]
        if not path.exists():
            item["verified"] = False
            item["violations"] = ["missing reference file"]
            continue
        code = path.read_text(encoding="utf-8")
        if "TODO generated" in code or "template stub" in code.lower() or "fun MigrationRoot() { TODO" in code:
            item["verified"] = False
            item["violations"] = ["rejected template-generated stub"]
            continue
        writer.write(code, harness_dir=HARNESS, screen_id=item["screen_id"])
        compile_res = compiler.assemble(HARNESS)
        runtime_res = runtime.check(code, built=compile_res.built, harness_dir=HARNESS)
        violations = check_arch_rules(code)
        item["build"] = compile_res.built
        item["runtime"] = runtime_res.ok
        item["violations"] = violations
        item["verified"] = bool(compile_res.built and runtime_res.ok and not violations)
    sel_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data
