# Evaluation protocol

## Scenarios

| ID | Initial prompt | Constraints | Refinement |
|---|---|---|---|
| B0 | none (XML→Compose transpiler) | no | no |
| S1 | one-line instruction | no | no |
| S2 | senior-engineer role, Material 3, `@Preview` | no | no |
| S3 | architecture-constrained prompt | yes | no |
| S4 | same as S3 | yes | yes, k = 4 |

Ablations (all on S4): `no_feedback_loop`, `no_arch_constraint`, `no_static_analysis`.

## Algorithm 3.1

`k = 4` generate–analyze iterations (initial generation plus at most three refinements).

Default convergence: `compile_ok AND build_ok AND arch_violations == []`.
Under `no_static_analysis` or `no_arch_constraint`: `build_ok` only.
Style findings (Detekt, ktlint, Lint) are fed back but never block convergence.

Feedback order: compiler errors (≤ 8), then R1–R6 by descending weight (≤ 6), then other analyzer findings (≤ 6). Total ≤ 20 unique lines.

## R1–R6

| Rule | Weight | Check |
|---|---|---|
| R1 | 20 | ViewModel owns state; immutable `StateFlow`; no public mutable state |
| R2 | 10 | `collectAsStateWithLifecycle()` |
| R3 | 25 | no I/O or data access in `@Composable` |
| R4 | 15 | no business `remember { mutableStateOf }` in leaf composables |
| R5 | 10 | no direct UI mutation; events hoisted |
| R6 | 20 | no concrete data-layer construction; no Android UI types on ViewModel |

`@Preview` composables are ignored. MVVM-compliant ⇔ R1, R3, R4, R5 pass.
Clean Architecture Score = 100 − Σ weights of failed rules.

## Models and generation

- `openai/gpt-4o`, `google/gemini-2.5-flash`, `anthropic/claude-sonnet-4` via OpenRouter.
- Temperature 0.2, `max_tokens` 8192, Gemini reasoning off, prompt version `v1.1-thesis`.
- Cache key = SHA-256 of (model, temperature, system prompt, prompt, run_index).
- Strict mode on `run`: missing harness, unknown model, or `model_returned` mismatch raises.

Gemini 2.0 Flash and Claude 3.x Sonnet are no longer served; the substitutes above are used.

## Benchmark

Stratified freeze: 52 Simple / 71 Medium / 27 Complex, seed 244.
Ground truth: 35 screens (12 / 16 / 7), seed 244, hand-authored only.

## Statistics

Means over runs with 95% Wilson intervals. Paired unit (screen, model), n = 450.
McNemar (exact if b+c < 25, else χ² with continuity correction), Wilcoxon signed-rank with matched-pairs rank-biserial r, Mann–Whitney U with Cliff’s δ for strata, Holm adjustment within each table.

Paper 244 published aggregates appear only as `PAPER_244_REFERENCE` in `orchestrator/evaluation/stats.py`.
