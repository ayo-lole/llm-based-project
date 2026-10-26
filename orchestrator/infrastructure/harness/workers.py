from __future__ import annotations

import json
import shutil
from pathlib import Path

from orchestrator.config import HARNESS, ROOT
from orchestrator.infrastructure.harness.runtime_adb import list_emulator_serials


def worker_dir(index: int) -> Path:
    return ROOT / "apps" / f"harness_w{index}"


def make_workers(n: int, serials: list[str] | None = None) -> list[Path]:
    paths: list[Path] = []
    ignore = shutil.ignore_patterns("build", ".gradle", "*.apk")
    bound = serials if serials is not None else list_emulator_serials()
    for i in range(1, n + 1):
        dest = worker_dir(i)
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(HARNESS, dest, ignore=ignore)
        serial = bound[i - 1] if i - 1 < len(bound) else None
        (dest / "worker.json").write_text(
            json.dumps({"worker": i, "serial": serial}, indent=2),
            encoding="utf-8",
        )
        paths.append(dest)
    return paths
