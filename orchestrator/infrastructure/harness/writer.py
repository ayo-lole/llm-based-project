from __future__ import annotations

import re
from pathlib import Path
from xml.sax.saxutils import escape

from orchestrator.config import DATASET, GENERATED_KT, HARNESS, HARNESS_ENTRY_COMPOSABLE

PACKAGE_PREFIX = "package harness\n\n"


def _extract_kotlin(raw: str) -> str:
    text = raw.strip()
    fence = re.search(r"```(?:kotlin|kt)?\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    if not text.startswith("package ") and "package " in text:
        text = text[text.find("package "):]
    return text

RES_REF = re.compile(r"R\.(string|drawable|color|dimen|mipmap)\.(\w+)")
STUB_VECTOR = """<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp"
    android:height="24dp"
    android:viewportWidth="24"
    android:viewportHeight="24">
    <path
        android:fillColor="#FF888888"
        android:pathData="M2,2h20v20h-20z"/>
</vector>
"""
_COMPOSABLE_HEAD = re.compile(
    r"(?P<ann>(?:@\w+(?:\([^)]*\))?\s+)*)@Composable\s+(?:private\s+|internal\s+)?fun\s+(?P<name>\w+)\s*\(",
    re.S,
)


def _composables_meta(code: str) -> list[tuple[str, str, str]]:
    out = []
    for m in _COMPOSABLE_HEAD.finditer(code):
        i = m.end()
        depth = 1
        while i < len(code) and depth:
            if code[i] == "(":
                depth += 1
            elif code[i] == ")":
                depth -= 1
            i += 1
        params = code[m.end(): i - 1]
        out.append((m.group("ann") or "", m.group("name"), params))
    return out


def _params_all_defaulted(params: str) -> bool:
    params = params.strip()
    if not params:
        return True
    parts = [p.strip() for p in params.split(",") if p.strip()]
    return all("=" in p for p in parts)


def _params_only_lambdas_or_state(params: str) -> bool:
    parts = [p.strip() for p in params.split(",") if p.strip()]
    if not parts:
        return False
    for p in parts:
        if "=" in p:
            continue
        if "->" in p or "UiState" in p:
            continue
        return False
    return True


def _call_defaults(params: str) -> str:
    args = []
    for p in [x.strip() for x in params.split(",") if x.strip()]:
        if "=" in p:
            continue
        name = p.split(":")[0].strip().lstrip("val ").lstrip("var ").strip()
        typ = p.split(":", 1)[1].strip() if ":" in p else ""
        if "->" in typ:
            args.append(f"{name} = {{ }}")
        elif "UiState" in typ:
            args.append(f"{name} = {typ.split()[0]}()")
        else:
            args.append(f"{name} = {{ }}")
    return ", ".join(args)


def _wrap(name: str, call_args: str = "") -> str:
    return f"\n@Composable\nfun {HARNESS_ENTRY_COMPOSABLE}() {{\n    {name}({call_args})\n}}\n"


def ensure_harness_entry(code: str) -> tuple[str, str]:
    if f"fun {HARNESS_ENTRY_COMPOSABLE}" in code:
        return code, "existing"
    matches = _composables_meta(code)

    def is_preview(ann: str) -> bool:
        return "@Preview" in ann

    screens = [m for m in matches if m[1].endswith("Screen")]
    for _ann, name, params in screens:
        if _params_all_defaulted(params):
            return code.rstrip() + _wrap(name), "screen_defaults"
    for ann, name, params in matches:
        if is_preview(ann):
            continue
        if not params.strip():
            return code.rstrip() + _wrap(name), "parameterless"
    for ann, name, params in matches:
        if is_preview(ann):
            return code.rstrip() + _wrap(name), "preview"
    for _ann, name, params in screens:
        if _params_only_lambdas_or_state(params):
            args = _call_defaults(params)
            return code.rstrip() + _wrap(name, args), "screen_generated_defaults"
    return code, "missing"


def _res_dir(harness_dir: Path | None) -> Path:
    return (harness_dir or HARNESS) / "app" / "src" / "main" / "res"


def _generated_kt(harness_dir: Path | None, path: Path | None) -> Path:
    if path is not None:
        return path
    if harness_dir is not None:
        return harness_dir / "app" / "src" / "main" / "java" / "harness" / "Generated.kt"
    return GENERATED_KT


def _clear_previous_stubs(res: Path) -> None:
    stubs = res / "values" / "generated_stubs.xml"
    if stubs.exists():
        stubs.unlink()
    draw = res / "drawable"
    if draw.exists():
        for p in draw.glob("*.xml"):
            text = p.read_text(encoding="utf-8", errors="ignore")
            if "viewportWidth" in text and "M2,2h20v20h-20z" in text:
                p.unlink()


def _load_real_strings(screen_id: str | None) -> dict[str, str]:
    if not screen_id:
        return {}
    src = DATASET / "screens" / screen_id / "res" / "values" / "strings.xml"
    if not src.exists():
        src = DATASET / "screens" / screen_id / "values" / "strings.xml"
    if not src.exists():
        return {}
    text = src.read_text(encoding="utf-8", errors="replace")
    return {m.group(1): m.group(2) for m in re.finditer(r'<string name="(\w+)">([^<]*)</string>', text)}


def _humanise(name: str) -> str:
    return name.replace("_", " ").strip() or name


def _normalise_r_imports(kotlin: str) -> str:
    kotlin = re.sub(r"^import\s+[\w.]+(?:\.R|\.R\.\*)\s*$", "import harness.R", kotlin, flags=re.MULTILINE)
    if "import harness.R" not in kotlin and RES_REF.search(kotlin):
        if kotlin.startswith("package "):
            lines = kotlin.splitlines(True)
            insert_at = 1
            while insert_at < len(lines) and lines[insert_at].startswith("import "):
                insert_at += 1
            lines.insert(insert_at, "import harness.R\n")
            kotlin = "".join(lines)
        else:
            kotlin = "import harness.R\n" + kotlin
    return kotlin


def write_resource_stubs(
    kotlin: str,
    *,
    harness_dir: Path | None = None,
    screen_id: str | None = None,
) -> int:
    res = _res_dir(harness_dir)
    _clear_previous_stubs(res)
    refs = RES_REF.findall(kotlin)
    if not refs:
        return 0
    real_strings = _load_real_strings(screen_id)
    strings, colors, dimens, drawables = {}, {}, {}, set()
    for kind, name in refs:
        if kind == "string":
            strings[name] = real_strings.get(name, _humanise(name))
        elif kind == "color":
            colors[name] = "#FF888888"
        elif kind == "dimen":
            dimens[name] = "16dp"
        else:
            drawables.add(name)
    values = res / "values"
    values.mkdir(parents=True, exist_ok=True)
    parts = ['<?xml version="1.0" encoding="utf-8"?>', "<resources>"]
    for n, v in sorted(strings.items()):
        parts.append(f'    <string name="{n}">{escape(v)}</string>')
    for n, v in sorted(colors.items()):
        parts.append(f'    <color name="{n}">{v}</color>')
    for n, v in sorted(dimens.items()):
        parts.append(f'    <dimen name="{n}">{v}</dimen>')
    parts.append("</resources>")
    (values / "generated_stubs.xml").write_text("\n".join(parts) + "\n", encoding="utf-8")
    draw_dir = res / "drawable"
    mip_dir = res / "mipmap-mdpi"
    for name in sorted(drawables):
        dest_dir = mip_dir if any(k == "mipmap" and n == name for k, n in refs) else draw_dir
        dest_dir.mkdir(parents=True, exist_ok=True)
        (dest_dir / f"{name}.xml").write_text(STUB_VECTOR, encoding="utf-8")
        if dest_dir == mip_dir:
            draw_dir.mkdir(parents=True, exist_ok=True)
            (draw_dir / f"{name}.xml").write_text(STUB_VECTOR, encoding="utf-8")
    return len(refs)


def _normalize_package(code: str) -> str:
    if re.search(r"^package\s+", code, re.MULTILINE):
        return re.sub(r"^package\s+[\w.]+", "package harness", code, count=1, flags=re.MULTILINE)
    return PACKAGE_PREFIX + code


class FileHarnessWriter:
    def write(
        self,
        code: str,
        *,
        harness_dir: Path | None = None,
        screen_id: str | None = None,
    ) -> tuple[Path, int, str]:
        target = _generated_kt(harness_dir, None)
        kotlin, entry = ensure_harness_entry(_extract_kotlin(code))
        if not kotlin.startswith("package "):
            kotlin = PACKAGE_PREFIX + kotlin
        elif not kotlin.startswith("package harness"):
            kotlin = _normalize_package(kotlin)
        kotlin = _normalise_r_imports(kotlin)
        n_stubs = write_resource_stubs(kotlin, harness_dir=harness_dir, screen_id=screen_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(kotlin, encoding="utf-8")
        return target, n_stubs, entry
