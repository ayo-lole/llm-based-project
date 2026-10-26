from __future__ import annotations

import json
import os
import re
from pathlib import Path

from orchestrator.config import RESULTS
from orchestrator.domain.models import MigrationResult


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)


class JsonResultStore:
    def __init__(self, root: Path | None = None):
        self.root = root or RESULTS

    def path_for(self, model: str, sub: str, screen_id: str, run_index: int) -> Path:
        folder = self.root / _safe(model) / _safe(sub)
        return folder / f"{_safe(screen_id)}_run{run_index}.json"

    def exists(self, model: str, sub: str, screen_id: str, run_index: int) -> bool:
        return self.path_for(model, sub, screen_id, run_index).exists()

    def save(self, result: MigrationResult) -> Path:
        sub = result.ablation.get("preset") or result.scenario
        path = self.path_for(result.model, sub, result.screen_id, result.run_index)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
        os.replace(tmp, path)
        return path
