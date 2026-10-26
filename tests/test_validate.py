import json

from orchestrator.evaluation.validate import EXPECTED_ABLATION, EXPECTED_B0, EXPECTED_MATRIX, validate
from orchestrator.infrastructure.harness.writer import ensure_harness_entry


def test_validate_fails_empty(tmp_path, monkeypatch):
    from orchestrator.evaluation import collect as c
    from orchestrator.evaluation import validate as v

    monkeypatch.setattr(c, "load_benchmark_ids", lambda: ["s1"])
    monkeypatch.setattr(v, "load_benchmark_ids", lambda: ["s1"])
    report = validate(tmp_path)
    assert report["ok"] is False
    names = {c["check"]: c["ok"] for c in report["checks"]}
    assert names["matrix_n"] is False
    assert names["no_is_mock"] is True


def test_validate_rejects_mock(tmp_path, monkeypatch):
    from orchestrator.evaluation import collect as c
    from orchestrator.evaluation import validate as v

    def missing():
        raise FileNotFoundError

    monkeypatch.setattr(c, "load_benchmark_ids", missing)
    monkeypatch.setattr(v, "load_benchmark_ids", lambda: [])
    rec = {
        "screen_id": "x",
        "scenario": "s1",
        "ablation": "",
        "is_mock": True,
        "model": "openai/gpt-4o",
        "model_id": "openai/gpt-4o",
        "model_returned": "openai/gpt-4o",
        "run_index": 1,
        "history": [{"compile": {"compiled": True, "built": True, "runtime_ok": True, "runtime_method": "emulator"}, "code": ""}],
        "code": "class Foo",
    }
    path = tmp_path / "openai_gpt-4o" / "s1" / "x_run1.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(rec), encoding="utf-8")
    report = validate(tmp_path)
    names = {c["check"]: c["ok"] for c in report["checks"]}
    assert names["no_is_mock"] is False


def test_expected_counts():
    assert EXPECTED_MATRIX == 5400
    assert EXPECTED_ABLATION == 4050
    assert EXPECTED_B0 == 150


def test_entry_order():
    _, r1 = ensure_harness_entry("@Composable fun MigrationRoot() {}")
    assert r1 == "existing"
    _, r2 = ensure_harness_entry("@Composable fun LoginScreen(x: Int = 1) {}")
    assert r2 == "screen_defaults"
    _, r3 = ensure_harness_entry("@Composable fun Body() {}")
    assert r3 == "parameterless"
    _, r4 = ensure_harness_entry("@Preview @Composable fun Prev() {}")
    assert r4 == "preview"
    _, r5 = ensure_harness_entry("@Composable fun LoginScreen(onClick: () -> Unit, state: LoginUiState) {}")
    assert r5 == "screen_generated_defaults"
    _, r6 = ensure_harness_entry("class Foo")
    assert r6 == "missing"
