from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from orchestrator.config import HARNESS
from orchestrator.domain.models import StaticAnalysisResult
from orchestrator.infrastructure.harness.gradle import run_gradle


def _parse_detekt(text: str, limit: int = 15) -> list[str]:
    issues: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if (" - " in s or s.startswith("[")) and ".kt" in s:
            issues.append(s)
        if len(issues) >= limit:
            break
    return issues


def _parse_ktlint(text: str, limit: int = 15) -> list[str]:
    issues: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("WARNING:"):
            continue
        if ".kt:" in s or "Format" in s or "Unexpected" in s:
            issues.append(s)
        if len(issues) >= limit:
            break
    return issues


def _parse_lint(text: str, limit: int = 10) -> list[str]:
    issues: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if "lint" in s.lower() and ("Error" in s or "Warning" in s or ".kt" in s):
            issues.append(s)
        if len(issues) >= limit:
            break
    return issues


class GradleStaticAnalyzer:
    def analyze(self, harness_dir: Path | None = None, *, skip_lint: bool = False) -> StaticAnalysisResult:
        detekt_ok, detekt_issues = self._detekt(harness_dir)
        ktlint_ok, ktlint_issues = self._ktlint(harness_dir)
        if skip_lint:
            lint_ok, lint_issues = True, []
        else:
            lint_ok, lint_issues = self._lint(harness_dir)
        return StaticAnalysisResult(
            detekt_ok=detekt_ok,
            ktlint_ok=ktlint_ok,
            lint_ok=lint_ok,
            detekt_issues=detekt_issues,
            ktlint_issues=ktlint_issues,
            lint_issues=lint_issues,
        )

    def _detekt(self, harness_dir: Path | None) -> tuple[bool, list[str]]:
        proc = run_gradle(":app:detekt", harness_dir=harness_dir, timeout=300)
        combined = proc.stdout + proc.stderr
        issues = _parse_detekt(combined)
        return proc.returncode == 0 and not issues, issues

    def _ktlint(self, harness_dir: Path | None) -> tuple[bool, list[str]]:
        cwd = harness_dir or HARNESS
        src = cwd / "app" / "src" / "main" / "java"
        ktlint = shutil.which("ktlint")
        if not ktlint:
            return True, []
        proc = subprocess.run(
            [ktlint, str(src)],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        issues = _parse_ktlint(proc.stdout + proc.stderr)
        return proc.returncode == 0, issues

    def _lint(self, harness_dir: Path | None) -> tuple[bool, list[str]]:
        proc = run_gradle(":app:lintDebug", harness_dir=harness_dir, timeout=600)
        combined = proc.stdout + proc.stderr
        issues = _parse_lint(combined)
        return proc.returncode == 0 and not issues, issues
