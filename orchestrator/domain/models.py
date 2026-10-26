from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum


class Scenario(str, Enum):
    S1 = "s1"
    S2 = "s2"
    S3 = "s3"
    S4 = "s4"
    B0 = "b0"


class AblationPreset(str, Enum):
    NO_FEEDBACK_LOOP = "no_feedback_loop"
    NO_ARCH_CONSTRAINT = "no_arch_constraint"
    NO_STATIC_ANALYSIS = "no_static_analysis"


MODELS = (
    "openai/gpt-4o",
    "google/gemini-2.5-flash",
    "anthropic/claude-sonnet-4",
)
SCENARIOS = ("s1", "s2", "s3", "s4")
ABLATION_PRESETS = {
    "no_feedback_loop": {"no_feedback": True},
    "no_arch_constraint": {"no_constraints": True},
    "no_static_analysis": {"no_static_analysis": True},
}


@dataclass(frozen=True)
class Screen:
    id: str
    xml: str
    context: str = ""
    complexity: str = ""
    repo: str = ""
    license_spdx: str = ""
    commit_sha: str = ""
    source_url: str = ""


@dataclass
class CompileResult:
    ok: bool
    compiled: bool
    built: bool
    errors: list[str] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""

    def to_dict(self) -> dict:
        return {"ok": self.ok, "compiled": self.compiled, "built": self.built, "errors": self.errors}


@dataclass
class StaticAnalysisResult:
    detekt_ok: bool
    ktlint_ok: bool
    lint_ok: bool
    detekt_issues: list[str] = field(default_factory=list)
    ktlint_issues: list[str] = field(default_factory=list)
    lint_issues: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.detekt_ok and self.ktlint_ok and self.lint_ok

    def to_dict(self) -> dict:
        return {
            "detekt_ok": self.detekt_ok,
            "ktlint_ok": self.ktlint_ok,
            "lint_ok": self.lint_ok,
            "detekt_count": len(self.detekt_issues),
            "ktlint_count": len(self.ktlint_issues),
            "lint_count": len(self.lint_issues),
            "detekt_issues": self.detekt_issues,
            "ktlint_issues": self.ktlint_issues,
            "lint_issues": self.lint_issues,
        }


@dataclass
class RuntimeResult:
    ok: bool
    method: str
    detail: str = ""
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "runtime_ok": self.ok,
            "runtime_method": self.method,
            "runtime_detail": self.detail,
            "runtime_errors": self.errors,
        }


@dataclass
class RuleViolation:
    rule: str
    message: str


@dataclass
class IterationRecord:
    iteration: int
    compile: dict
    static_analysis: dict
    arch_violations: list[str]
    arch_score: float
    problems: list[str]
    problem_categories: dict[str, int] = field(default_factory=dict)
    error_types: dict[str, int] = field(default_factory=dict)
    code_lines: int = 0
    resource_stubs: int = 0
    harness_entry: str = ""
    compile_s: float = 0.0
    static_s: float = 0.0
    runtime_s: float = 0.0
    code: str = ""
    feedback: str = ""


@dataclass
class MigrationResult:
    screen_id: str
    model: str
    scenario: str
    code: str
    converged: bool
    iterations: int
    xml: str = ""
    history: list[IterationRecord] = field(default_factory=list)
    codes_per_iteration: list[str] = field(default_factory=list)
    ablation: dict = field(default_factory=dict)
    run_index: int = 1
    generation_settings: dict = field(default_factory=dict)
    provider: str = "openrouter"
    model_id: str = ""
    model_returned: str | None = None
    finish_reason: str | None = None
    cache_key: str | None = None
    tokens: dict = field(default_factory=dict)
    cost: float | None = None
    latency: float | None = None
    wall_s: float = 0.0
    is_mock: bool = False
    temperature: float | None = None
    max_tokens: int | None = None
    seed: int | None = None
    prompt_template_version: str = "v1.1-thesis"

    def to_dict(self) -> dict:
        settings = self.generation_settings or {}
        last = self.history[-1] if self.history else None
        runtime = (last.compile if last else {}) if last else {}
        return {
            "screen_id": self.screen_id,
            "scenario": self.scenario,
            "ablation": self.ablation.get("preset", "") if isinstance(self.ablation, dict) else self.ablation,
            "is_mock": False,
            "provider": self.provider,
            "model": self.model,
            "model_id": self.model_id or self.model,
            "run_index": self.run_index,
            "timestamp": settings.get("timestamp"),
            "temperature": self.temperature if self.temperature is not None else settings.get("temperature"),
            "max_tokens": self.max_tokens if self.max_tokens is not None else settings.get("max_tokens"),
            "seed": self.seed if self.seed is not None else settings.get("seed"),
            "prompt_template_version": self.prompt_template_version
            or settings.get("prompt_template_version", "v1.1-thesis"),
            "converged": self.converged,
            "iterations": self.iterations,
            "arch_score": last.arch_score if last else 0,
            "arch_violations": last.arch_violations if last else [],
            "history": [asdict(h) for h in self.history],
            "generation_settings": self.generation_settings,
            "code": self.code,
            "codes_per_iteration": self.codes_per_iteration,
            "model_returned": self.model_returned,
            "finish_reason": self.finish_reason,
            "cache_key": self.cache_key,
            "tokens": self.tokens,
            "cost": self.cost,
            "latency": self.latency,
            "wall_s": self.wall_s,
            "runtime": {
                "ok": runtime.get("runtime_ok"),
                "method": runtime.get("runtime_method"),
            },
        }
