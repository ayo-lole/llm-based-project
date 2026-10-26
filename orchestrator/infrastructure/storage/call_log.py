from __future__ import annotations

import json
from pathlib import Path

from orchestrator.config import RESULTS


class JsonlCallLog:
    def __init__(self, path: Path | None = None):
        self.path = path or (RESULTS / "_calls" / "calls.jsonl")

    def append(self, record: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
