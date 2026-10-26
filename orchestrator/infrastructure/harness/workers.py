from __future__ import annotations

import shutil
from pathlib import Path

from orchestrator.config import HARNESS, ROOT


def worker_dir(index: int) -> Path:
    return ROOT / "apps" / f"harness_w{index}"


def make_workers(n: int) -> list[Path]:
    paths: list[Path] = []
    ignore = shutil.ignore_patterns("build", ".gradle", "*.apk")
    for i in range(1, n + 1):
        dest = worker_dir(i)
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(HARNESS, dest, ignore=ignore)
        paths.append(dest)
    return paths
