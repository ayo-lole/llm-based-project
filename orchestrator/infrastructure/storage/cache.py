from __future__ import annotations

from pathlib import Path

from orchestrator.config import CACHE


def llm_cache_dir() -> Path:
    path = CACHE / "llm"
    path.mkdir(parents=True, exist_ok=True)
    return path
