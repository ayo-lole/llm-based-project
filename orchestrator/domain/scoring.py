from __future__ import annotations

import re

from orchestrator.domain.rules import COMPLIANCE_RULES, WEIGHTS, check_arch_rules

EQUAL_WEIGHTS = {r: 100 / 6 for r in WEIGHTS}

_KNOWN_COMPOSE = (
    "Column", "Row", "Box", "Text", "Button", "Image", "Icon", "TextField", "OutlinedTextField",
    "LazyColumn", "LazyRow", "Modifier", "NavHost", "composable", "rememberNavController",
    "AsyncImage", "viewModel", "collectAsStateWithLifecycle", "collectAsState", "Scaffold",
    "TopAppBar", "FloatingActionButton", "Checkbox", "Switch", "Slider", "Card", "Spacer",
    "MaterialTheme", "padding", "fillMaxSize", "fillMaxWidth", "clickable", "Arrangement",
    "Alignment", "dp", "sp", "stringResource", "painterResource", "Icons",
)


def failed_rules(violations: list[str]) -> set[str]:
    return {m[1:3] for m in violations if re.match(r"^\[R[1-6]\]", m)}


def arch_score(violations: list[str], weights: dict[str, float] | None = None) -> float:
    w = weights or WEIGHTS
    return max(0.0, 100.0 - sum(w[r] for r in failed_rules(violations)))


def mvvm_compliant(violations: list[str]) -> bool:
    return not (failed_rules(violations) & set(COMPLIANCE_RULES))


def classify_errors(problems: list[str], code: str, xml: str | None = None) -> dict[str, int]:
    buckets = {
        "compilation": 0, "state_management": 0, "navigation": 0,
        "mvvm_violation": 0, "ui_rendering": 0, "static_analysis": 0,
        "unresolved_reference": 0, "type_mismatch": 0, "missing_import": 0,
        "composable_context": 0, "other_compile": 0, "custom_view": 0,
    }
    for p in problems:
        pl = p.lower()
        compile_like = pl.startswith("e:") or "compile" in pl or (".kt:" in pl and "error" in pl)
        if compile_like:
            buckets["compilation"] += 1
            if "Unresolved reference" in p:
                buckets["unresolved_reference"] += 1
                m = re.search(r"Unresolved reference[:\s']+(\w+)", p)
                name = m.group(1) if m else ""
                if name in _KNOWN_COMPOSE:
                    buckets["missing_import"] += 1
            elif "Type mismatch" in p or "type mismatch" in pl:
                buckets["type_mismatch"] += 1
            elif "@Composable invocations can only happen" in p:
                buckets["composable_context"] += 1
            else:
                buckets["other_compile"] += 1
        elif p.startswith(("[R1]", "[R4]")) or any(k in pl for k in ("mutablestate", "remember", "hoist")):
            buckets["state_management"] += 1
        elif "navcontroller" in pl or "navhost" in pl or "navigation" in pl:
            buckets["navigation"] += 1
        elif p.startswith(("[R2]", "[R3]", "[R5]", "[R6]")):
            buckets["mvvm_violation"] += 1
        else:
            buckets["static_analysis"] += 1
    if re.search(r"androidview\s*\(|canvas\s*\(|ondraw", code, re.I):
        buckets["ui_rendering"] += 1
    custom_xml = bool(xml and re.search(r"<[a-zA-Z][\w.]*\.[A-Z]\w+", xml))
    if "AndroidView(" in code or custom_xml:
        buckets["custom_view"] += 1
    return buckets


def violations_of(code: str) -> list[str]:
    return check_arch_rules(code)
