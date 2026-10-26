from __future__ import annotations

import csv
import json
import random
from datetime import datetime, timezone
from pathlib import Path

from orchestrator.config import RESULTS
from orchestrator.evaluation.collect import collect_rows
from orchestrator.evaluation.stats import wilson_interval

MIN_INTERVAL_DAYS = 14


def prepare(n: int = 20, seed: int = 244) -> Path:
    rows = [
        r
        for r in collect_rows()
        if r["scenario"] in ("s3", "s4") and not r["preset"] and r.get("built_ok")
    ]
    rng = random.Random(seed)
    rng.shuffle(rows)
    chosen = rows[:n]
    out = RESULTS / "labeling"
    out.mkdir(parents=True, exist_ok=True)
    key = [
        {
            "screen_id": r["screen_id"],
            "model": r["model"],
            "scenario": r["scenario"],
            "source": r["source"],
            "detector_mvvm": r["mvvm_compliant"],
        }
        for r in chosen
    ]
    (out / "hidden_key.json").write_text(json.dumps(key, indent=2), encoding="utf-8")
    sheet = []
    for round_id in (1, 2):
        order = chosen[:]
        rng.shuffle(order)
        for i, r in enumerate(order, 1):
            sheet.append(
                {
                    "round": round_id,
                    "item": i,
                    "screen_id": r["screen_id"],
                    "model": r["model"],
                    "scenario": r["scenario"],
                    "label": "",
                }
            )
    path = out / "worksheet.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["round", "item", "screen_id", "model", "scenario", "label"])
        w.writeheader()
        w.writerows(sheet)
    meta = {
        "n": len(chosen),
        "round1_started_utc": datetime.now(timezone.utc).isoformat(),
        "round2_started_utc": "",
        "interval_days": None,
        "min_interval_days": MIN_INTERVAL_DAYS,
        "note": "Record round2_started_utc after at least 14 days. Detector output is not in the worksheet.",
    }
    (out / "protocol.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    (out / "third_review.csv").write_text("screen_id,model,scenario,final_label,borderline,notes\n", encoding="utf-8")
    return path


def _kappa(a: list[int], b: list[int]) -> float:
    n = len(a)
    if n == 0:
        return 0.0
    po = sum(x == y for x, y in zip(a, b, strict=False)) / n
    p1 = sum(a) / n
    q1 = 1 - p1
    p2 = sum(b) / n
    q2 = 1 - p2
    pe = p1 * p2 + q1 * q2
    return 0.0 if pe == 1 else (po - pe) / (1 - pe)


def score(worksheet: Path | None = None) -> dict:
    out = RESULTS / "labeling"
    ws = worksheet or (out / "worksheet.csv")
    protocol = json.loads((out / "protocol.json").read_text(encoding="utf-8")) if (out / "protocol.json").exists() else {}
    interval = protocol.get("interval_days")
    if interval is not None and interval < MIN_INTERVAL_DAYS:
        raise RuntimeError(f"Labeling interval {interval} < {MIN_INTERVAL_DAYS} days")
    key = {(r["screen_id"], r["model"], r["scenario"]): r for r in json.loads((out / "hidden_key.json").read_text(encoding="utf-8"))}
    by_round: dict[int, dict] = {1: {}, 2: {}}
    with ws.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            lab = row["label"].strip().lower() in ("1", "true", "yes", "compliant")
            by_round[int(row["round"])][(row["screen_id"], row["model"], row["scenario"])] = lab
    keys = sorted(key)
    r1 = [int(by_round[1].get(k, False)) for k in keys]
    r2 = [int(by_round[2].get(k, False)) for k in keys]
    disagreements = [k for k in keys if by_round[1].get(k) != by_round[2].get(k)]
    third: dict[tuple, dict] = {}
    third_path = out / "third_review.csv"
    if third_path.exists():
        with third_path.open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                if not row.get("screen_id"):
                    continue
                k = (row["screen_id"], row["model"], row["scenario"])
                third[k] = row
    final = []
    borderline = []
    for k in keys:
        if k in disagreements:
            rec = third.get(k)
            if rec and rec.get("final_label"):
                lab = rec["final_label"].strip().lower() in ("1", "true", "yes", "compliant")
                if rec.get("borderline", "").strip().lower() in ("1", "true", "yes"):
                    borderline.append({"screen_id": k[0], "model": k[1], "scenario": k[2]})
            else:
                lab = False
                borderline.append({"screen_id": k[0], "model": k[1], "scenario": k[2], "unresolved": True})
            final.append(int(lab))
        else:
            final.append(r2[keys.index(k)])
    det = [int(key[k]["detector_mvvm"]) for k in keys]
    tp = sum(d == 1 and m == 1 for d, m in zip(det, final, strict=False))
    tn = sum(d == 0 and m == 0 for d, m in zip(det, final, strict=False))
    fp = sum(d == 1 and m == 0 for d, m in zip(det, final, strict=False))
    fn = sum(d == 0 and m == 1 for d, m in zip(det, final, strict=False))
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    acc, lo, hi = wilson_interval(tp + tn, len(keys))
    report = {
        "intra_rater_kappa": _kappa(r1, r2),
        "confusion_matrix": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
        "precision": prec,
        "recall": rec,
        "f1": f1,
        "accuracy": acc,
        "accuracy_ci_lo": lo,
        "accuracy_ci_hi": hi,
        "n": len(keys),
        "interval_days": interval,
        "disagreements": len(disagreements),
        "borderline": borderline,
    }
    (out / "score.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
