from __future__ import annotations

import csv
import json
import random
from pathlib import Path

from orchestrator.config import RESULTS
from orchestrator.evaluation.collect import collect_rows


def prepare(n: int = 20, seed: int = 244) -> Path:
    rows = [
        r
        for r in collect_rows()
        if r["scenario"] in ("s3", "s4")
        and not r["preset"]
        and r.get("built_ok")
    ]
    rng = random.Random(seed)
    rng.shuffle(rows)
    chosen = rows[:n]
    out = RESULTS / "labeling"
    out.mkdir(parents=True, exist_ok=True)
    key = [{"screen_id": r["screen_id"], "model": r["model"], "scenario": r["scenario"], "source": r["source"], "detector_mvvm": r["mvvm_compliant"]} for r in chosen]
    (out / "hidden_key.json").write_text(json.dumps(key, indent=2), encoding="utf-8")
    sheet = []
    for round_id in (1, 2):
        order = chosen[:]
        rng.shuffle(order)
        for i, r in enumerate(order, 1):
            sheet.append({"round": round_id, "item": i, "screen_id": r["screen_id"], "model": r["model"], "scenario": r["scenario"], "label": ""})
    path = out / "worksheet.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["round", "item", "screen_id", "model", "scenario", "label"])
        w.writeheader()
        w.writerows(sheet)
    return path


def _kappa(a: list[int], b: list[int]) -> float:
    n = len(a)
    if n == 0:
        return 0.0
    po = sum(x == y for x, y in zip(a, b)) / n
    p1 = sum(a) / n
    q1 = 1 - p1
    p2 = sum(b) / n
    q2 = 1 - p2
    pe = p1 * p2 + q1 * q2
    return 0.0 if pe == 1 else (po - pe) / (1 - pe)


def score(worksheet: Path | None = None) -> dict:
    out = RESULTS / "labeling"
    ws = worksheet or (out / "worksheet.csv")
    key = { (r["screen_id"], r["model"], r["scenario"]): r for r in json.loads((out / "hidden_key.json").read_text(encoding="utf-8")) }
    by_round: dict[int, dict] = {1: {}, 2: {}}
    with ws.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            lab = row["label"].strip().lower() in ("1", "true", "yes", "compliant")
            by_round[int(row["round"])][(row["screen_id"], row["model"], row["scenario"])] = lab
    keys = sorted(key)
    r1 = [int(by_round[1].get(k, False)) for k in keys]
    r2 = [int(by_round[2].get(k, False)) for k in keys]
    det = [int(key[k]["detector_mvvm"]) for k in keys]
    # use round 2 as final manual
    tp = sum(d == 1 and m == 1 for d, m in zip(det, r2))
    tn = sum(d == 0 and m == 0 for d, m in zip(det, r2))
    fp = sum(d == 1 and m == 0 for d, m in zip(det, r2))
    fn = sum(d == 0 and m == 1 for d, m in zip(det, r2))
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    acc_n = tp + tn
    n = len(keys)
    from orchestrator.evaluation.stats import wilson_interval

    acc, lo, hi = wilson_interval(acc_n, n)
    report = {
        "intra_rater_kappa": _kappa(r1, r2),
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "precision": prec, "recall": rec, "f1": f1,
        "accuracy": acc, "accuracy_ci_lo": lo, "accuracy_ci_hi": hi, "n": n,
    }
    (out / "score.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
