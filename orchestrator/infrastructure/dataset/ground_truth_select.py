from __future__ import annotations

import json
import random
from pathlib import Path

from orchestrator.config import DATASET, GROUND_TRUTH

QUOTA = {"simple": 12, "medium": 16, "complex": 7}
SEED = 244


def select_ground_truth(
    benchmark: Path | None = None,
    *,
    seed: int = SEED,
    dataset_root: Path | None = None,
    ground_truth_root: Path | None = None,
) -> dict:
    data_root = dataset_root or DATASET
    gt_root = ground_truth_root or GROUND_TRUTH
    bench = benchmark or (data_root / "benchmark_150.json")
    ids = json.loads(bench.read_text(encoding="utf-8"))["screens"]
    by_tier: dict[str, list[str]] = {k: [] for k in QUOTA}
    for sid in ids:
        meta_p = data_root / "screens" / sid / "meta.json"
        if not meta_p.exists():
            continue
        tier = str(json.loads(meta_p.read_text(encoding="utf-8")).get("complexity", "")).lower()
        if tier in by_tier:
            by_tier[tier].append(sid)
    rng = random.Random(seed)
    chosen = []
    for tier, n in QUOTA.items():
        pool = sorted(by_tier[tier])
        if len(pool) < n:
            raise RuntimeError(f"Not enough {tier} screens: {len(pool)} < {n}")
        for sid in rng.sample(pool, n):
            chosen.append(
                {
                    "screen_id": sid,
                    "complexity": tier,
                    "status": "pending_manual",
                    "reference": f"manual/{sid}.kt",
                    "minutes_spent": None,
                    "verified": False,
                    "build": False,
                    "runtime": False,
                    "violations": [],
                }
            )
    gt_root.mkdir(parents=True, exist_ok=True)
    (gt_root / "manual").mkdir(parents=True, exist_ok=True)
    out = {"seed": seed, "quota": QUOTA, "benchmark_source": str(bench), "screens": chosen}
    (gt_root / "selection.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out
