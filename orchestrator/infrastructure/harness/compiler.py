from __future__ import annotations

from pathlib import Path

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


class GradleCompiler:
    def assemble(self, harness_dir: Path | None = None) -> CompileResult:
        proc = run_gradle(":app:assembleDebug", harness_dir=harness_dir)
        combined = proc.stdout + "\n" + proc.stderr
        built = proc.returncode == 0 and "BUILD SUCCESSFUL" in combined
        kotlin_failed = "compileDebugKotlin FAILED" in combined
        kotlin_ok = "compileDebugKotlin" in combined and not kotlin_failed
        errors = _extract_errors(combined) if not built else []
        return CompileResult(
            ok=built,
            compiled=built or kotlin_ok,
            built=built,
            stdout=proc.stdout,
            stderr=proc.stderr,
            errors=errors,
        )
