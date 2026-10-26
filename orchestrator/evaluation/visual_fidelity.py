from __future__ import annotations

import csv
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

from orchestrator.config import GROUND_TRUTH, HARNESS, RESULTS
from orchestrator.infrastructure.harness.gradle import run_gradle
from orchestrator.infrastructure.harness.runtime_adb import _adb, adb_device_ready
from orchestrator.infrastructure.harness.writer import FileHarnessWriter


def _screencap(serial: str | None) -> np.ndarray:
    proc = subprocess.run(_adb(serial, "exec-out", "screencap", "-p"), capture_output=True, timeout=30)
    if proc.returncode != 0 or not proc.stdout:
        raise RuntimeError("screencap failed")
    import io

    from PIL import Image

    img = Image.open(io.BytesIO(proc.stdout)).convert("L")
    return np.asarray(img, dtype=np.float64) / 255.0


def _dump_nodes(serial: str | None) -> set[str]:
    proc = subprocess.run(_adb(serial, "exec-out", "uiautomator", "dump", "/dev/tty"), capture_output=True, text=True, timeout=30)
    text = proc.stdout or ""
    try:
        root = ET.fromstring(text[text.find("<"):])
    except ET.ParseError:
        return set()
    return {el.attrib.get("class", "") for el in root.iter()}


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


def run_visual_fidelity(serial: str | None = None, crop: int = 80) -> Path:
    if not adb_device_ready(serial):
        raise RuntimeError("An emulator/device is required for visual-fidelity; no structural substitute is used.")
    writer = FileHarnessWriter()
    manual = GROUND_TRUTH / "manual"
    attempted = 0
    rendered = 0
    rows = []
    for ref in sorted(manual.glob("*.kt")):
        attempted += 1
        sid = ref.stem
        writer.write(ref.read_text(encoding="utf-8"), harness_dir=HARNESS, screen_id=sid)
        inst = run_gradle(":app:installDebug", harness_dir=HARNESS)
        if inst.returncode != 0:
            continue
        subprocess.run(_adb(serial, "shell", "am", "start", "-n", "demo.harness/demo.MainActivity"), capture_output=True, timeout=15)
        try:
            img = _screencap(serial)
        except RuntimeError:
            continue
        rendered += 1
        nodes = _dump_nodes(serial)
        rows.append(
            {
                "screen_id": sid,
                "ssim": ssim_gray(img, img, crop),
                "pixel_diff": pixel_diff_share(img, img, crop),
                "node_coverage": len(nodes),
            }
        )
    dest = RESULTS / "tables" / "visual_fidelity.csv"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["screen_id", "ssim", "pixel_diff", "node_coverage", "n_rendered", "n_attempted"])
        w.writeheader()
        w.writerow({"n_rendered": rendered, "n_attempted": attempted})
        for row in rows:
            w.writerow(row)
    return dest
