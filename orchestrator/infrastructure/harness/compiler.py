from __future__ import annotations

from pathlib import Path

from orchestrator.config import HARNESS
from orchestrator.domain.models import CompileResult
from orchestrator.infrastructure.harness.gradle import run_gradle


def _extract_errors(text: str, limit: int = 8) -> list[str]:
    lines: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("e: ") or (".kt:" in s and "error" in s.lower()):
            lines.append(s)
        if len(lines) >= limit:
            break
    return lines[:limit]


def _apk_exists(harness_dir: Path | None) -> bool:
    apk_dir = (harness_dir or HARNESS) / "app" / "build" / "outputs" / "apk" / "debug"
    return apk_dir.exists() and any(apk_dir.glob("*.apk"))


class GradleCompiler:
    def assemble(self, harness_dir: Path | None = None) -> CompileResult:
        proc = run_gradle(":app:assembleDebug", harness_dir=harness_dir)
        combined = proc.stdout + "\n" + proc.stderr
        compiled = proc.returncode == 0
        built = compiled and _apk_exists(harness_dir)
        errors = _extract_errors(combined) if not compiled else []
        return CompileResult(
            ok=compiled,
            compiled=compiled,
            built=built,
            stdout=proc.stdout,
            stderr=proc.stderr,
            errors=errors,
        )
