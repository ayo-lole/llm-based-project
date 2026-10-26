from __future__ import annotations

import json
from pathlib import Path

from orchestrator.config import DATASET
from orchestrator.domain.models import Screen


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rebuild_index() -> dict:
    root = DATASET / "screens"
    ids = sorted(p.name for p in root.iterdir() if p.is_dir()) if root.exists() else []
    stratification = {"simple": 0, "medium": 0, "complex": 0}
    for sid in ids:
        meta_path = root / sid / "meta.json"
        if meta_path.exists():
            c = str(_read_json(meta_path).get("complexity", "")).lower()
            if c in stratification:
                stratification[c] += 1
    payload = {"count": len(ids), "screens": ids, "stratification": stratification}
    DATASET.mkdir(parents=True, exist_ok=True)
    (DATASET / "index.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


class FileScreenRepository:
    def __init__(self, root: Path | None = None):
        self.root = root or (DATASET / "screens")

    def ids(self) -> list[str]:
        index = DATASET / "index.json"
        if index.exists():
            return list(_read_json(index).get("screens", []))
        if not self.root.exists():
            return []
        return sorted(p.name for p in self.root.iterdir() if p.is_dir())

    def get(self, screen_id: str) -> Screen:
        folder = self.root / screen_id
        meta = _read_json(folder / "meta.json") if (folder / "meta.json").exists() else {}
        layout_name = meta.get("layout", "layout.xml")
        xml = (folder / layout_name).read_text(encoding="utf-8-sig")
        parts: list[str] = []
        for name in ("Activity.kt", "Fragment.kt", "ViewModel.kt"):
            p = folder / name
            if p.exists():
                parts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')}")
        return Screen(
            id=screen_id,
            xml=xml,
            context="\n".join(parts),
            complexity=str(meta.get("complexity", "")),
            repo=str(meta.get("repo", "")),
            license_spdx=str(meta.get("license") or meta.get("license_spdx") or ""),
            commit_sha=str(meta.get("commit_sha") or meta.get("sha") or ""),
            source_url=str(meta.get("url") or meta.get("source_url") or ""),
        )
