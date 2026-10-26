from __future__ import annotations

import csv
import json
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

from orchestrator.config import GROUND_TRUTH, HARNESS, RESULTS, RUNTIME_LAUNCH_S
from orchestrator.evaluation.collect import collect_rows
from orchestrator.infrastructure.harness.gradle import run_gradle
from orchestrator.infrastructure.harness.runtime_adb import HARNESS_ACTIVITY, _adb, adb_device_ready
from orchestrator.infrastructure.harness.writer import FileHarnessWriter


def _screencap(serial: str | None) -> np.ndarray:
    proc = subprocess.run(_adb(serial, "exec-out", "screencap", "-p"), capture_output=True, timeout=30)
    if proc.returncode != 0 or not proc.stdout:
        raise RuntimeError("screencap failed")
    import io

    from PIL import Image

    img = Image.open(io.BytesIO(proc.stdout)).convert("L")
    return np.asarray(img, dtype=np.float64) / 255.0


def _dump_a11y(serial: str | None) -> list[dict]:
    proc = subprocess.run(
        _adb(serial, "exec-out", "uiautomator", "dump", "/dev/tty"),
        capture_output=True,
        text=True,
        timeout=30,
    )
    text = proc.stdout or ""
    try:
        root = ET.fromstring(text[text.find("<"):])
    except ET.ParseError:
        return []
    nodes = []
    for el in root.iter():
        nodes.append(
            {
                "text": (el.attrib.get("text") or "").strip(),
                "desc": (el.attrib.get("content-desc") or "").strip(),
            }
        )
    return nodes


def ssim_gray(a: np.ndarray, b: np.ndarray, crop: int = 80) -> float:
    from skimage.metrics import structural_similarity

    h = min(a.shape[0], b.shape[0])
    w = min(a.shape[1], b.shape[1])
    a = a[crop:h, :w]
    b = b[crop:h, :w]
    return float(structural_similarity(a, b, data_range=1.0))


def pixel_diff_share(a: np.ndarray, b: np.ndarray, crop: int = 80, thresh: float = 16 / 255) -> float:
    h = min(a.shape[0], b.shape[0])
    w = min(a.shape[1], b.shape[1])
    a = a[crop:h, :w]
    b = b[crop:h, :w]
    return float(np.mean(np.abs(a - b) > thresh))


def a11y_coverage(ref_nodes: list[dict], cand_nodes: list[dict]) -> float:
    ref = {n["text"] or n["desc"] for n in ref_nodes if n["text"] or n["desc"]}
    if not ref:
        return 0.0
    cand = {n["text"] or n["desc"] for n in cand_nodes if n["text"] or n["desc"]}
    return len(ref & cand) / len(ref)


def _launch(serial: str | None, code: str, sid: str, writer: FileHarnessWriter) -> bool:
    writer.write(code, harness_dir=HARNESS, screen_id=sid)
    inst = run_gradle(":app:installDebug", harness_dir=HARNESS)
    if inst.returncode != 0:
        return False
    subprocess.run(_adb(serial, "logcat", "-c"), capture_output=True, timeout=15)
    subprocess.run(_adb(serial, "shell", "am", "start", "-n", HARNESS_ACTIVITY), capture_output=True, timeout=15)
    time.sleep(RUNTIME_LAUNCH_S)
    return True


def run_visual_fidelity(serial: str | None = None, crop: int = 80) -> Path:
    if not adb_device_ready(serial):
        raise RuntimeError("An emulator is required for visual-fidelity; no screenshot substitute is used.")
    writer = FileHarnessWriter()
    manual = GROUND_TRUTH / "manual"
    refs = sorted(manual.glob("*.kt"))
    rows_by_id = {(r["screen_id"], r["scenario"]): r for r in collect_rows() if r["scenario"] in ("s1", "s4", "b0")}
    attempted = 0
    rendered = 0
    rows = []
    for ref in refs:
        sid = ref.stem
        attempted += 1
        if not _launch(serial, ref.read_text(encoding="utf-8"), sid, writer):
            continue
        try:
            ref_img = _screencap(serial)
        except RuntimeError:
            continue
        ref_nodes = _dump_a11y(serial)
        rendered += 1
        for sc in ("s1", "s4", "b0"):
            cand = rows_by_id.get((sid, sc))
            if not cand or not cand.get("code"):
                continue
            if not _launch(serial, cand["code"], sid, writer):
                continue
            try:
                img = _screencap(serial)
            except RuntimeError:
                continue
            nodes = _dump_a11y(serial)
            rows.append(
                {
                    "screen_id": sid,
                    "scenario": sc,
                    "ssim": ssim_gray(ref_img, img, crop),
                    "pixel_diff": pixel_diff_share(ref_img, img, crop),
                    "a11y_coverage": a11y_coverage(ref_nodes, nodes),
                }
            )
    dest = RESULTS / "tables" / "visual_fidelity.csv"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=["screen_id", "scenario", "ssim", "pixel_diff", "a11y_coverage", "n_rendered", "n_attempted"],
        )
        w.writeheader()
        w.writerow({"n_rendered": rendered, "n_attempted": attempted})
        for row in rows:
            w.writerow(row)
    (RESULTS / "tables" / "visual_fidelity_n.json").write_text(
        json.dumps({"n_rendered": rendered, "n_attempted": attempted, "n_pairs": len(rows)}),
        encoding="utf-8",
    )
    return dest
