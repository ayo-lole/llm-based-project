from __future__ import annotations

import os
import subprocess
from pathlib import Path

from orchestrator.config import HARNESS


def gradle_cmd(harness_dir: Path | None = None) -> list[str]:
    cwd = harness_dir or HARNESS
    win = cwd / "gradlew.bat"
    unix = cwd / "gradlew"
    if win.exists():
        return [str(win)]
    if unix.exists():
        return [str(unix)]
    raise RuntimeError(f"Gradle wrapper missing in {cwd}")


def run_gradle(task: str, harness_dir: Path | None = None, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    cwd = harness_dir or HARNESS
    extra = os.getenv("THESIS_GRADLE_ARGS", "--daemon --build-cache").split()
    cmd = gradle_cmd(cwd) + [task, "--console=plain", *extra]
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=os.environ.copy(),
    )
