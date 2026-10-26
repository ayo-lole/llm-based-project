from __future__ import annotations

from orchestrator.domain.models import CompileResult, StaticAnalysisResult
from orchestrator.domain.rules import WEIGHTS


def collect_problems(
    compile_res: CompileResult,
    sa_res: StaticAnalysisResult,
    arch_violations: list[str],
    *,
    compile_only: bool = False,
) -> list[str]:
    problems: list[str] = []
    if compile_res.errors:
        problems.extend(compile_res.errors[:8])
    elif not compile_res.ok:
        problems.append("Gradle assembleDebug failed — fix compilation errors.")
    if compile_only:
        return _dedupe(problems)
    problems.extend(arch_violations)
    problems.extend(sa_res.detekt_issues)
    problems.extend(sa_res.ktlint_issues)
    problems.extend(sa_res.lint_issues)
    return _dedupe(problems)


def prioritize(problems: list[str]) -> list[str]:
    compiler, arch, other = [], [], []
    for p in problems:
        pl = p.lower()
        if p.startswith("e: ") or ".kt:" in p or "compile" in pl or "gradle" in pl:
            compiler.append(p)
        elif p.startswith("[R"):
            arch.append(p)
        else:
            other.append(p)
    arch.sort(key=lambda m: -WEIGHTS.get(m[1:3], 0) if m.startswith("[R") else 0)
    ranked = compiler[:8] + arch[:6] + other[:6]
    return _dedupe(ranked)[:20]


def format_feedback(problems: list[str]) -> str:
    ranked = prioritize(problems)
    if not ranked:
        return "No specific issues recorded."
    return "\n".join(f"- {x}" for x in ranked)


def categorize_problems(problems: list[str]) -> dict[str, int]:
    cats = {"compiler": 0, "architecture": 0, "static_analysis": 0}
    for p in problems:
        pl = p.lower()
        if p.startswith("e: ") or ".kt:" in p or "compile" in pl or "gradle" in pl:
            cats["compiler"] += 1
        elif p.startswith("[R"):
            cats["architecture"] += 1
        else:
            cats["static_analysis"] += 1
    return cats


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.strip()
        if key and key not in seen:
            seen.add(key)
            out.append(key)
    return out
