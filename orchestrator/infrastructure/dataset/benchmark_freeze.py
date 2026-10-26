from __future__ import annotations

import json
import random
import xml.etree.ElementTree as ET
from pathlib import Path

from orchestrator.config import DATASET

QUOTA = {"simple": 52, "medium": 71, "complex": 27}
SEED = 244


def _has_viewmodel_evidence(folder: Path, xml: str) -> bool:
    if (folder / "ViewModel.kt").exists():
        return True
    if "ViewModel" in xml and "<variable" in xml:
        return True
    for name in ("Activity.kt", "Fragment.kt"):
        p = folder / name
        if p.exists() and "ViewModel" in p.read_text(encoding="utf-8", errors="replace"):
            return True
    return False


def freeze_benchmark(
    *,
    seed: int = SEED,
    quota: dict[str, int] | None = None,
    overwrite: bool = False,
    dataset_root: Path | None = None,
) -> dict:
    quota = quota or QUOTA
    root = dataset_root or DATASET
    out = root / "benchmark_150.json"
    if out.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing freeze at {out}")
    screens_root = root / "screens"
    funnel = {"total": 0, "seed_or_demo": 0, "unparseable": 0, "no_viewmodel": 0, "eligible": 0}
    by_tier: dict[str, list[str]] = {k: [] for k in quota}
    for folder in sorted(screens_root.iterdir()) if screens_root.exists() else []:
        if not folder.is_dir():
            continue
        funnel["total"] += 1
        sid = folder.name
        if sid.startswith("seed_") or sid == "0001_login":
            funnel["seed_or_demo"] += 1
            continue
        meta_path = folder / "meta.json"
        if not meta_path.exists():
            funnel["unparseable"] += 1
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        layout = folder / meta.get("layout", "layout.xml")
        if not layout.exists():
            funnel["unparseable"] += 1
            continue
        xml = layout.read_text(encoding="utf-8-sig")
        try:
            ET.fromstring(xml)
        except ET.ParseError:
            funnel["unparseable"] += 1
            continue
        if not _has_viewmodel_evidence(folder, xml):
            funnel["no_viewmodel"] += 1
            continue
        tier = str(meta.get("complexity", "")).lower()
        if tier not in by_tier:
            continue
        funnel["eligible"] += 1
        by_tier[tier].append(sid)
    rng = random.Random(seed)
    chosen: list[str] = []
    for tier, n in quota.items():
        pool = sorted(by_tier[tier])
        if len(pool) < n:
            raise RuntimeError(f"Not enough {tier} eligible screens: {len(pool)} < {n}")
        chosen.extend(rng.sample(pool, n))
    payload = {
        "seed": seed,
        "quota": quota,
        "screens": chosen,
        "count": len(chosen),
        "funnel": funnel,
        "available": {k: len(v) for k, v in by_tier.items()},
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def load_benchmark_ids() -> list[str]:
    path = DATASET / "benchmark_150.json"
    if not path.exists():
        raise FileNotFoundError("benchmark_150.json is not frozen yet")
    return list(json.loads(path.read_text(encoding="utf-8"))["screens"])
