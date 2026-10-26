from orchestrator.domain.models import RuntimeResult
from orchestrator.infrastructure.harness.runtime_adb import AdbRuntimeChecker


def test_device_present_emulator_failure_is_final(monkeypatch):
    from orchestrator.infrastructure.harness import runtime_adb as rt

    monkeypatch.setattr(rt, "adb_device_ready", lambda serial=None: True)

    def boom(harness_dir=None, serial=None):
        return RuntimeResult(False, "emulator", "crash", ["FATAL"])

    monkeypatch.setattr(rt, "_emulator", boom)
    out = AdbRuntimeChecker().check("fun MigrationRoot() { Text(\"a\") }", built=True)
    assert out.ok is False
    assert out.method == "emulator"
