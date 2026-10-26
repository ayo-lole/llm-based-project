from __future__ import annotations

import re

NO_PROCESSORS = "Do not use Hilt, Koin or kapt/ksp annotation processors."
REPO_CTOR = (
    "Declare repository/data-source dependencies as interfaces in the same file "
    "and receive them through the ViewModel constructor."
)


def extract_kotlin(raw: str) -> str:
    text = raw.strip()
    fence = re.search(r"```(?:kotlin|kt)?\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    if not text.startswith("package ") and "package " in text:
        text = text[text.find("package "):]
    return text


def build_initial_prompt(
    templates: dict[str, str],
    scenario: str,
    xml: str,
    context: str,
    *,
    no_constraints: bool = False,
) -> tuple[str, str | None]:
    key = scenario
    if no_constraints and scenario == "s4":
        key = "s2"
    template = templates[key]
    prompt = template.replace("{XML}", xml)
    prompt = prompt.replace("{CONTEXT}", context.strip() or "(none)")
    system = None
    if key in ("s3", "s4") and not no_constraints:
        system = (
            "You are a senior Android engineer migrating screens to Jetpack Compose. "
            "Follow MVVM, UDF/state hoisting, separation of concerns, and collectAsStateWithLifecycle(). "
            f"{NO_PROCESSORS} {REPO_CTOR} "
            "Return only Kotlin source code in package demo."
        )
    return prompt, system


def build_refine_prompt(
    templates: dict[str, str],
    prev_code: str,
    feedback: str,
    *,
    no_constraints: bool = False,
) -> tuple[str, str | None]:
    prompt = (
        templates["refine"]
        .replace("{PREV_CODE}", prev_code)
        .replace("{FEEDBACK}", feedback)
    )
    system = None if no_constraints else (
        "You are a senior Android engineer migrating screens to Jetpack Compose. "
        f"{NO_PROCESSORS} {REPO_CTOR} Return only Kotlin source code in package demo."
    )
    return prompt, system
