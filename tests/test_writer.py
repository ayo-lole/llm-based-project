from orchestrator.infrastructure.harness.writer import (
    _normalise_r_imports,
    ensure_harness_entry,
    write_resource_stubs,
)  # noqa: SLF001


def test_existing_entry():
    code, rule = ensure_harness_entry("@Composable fun MigrationRoot() { Text(\"a\") }")
    assert rule == "existing"
    assert "fun MigrationRoot" in code


def test_screen_defaults():
    src = "@Composable fun LoginScreen(x: Int = 1) { }"
    code, rule = ensure_harness_entry(src)
    assert rule == "screen_defaults"
    assert "fun MigrationRoot" in code
    assert "LoginScreen()" in code


def test_parameterless():
    src = "@Composable fun Body() { Text(\"a\") }"
    _, rule = ensure_harness_entry(src)
    assert rule == "parameterless"


def test_preview():
    src = "@Preview @Composable fun Prev() { }"
    _, rule = ensure_harness_entry(src)
    assert rule == "preview"


def test_screen_generated_defaults():
    src = "@Composable fun LoginScreen(onClick: () -> Unit, state: LoginUiState) { }"
    code, rule = ensure_harness_entry(src)
    assert rule == "screen_generated_defaults"
    assert "onClick = { }" in code


def test_missing():
    src = "class Foo"
    _, rule = ensure_harness_entry(src)
    assert rule == "missing"


def test_r_import_normalise():
    src = "package harness\nimport com.app.R\nfun x() { R.string.hi }\n"
    out = _normalise_r_imports(src)
    assert "import harness.R" in out
    assert "com.app.R" not in out


def test_resource_stubs(tmp_path, monkeypatch):
    from orchestrator.infrastructure.harness import writer as w

    monkeypatch.setattr(w, "HARNESS", tmp_path)
    res = tmp_path / "app" / "src" / "main" / "res" / "values"
    res.mkdir(parents=True)
    n = write_resource_stubs("R.string.title R.drawable.icon", harness_dir=tmp_path)
    assert n == 2
    assert (tmp_path / "app" / "src" / "main" / "res" / "values" / "generated_stubs.xml").exists()
    assert (tmp_path / "app" / "src" / "main" / "res" / "drawable" / "icon.xml").exists()
