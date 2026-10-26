from __future__ import annotations

import re
import shutil
import subprocess
import time
from pathlib import Path

from orchestrator.domain.models import RuntimeResult
from orchestrator.infrastructure.harness.gradle import run_gradle


def _adb(serial: str | None, *args: str) -> list[str]:
    cmd = ["adb"]
    if serial:
        cmd.extend(["-s", serial])
    cmd.extend(args)
    return cmd


def _structural(code: str) -> RuntimeResult:
    errors: list[str] = []
    if "fun MigrationRoot" not in code:
        errors.append("Missing MigrationRoot entry composable.")
    if "@Composable" not in code:
        errors.append("No @Composable functions found.")
    if re.search(r"MigrationRoot\s*\(\s*\)\s*\{\s*\}", code):
        errors.append("MigrationRoot body is empty.")
    ui_markers = ("Text(", "Button(", "Column(", "Row(", "LazyColumn", "Image(", "TextField")
    if not any(m in code for m in ui_markers):
        errors.append("No recognizable Compose UI widgets in generated code.")
    return RuntimeResult(
        ok=not errors,
        method="structural",
        detail="Compose structure check (no device attached).",
        errors=errors,
    )


def adb_device_ready(serial: str | None = None) -> bool:
    if not shutil.which("adb"):
        return False
    proc = subprocess.run(_adb(None, "devices"), capture_output=True, text=True, timeout=15)
    lines = [ln.strip() for ln in proc.stdout.splitlines()[1:] if ln.strip()]
    ready = [ln for ln in lines if ln.endswith("device") and "offline" not in ln]
    if serial:
        return any(ln.split()[0] == serial for ln in ready)
    return bool(ready)


def _emulator(harness_dir: Path | None, serial: str | None) -> RuntimeResult:
    install = run_gradle(":app:installDebug", harness_dir=harness_dir)
    combined = install.stdout + install.stderr
    if install.returncode != 0 or "BUILD FAILED" in combined:
        return RuntimeResult(False, "emulator", "installDebug failed", ["APK install failed"])
    subprocess.run(_adb(serial, "shell", "am", "force-stop", "demo.harness"), capture_output=True, timeout=15)
    subprocess.run(_adb(serial, "logcat", "-c"), capture_output=True, timeout=15)
    start = subprocess.run(
        _adb(serial, "shell", "am", "start", "-n", "demo.harness/demo.MainActivity"),
        capture_output=True,
        text=True,
        timeout=15,
    )
    if start.returncode != 0:
        return RuntimeResult(False, "emulator", "Activity start failed", [start.stderr or start.stdout or "am start failed"])
    time.sleep(2)
    proc = subprocess.run(
        _adb(serial, "shell", "dumpsys", "activity", "activities"),
        capture_output=True,
        text=True,
        timeout=20,
    )
    text = proc.stdout or ""
    crashed = subprocess.run(
        _adb(serial, "logcat", "-d", "-t", "40", "*:E"),
        capture_output=True,
        text=True,
        timeout=20,
    )
    log = crashed.stdout or ""
    fatals = [ln for ln in log.splitlines() if "FATAL EXCEPTION" in ln or "AndroidRuntime" in ln]
    resumed = "demo.MainActivity" in text and "mResumedActivity" in text
    ok = resumed and not fatals
    return RuntimeResult(ok, "emulator", "installDebug + MainActivity launch", fatals[:5] if not ok else [])


class AdbRuntimeChecker:
    def check(
        self,
        code: str,
        *,
        built: bool,
        harness_dir: Path | None = None,
        device_serial: str | None = None,
    ) -> RuntimeResult:
        if not built:
            return RuntimeResult(False, "skipped", "Skipped: build not successful.", ["build failed"])
        if adb_device_ready(device_serial):
            return _emulator(harness_dir, serial=device_serial)
        return _structural(code)
