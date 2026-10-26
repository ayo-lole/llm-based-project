"""Deterministic XML to Compose transpiler (no LLM)."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

HEADER = """package harness

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.horizontalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
"""

ANDROID = "{http://schemas.android.com/apk/res/android}"
SKIP_TAGS = {"data", "import", "variable", "requestFocus", "tag"}


def _local(tag: str) -> str:
    tag = tag.split("}")[-1]
    return tag.rsplit(".", 1)[-1]


def _attr(el: ET.Element, name: str, default: str = "") -> str:
    return el.attrib.get(ANDROID + name, el.attrib.get("android:" + name, default))


def _kstr(value: str) -> str:
    v = value.strip()
    if not v:
        return '""'
    m = re.match(r"@\{(.*)\}$", v, re.S)
    if m:
        v = "{" + m.group(1).strip() + "}"
    elif v.startswith("@string/"):
        v = v[len("@string/"):].replace("_", " ")
    elif v.startswith("@") or v.startswith("?"):
        v = v.split("/")[-1].replace("_", " ")
    v = v.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("\n", " ")
    return f'"{v}"'


def _dp(value: str) -> str | None:
    m = re.match(r"^(-?\d+(?:\.\d+)?)\s*(dp|dip|px)$", value.strip())
    return f"{m.group(1)}.dp" if m else None


def _modifier(el: ET.Element, extra: list[str] | None = None) -> str:
    parts: list[str] = []
    w, h = _attr(el, "layout_width"), _attr(el, "layout_height")
    if w in ("match_parent", "fill_parent") and h in ("match_parent", "fill_parent"):
        parts.append("fillMaxSize()")
    else:
        if w in ("match_parent", "fill_parent") or w == "0dp":
            parts.append("fillMaxWidth()")
        elif _dp(w):
            parts.append(f"width({_dp(w)})")
        if h in ("match_parent", "fill_parent"):
            parts.append("fillMaxHeight()")
        elif _dp(h):
            parts.append(f"height({_dp(h)})")
    pad = _dp(_attr(el, "padding"))
    if pad:
        parts.append(f"padding({pad})")
    else:
        for side, kt in (
            ("paddingStart", "start"),
            ("paddingLeft", "start"),
            ("paddingEnd", "end"),
            ("paddingRight", "end"),
            ("paddingTop", "top"),
            ("paddingBottom", "bottom"),
        ):
            v = _dp(_attr(el, side))
            if v:
                parts.append(f"padding({kt} = {v})")
    mtop = _dp(_attr(el, "layout_marginTop"))
    if mtop:
        parts.append(f"padding(top = {mtop})")
    if extra:
        parts.extend(extra)
    return "Modifier" + "".join("." + p for p in parts)


class B0Transpiler:
    def __init__(self) -> None:
        self.unmapped: list[str] = []

    def emit(self, el: ET.Element, depth: int) -> list[str]:
        tag = _local(el.tag)
        ind = "    " * depth
        if tag in SKIP_TAGS:
            return []
        if tag == "layout":
            out: list[str] = []
            for c in el:
                out.extend(self.emit(c, depth))
            return out
        if _attr(el, "visibility") == "gone":
            return [f"{ind}// {tag} omitted (visibility=gone)"]
        kids = [c for c in el if _local(c.tag) not in SKIP_TAGS]

        def block(head: str) -> list[str]:
            body: list[str] = []
            for c in kids:
                body.extend(self.emit(c, depth + 1))
            return [f"{ind}{head} {{"] + (body or [f"{ind}    Spacer(Modifier)"]) + [f"{ind}}}"]

        if tag in ("LinearLayout", "LinearLayoutCompat"):
            horiz = _attr(el, "orientation") == "horizontal"
            return block(f"{'Row' if horiz else 'Column'}(modifier = {_modifier(el)})")
        if tag in (
            "ConstraintLayout", "RelativeLayout", "FrameLayout", "CoordinatorLayout",
            "MotionLayout", "CardView", "MaterialCardView", "AppBarLayout",
            "CollapsingToolbarLayout", "DrawerLayout",
        ):
            container = "Card" if "Card" in tag else "Box"
            if container == "Card":
                return block(f"Card(modifier = {_modifier(el)})")
            return block(f"Box(modifier = {_modifier(el)})")
        if tag in ("ScrollView", "NestedScrollView"):
            return block(f"Column(modifier = {_modifier(el, ['verticalScroll(rememberScrollState())'])})")
        if tag == "HorizontalScrollView":
            return block(f"Row(modifier = {_modifier(el, ['horizontalScroll(rememberScrollState())'])})")
        if tag in ("TextView", "AppCompatTextView", "MaterialTextView"):
            return [f"{ind}Text(text = {_kstr(_attr(el, 'text') or _attr(el, 'hint'))}, modifier = {_modifier(el)})"]
        if tag in ("Button", "MaterialButton", "AppCompatButton"):
            return [f"{ind}Button(onClick = {{ }}, modifier = {_modifier(el)}) {{ Text({_kstr(_attr(el, 'text'))}) }}"]
        if tag in ("ImageButton", "FloatingActionButton"):
            return [f"{ind}FilledIconButton(onClick = {{ }}) {{ Text(\"•\") }}"]
        if tag in ("EditText", "TextInputEditText", "AppCompatEditText", "AutoCompleteTextView"):
            return [
                f"{ind}OutlinedTextField(value = \"\", onValueChange = {{ }}, "
                f"label = {{ Text({_kstr(_attr(el, 'hint'))}) }}, modifier = {_modifier(el)})"
            ]
        if tag == "TextInputLayout":
            return [line for c in kids for line in self.emit(c, depth)]
        if tag in ("CheckBox", "AppCompatCheckBox", "MaterialCheckBox"):
            return [f"{ind}Row {{ Checkbox(checked = false, onCheckedChange = {{ }}); Text({_kstr(_attr(el, 'text'))}) }}"]
        if tag in ("Switch", "SwitchCompat", "SwitchMaterial", "ToggleButton"):
            return [f"{ind}Row {{ Switch(checked = false, onCheckedChange = {{ }}); Text({_kstr(_attr(el, 'text'))}) }}"]
        if tag == "RadioButton":
            return [f"{ind}Row {{ RadioButton(selected = false, onClick = {{ }}); Text({_kstr(_attr(el, 'text'))}) }}"]
        if tag == "RadioGroup":
            return block(f"Column(modifier = {_modifier(el)})")
        if tag in ("ProgressBar", "ContentLoadingProgressBar", "CircularProgressIndicator"):
            horiz = "Horizontal" in _attr(el, "style", "") or "horizontal" in el.attrib.get("style", "").lower()
            return [f"{ind}{'LinearProgressIndicator()' if horiz else 'CircularProgressIndicator()'}"]
        if tag in ("SeekBar", "Slider"):
            return [f"{ind}Slider(value = 0f, onValueChange = {{ }})"]
        if tag in ("RecyclerView", "ListView", "GridView", "ViewPager", "ViewPager2"):
            return [f"{ind}LazyColumn(modifier = {_modifier(el)}) {{ }}  // items are bound at runtime; B0 has no data source"]
        if tag in ("ImageView", "AppCompatImageView", "ShapeableImageView"):
            return [f"{ind}Box(modifier = {_modifier(el)}.background(Color.LightGray))  // image omitted"]
        if tag in ("Toolbar", "MaterialToolbar"):
            return [f"{ind}Text(text = {_kstr(_attr(el, 'title'))}, fontSize = 20.sp, modifier = Modifier.padding(16.dp))"]
        if tag in ("View", "Space"):
            return [f"{ind}Spacer(modifier = {_modifier(el)})"]
        if tag in ("include", "fragment", "FragmentContainerView", "ViewStub"):
            ref = el.attrib.get("layout", "") or _attr(el, "name")
            return [f"{ind}Box(modifier = {_modifier(el)})  // {tag} {ref} not inlined by B0"]
        self.unmapped.append(tag)
        if kids:
            return block(f"Box(modifier = {_modifier(el)})  // B0-unmapped: {tag}")
        return [f"{ind}Box(modifier = {_modifier(el)})  // B0-unmapped: {tag}"]

    def transpile(self, xml: str) -> str:
        root = ET.fromstring(xml)
        body = self.emit(root, 1)
        return HEADER + "\n@Composable\nfun MigrationRoot() {\n" + "\n".join(body) + "\n}\n"


def transpile(xml: str) -> tuple[str, list[str]]:
    t = B0Transpiler()
    return t.transpile(xml), t.unmapped
