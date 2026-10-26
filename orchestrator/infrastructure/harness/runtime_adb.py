from __future__ import annotations

import subprocess
import time
from pathlib import Path

from orchestrator.config import RUNTIME_LAUNCH_S
from orchestrator.domain.models import RuntimeResult
from orchestrator.infrastructure.harness.gradle import run_gradle

HARNESS_APP_ID = "harness"
HARNESS_ACTIVITY = "harness/.MainActivity"


def _adb(serial: str | None, *args: str) -> list[str]:
    cmd = ["adb"]
    if serial:
        cmd.extend(["-s", serial])
    cmd.extend(args)
    return cmd


def adb_device_ready(serial: str | None = None) -> bool:
    import shutil

    if not shutil.which("adb"):
        return False
    proc = subprocess.run(_adb(None, "devices"), capture_output=True, text=True, timeout=15)
    lines = [ln.strip() for ln in proc.stdout.splitlines()[1:] if ln.strip()]
    ready = [ln for ln in lines if ln.endswith("device") and "offline" not in ln]
    if serial:
        return any(ln.split()[0] == serial for ln in ready)
    return bool(ready)


def list_emulator_serials() -> list[str]:
    import shutil

    if not shutil.which("adb"):
        return []
    proc = subprocess.run(_adb(None, "devices"), capture_output=True, text=True, timeout=15)
    serials = []
    for ln in proc.stdout.splitlines()[1:]:
        parts = ln.strip().split()
        if len(parts) >= 2 and parts[1] == "device":
            serials.append(parts[0])
    return serials


def _emulator(harness_dir: Path | None, serial: str | None) -> RuntimeResult:
    install = run_gradle(":app:installDebug", harness_dir=harness_dir)
    combined = install.stdout + install.stderr
    if install.returncode != 0 or "BUILD FAILED" in combined:
        return RuntimeResult(False, "emulator", "installDebug failed", ["APK install failed"])
    subprocess.run(_adb(serial, "shell", "am", "force-stop", HARNESS_APP_ID), capture_output=True, timeout=15)
    subprocess.run(_adb(serial, "logcat", "-c"), capture_output=True, timeout=15)
    start = subprocess.run(
        _adb(serial, "shell", "am", "start", "-n", HARNESS_ACTIVITY),
        capture_output=True,
        text=True,
        timeout=15,
    )
    if start.returncode != 0:
        return RuntimeResult(
            False, "emulator", "Activity start failed", [start.stderr or start.stdout or "am start failed"]
        )
    time.sleep(RUNTIME_LAUNCH_S)
    proc = subprocess.run(
        _adb(serial, "shell", "dumpsys", "activity", "activities"),
        capture_output=True,
        text=True,
        timeout=20,
    )
    text = proc.stdout or ""
    crashed = subprocess.run(
        _adb(serial, "logcat", "-d", "*:E"),
        capture_output=True,
        text=True,
        timeout=20,
    )
    log = crashed.stdout or ""
    fatals = [
        ln
        for ln in log.splitlines()
        if "FATAL EXCEPTION" in ln or "AndroidRuntime" in ln or "UncaughtException" in ln
    ]
    resumed = "harness.MainActivity" in text and "mResumedActivity" in text
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
        return RuntimeResult(False, "not_evaluated", "No API 34 emulator attached.", ["emulator required"])
