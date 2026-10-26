"""Algorithm 3.1: generate–analyze–refine, k = 4."""

from __future__ import annotations

import time
from pathlib import Path

from orchestrator.application.feedback import categorize_problems, collect_problems, format_feedback
from orchestrator.application.ports import (
    Compiler,
    HarnessWriter,
    LLMClient,
    ResultStore,
    RuntimeChecker,
    ScreenRepository,
    StaticAnalyzer,
)
from orchestrator.application.prompts import build_initial_prompt, build_refine_prompt, extract_kotlin
from orchestrator.domain.models import IterationRecord, MigrationResult, StaticAnalysisResult
from orchestrator.domain.rules import check_arch_rules
from orchestrator.domain.scoring import arch_score, classify_errors

K = 4


def migrate_screen(
    screen_id: str,
    client: LLMClient,
    templates: dict[str, str],
    screens: ScreenRepository,
    writer: HarnessWriter,
    compiler: Compiler,
    analyzer: StaticAnalyzer,
    runtime: RuntimeChecker,
    store: ResultStore,
    *,
    scenario: str = "s3",
    max_iter: int = K,
    no_feedback: bool = False,
    no_constraints: bool = False,
    no_static_analysis: bool = False,
    skip_android_lint: bool = True,
    ablation_label: str | None = None,
    run_index: int = 1,
    harness_dir: Path | None = None,
    device_serial: str | None = None,
    generation_settings: dict | None = None,
) -> MigrationResult:
    screen = screens.get(screen_id)
    prompt, system = build_initial_prompt(
        templates, scenario, screen.xml, screen.context, no_constraints=no_constraints
    )
    raw, _meta = client.generate(
        prompt, system, run_index=run_index, iteration=0, screen_id=screen_id,
        scenario=scenario, preset=ablation_label or "",
    )
    code = extract_kotlin(raw)
    history: list[IterationRecord] = []
    codes: list[str] = []
    converged = False
    settings = generation_settings or {}

    for it in range(1, max_iter + 1):
        _path, n_stubs, entry = writer.write(code, harness_dir=harness_dir, screen_id=screen_id)
        codes.append(code)
        t0 = time.perf_counter()
        compile_res = compiler.assemble(harness_dir)
        compile_s = time.perf_counter() - t0
        t1 = time.perf_counter()
        if no_static_analysis:
            sa_res = StaticAnalysisResult(True, True, True)
        else:
            sa_res = analyzer.analyze(harness_dir, skip_lint=skip_android_lint)
        static_s = time.perf_counter() - t1
        t2 = time.perf_counter()
        runtime_res = runtime.check(
            code, built=compile_res.built, harness_dir=harness_dir, device_serial=device_serial
        )
        runtime_s = time.perf_counter() - t2
        compile_dict = compile_res.to_dict()
        compile_dict.update(runtime_res.to_dict())
        compile_dict["harness_entry"] = entry
        arch_violations = [] if no_constraints else check_arch_rules(code)
        problems = collect_problems(
            compile_res, sa_res, arch_violations,
            compile_only=no_static_analysis,
        )
        history.append(
            IterationRecord(
                iteration=it,
                compile=compile_dict,
                static_analysis=sa_res.to_dict(),
                arch_violations=arch_violations,
                arch_score=arch_score(arch_violations),
                problems=problems,
                problem_categories=categorize_problems(problems),
                error_types=classify_errors(problems, code, screen.xml),
                code_lines=len(code.splitlines()),
                resource_stubs=n_stubs,
                harness_entry=entry,
                compile_s=round(compile_s, 3),
                static_s=round(static_s, 3),
                runtime_s=round(runtime_s, 3),
            )
        )
        build_ok = compile_res.ok and compile_res.built
        if no_static_analysis or no_constraints:
            converged = build_ok
        else:
            converged = build_ok and not arch_violations
        if converged or scenario != "s4" or it == max_iter:
            break
        if no_feedback:
            break
        refine_prompt, refine_system = build_refine_prompt(
            templates, code, format_feedback(problems), no_constraints=no_constraints
        )
        raw, _ = client.generate(
            refine_prompt, refine_system, run_index=run_index, iteration=it,
            screen_id=screen_id, scenario=scenario, preset=ablation_label or "",
        )
        code = extract_kotlin(raw)

    ablation: dict = {}
    if ablation_label:
        ablation["preset"] = ablation_label
    if no_constraints:
        ablation["no_constraints"] = True
    if no_static_analysis:
        ablation["no_static_analysis"] = True
    if no_feedback:
        ablation["no_feedback"] = True
    result = MigrationResult(
        screen_id=screen_id,
        model=client.model,
        scenario=scenario,
        code=code,
        converged=converged,
        iterations=len(history),
        xml=screen.xml,
        history=history,
        codes_per_iteration=codes,
        ablation=ablation,
        run_index=run_index,
        generation_settings=settings,
    )
    store.save(result)
    return result
