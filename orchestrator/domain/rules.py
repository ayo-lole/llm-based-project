"""R1–R6 detectors: pure functions over Kotlin source text."""

from __future__ import annotations

import re

WEIGHTS = {"R1": 20, "R2": 10, "R3": 25, "R4": 15, "R5": 10, "R6": 20}
COMPLIANCE_RULES = ("R1", "R3", "R4", "R5")

_UI_STATE_NAMES = re.compile(
    r"(expanded|show\w*|visible|isVisible|isOpen|open|focus\w*|scroll\w*|menu\w*|dialog\w*|"
    r"tab\w*|selectedTab\w*|anim\w*|offset|size|height|width|pressed|hover\w*|sheet\w*|"
    r"textFieldValue|passwordVisible|isPasswordVisible)$",
    re.IGNORECASE,
)
_IO_PATTERNS = re.compile(
    r"\b(Retrofit|Room\.databaseBuilder|HttpURLConnection|OkHttpClient|URL\(|File\(|"
    r"getSharedPreferences|SharedPreferences|\.enqueue\(|Dispatchers\.IO|\w*[Rr]epository\.|"
    r"\w*Repository\(|\w*[Dd]ao\.|\w*Api\.|\w*Service\.\w+\(|database\.|\.execute\(\)|"
    r"FirebaseFirestore|contentResolver)"
)
_CLIENT_CONSTRUCTION = re.compile(
    r"\b(Retrofit\.Builder\(|Room\.databaseBuilder\(|OkHttpClient\(|HttpURLConnection|"
    r"[A-Z]\w*(Repository|RepositoryImpl|Api|Service|Dao|Database|DataSource)\()"
)
_ANDROID_UI_TYPES = re.compile(r"\b(Context|Activity|Fragment|View|Resources)\b")
_COMPOSABLE = re.compile(
    r"@Composable\s+(?:(?:private|internal|public)\s+)?fun\s+(?P<name>\w+)\s*\((?P<params>[^)]*)\)\s*(?::\s*\w+\s*)?\{",
    re.S,
)
_VIEWMODEL = re.compile(
    r"class\s+(?P<name>\w+)\s*(?:\((?P<params>[^)]*)\))?\s*:\s*(?:Android)?ViewModel\s*\([^)]*\)\s*\{",
    re.S,
)


def _blocks(code: str, header: re.Pattern) -> list[tuple[str, str, str]]:
    out = []
    for m in header.finditer(code):
        start = code.find("{", m.end() - 1)
        if start == -1:
            continue
        depth, i = 0, start
        while i < len(code):
            if code[i] == "{":
                depth += 1
            elif code[i] == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        out.append((m.group("name"), m.groupdict().get("params") or "", code[start + 1:i]))
    return out


def _composables(code: str):
    return [
        c for c in _blocks(code, _COMPOSABLE)
        if not re.search(
            r"@Preview[^\n]*\n\s*@Composable\s+(?:\w+\s+)?fun\s+" + re.escape(c[0]),
            code,
        )
    ]


def rule_violations(code: str) -> dict[str, list[str]]:
    v: dict[str, list[str]] = {r: [] for r in WEIGHTS}
    comps = _composables(code)
    vms = _blocks(code, _VIEWMODEL)
    has_vm = bool(vms)

    if comps and not has_vm:
        v["R1"].append("[R1] No ViewModel owns the presentation state (MVVM).")
    for name, params, body in vms:
        if (
            not re.search(r"\bval\s+\w+\s*:\s*StateFlow<", body)
            and "asStateFlow()" not in body
            and not re.search(r"\bstateIn\(", body)
        ):
            v["R1"].append(
                f"[R1] ViewModel {name} does not expose immutable UI state via StateFlow."
            )
        for m in re.finditer(
            r"^\s*(?!private)(?:public\s+)?(?:val|var)\s+(\w+)\s*(?::\s*Mutable\w+|=\s*Mutable\w+\()",
            body,
            re.M,
        ):
            v["R1"].append(
                f"[R1] ViewModel {name} exposes mutable state '{m.group(1)}' (should be private)."
            )
        if re.search(r"\bmutableStateOf\(", body) and not re.search(
            r"private\s+(?:val|var)\s+\w+\s*(?:by|=)\s*mutableStateOf", body
        ):
            v["R1"].append(
                f"[R1] ViewModel {name} exposes Compose mutableStateOf instead of StateFlow<UiState>."
            )

    if "StateFlow" in code or "uiState" in code:
        if re.search(r"\.collectAsState\(", code):
            v["R2"].append(
                "[R2] UI state collected with collectAsState() instead of collectAsStateWithLifecycle()."
            )
        elif has_vm and comps and "collectAsStateWithLifecycle" not in code:
            v["R2"].append("[R2] UI state not collected with collectAsStateWithLifecycle().")

    for name, params, body in comps:
        m = _IO_PATTERNS.search(body)
        if m:
            v["R3"].append(
                f"[R3] Data access or I/O inside composable {name} ('{m.group(0)}') — separation of concerns."
            )
        if re.search(r"\bLaunchedEffect\b[\s\S]{0,300}?(repository|api|fetch|load|http|dao)", body, re.I):
            v["R3"].append(
                f"[R3] Composable {name} loads data in LaunchedEffect instead of the ViewModel."
            )

    stateful_owner = {n for n, p, b in comps if re.search(r"viewModel\(|ViewModel\b", p + b)}
    for name, params, body in comps:
        if name in stateful_owner or name == "MigrationRoot":
            continue
        for m in re.finditer(
            r"(?:val|var)\s+(\w+)\s*(?:=|by)\s*(?:remember|rememberSaveable)\s*\{\s*mutable(?:State|StateList|StateMap|IntState|FloatState)Of",
            body,
        ):
            if not _UI_STATE_NAMES.search(m.group(1)):
                v["R4"].append(
                    f"[R4] Composable {name} holds business state '{m.group(1)}' instead of hoisting it (state hoisting)."
                )

    for name, params, body in comps:
        if re.search(
            r"\b\w*[uU]iState\.value\s*=|\b_\w+\.(value\s*=|update\s*\{)|\bviewModel\.\w+\s*=[^=]|\bvm\.\w+\s*=[^=]",
            body,
        ):
            v["R5"].append(
                f"[R5] Composable {name} mutates state directly instead of raising an event (UDF)."
            )
    if comps:
        has_lambda_params = any(re.search(r"->\s*Unit", p) for _, p, _ in comps)
        has_vm_events = re.search(r"\b(vm|viewModel)\s*(::|\.)\s*on[A-Z]\w*", code) is not None
        interactive = re.search(r"\bon(Click|ValueChange|CheckedChange)\s*=", code) is not None
        if interactive and not (has_lambda_params or has_vm_events):
            v["R5"].append("[R5] No event callbacks hoisted (events should flow up as lambdas).")

    for name, params, body in vms:
        m = _CLIENT_CONSTRUCTION.search(body)
        if m:
            v["R6"].append(
                f"[R6] ViewModel {name} constructs a concrete dependency '{m.group(0)}' instead of receiving it (dependency injection)."
            )
        if _ANDROID_UI_TYPES.search(params or ""):
            v["R6"].append(
                f"[R6] ViewModel {name} depends on an Android UI/context type in its constructor."
            )
        if re.search(r"@Composable|androidx\.compose\.ui\.graphics\.Color\b", body):
            v["R6"].append(f"[R6] ViewModel {name} references UI-layer types.")
    for name, params, body in comps:
        m = _CLIENT_CONSTRUCTION.search(body)
        if m:
            v["R6"].append(
                f"[R6] Composable {name} constructs '{m.group(0)}' (UI must depend only on the ViewModel)."
            )
    return v


def check_arch_rules(code: str) -> list[str]:
    return [msg for msgs in rule_violations(code).values() for msg in msgs]
