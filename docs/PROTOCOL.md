# Evaluation protocol

Constants below are the thesis Chapter 3 protocol. Measured rates are never stored in source.

## Scenarios

| ID | Initial prompt | Constraints | Refinement |
|---|---|---|---|
| B0 | XML→Compose transpiler (no LLM) | no | no |
| S1 | one-line instruction (Appendix B.1) | no | no |
| S2 | senior-engineer role, Material 3, `@Preview` (Appendix B.2) | no | no |
| S3 | architecture-constrained prompt (Appendix B.3) | yes | no |
| S4 | same as S3 | yes | yes, k = 4 |

Ablations (all on S4):

| Preset | Behaviour |
|---|---|
| `no_feedback_loop` | Single constrained pass (equivalent to S3). |
| `no_arch_constraint` | First draft uses the **S2** template (`orchestrator/prompts/v1.1-thesis/s2.txt`). No architecture feedback. Converge on `compile_ok AND build_ok`. |
| `no_static_analysis` | Compile-only feedback. Converge on `compile_ok AND build_ok`. |

## Algorithm 3.1

`k = max_iter = 4` generate–analyze iterations (initial generation plus at most three refinements).

Default convergence: `compile_ok AND build_ok AND no R1–R6 violations`.
Style findings (Detekt, ktlint, Android Lint) are fed back but never block convergence.

Feedback: de-duplicate; compiler errors first (≤ 8), then architecture violations by descending rule weight (≤ 6), then other analyzer findings (≤ 6); at most 20 lines.

## R1–R6 (Table 6)

| Rule | Weight | Check |
|---|---|---|
| R1 | 20 | ViewModel exposes immutable `StateFlow<UiState>`; also a violation when no ViewModel exists |
| R2 | 10 | `StateFlow` collected without `collectAsStateWithLifecycle()` |
| R3 | 25 | repository / network / database / file calls inside any `@Composable` |
| R4 | 15 | business state in `remember { mutableStateOf }` inside a composable |
| R5 | 10 | UI mutates state directly; no event lambdas hoisted |
| R6 | 20 | concrete outer-layer client instantiated in UI or ViewModel |

`@Preview` composables are ignored. MVVM-compliant ⇔ R1, R3, R4, R5 pass.
Clean Architecture Score = 100 − Σ weights of failed rules (minimum 0).

## Models and generation

- OpenRouter only: `openai/gpt-4o`, `google/gemini-2.5-flash`, `anthropic/claude-sonnet-4`.
- Temperature 0.2, `max_tokens` 8192, Gemini reasoning off, prompt version `v1.1-thesis`.
- Seed is sent when the provider supports it; otherwise the call log stores `null`.
- Cache key = SHA-256 of (model, temperature, system prompt, prompt, run_index). Runs 1–3 are distinct API requests.
- Strict mode (default on): stop on missing harness, unknown model, `model_returned != model_id`, or any fallback.
- `finish_reason == length` is recorded and flagged; `validate` rejects those records.

## Harness

- Kotlin 2.0.x, Compose BOM 2024.09.00, AGP 8.5.x, JDK 17, Detekt 1.23.6, ktlint 1.3.1.
- Android Lint, Detekt and ktlint run in every analysis pass.
- Package `harness`; entry composable `MigrationRoot`.
- Compile = `assembleDebug` exit 0. Build = debug APK produced. Runtime = API 34 emulator, logcat cleared, no uncaught exception within 10 s. The emulator verdict is final.
- Without a device, runtime = `not_evaluated` and `run` refuses to start in strict mode.
- `make-workers N` (default 4) copies the harness and binds worker *i* to `adb -s` serial *i*.

## Benchmark (Thesis 3.2.1–3.2.3)

Exclude (a) seed/demonstration screens, (b) unparseable layout XML, (c) screens with no ViewModel evidence (no ViewModel class in the screen folder **and** no data-binding variable of a ViewModel type **and** no ViewModel reference in the Activity/Fragment).

Complexity thresholds (`orchestrator.config.COMPLEXITY_THRESHOLDS`):

| Stratum | Rule |
|---|---|
| Simple | depth ≤ 4 **and** widgets ≤ 15 **and** no dynamic content |
| Complex | nested lists, **or** depth ≥ 8, **or** widgets ≥ 35 |
| Medium | otherwise |

Sample 52 / 71 / 27 with `random.Random(244)`. Each frozen screen stores SHA-256. Ground truth: 12 / 16 / 7 from the freeze, seed 244.

Thesis narrative cites 17 distinct repositories in the freeze; `dataset-sources` warns if the computed count differs and does not alter the data.

## Smoke tests

`--limit` or `--n-runs` < 3 mark the run as a smoke test. Records are stored under `outputs/smoke`, never under `outputs/results`, so they cannot enter aggregation.

## Statistics (Thesis 3.7.4)

Wilson 95% CI for pooled rates; run-to-run SD per model; unit = (screen, model) pair, n = 450; binary outcomes by majority over 3 runs; counts/scores by mean.

McNemar: exact binomial if b + c < 25, else χ² with continuity correction; OR = b/c (+0.5 to both if c = 0) with Clopper–Pearson exact CI.

Wilcoxon signed-rank + matched-pairs rank-biserial r (RQ2, RQ3 ablations, RQ5 model pairs). Mann–Whitney U + Cliff’s δ for strata (unpaired). Holm correction within each table; report adjusted and unadjusted p.

Sensitivity: per-model tests; screen-cluster bootstrap (5,000 resamples, all 3 models of a screen together); weights: equal, leave-one-rule-out, 10,000 Dirichlet(1,…,1) vectors.

Convergence distribution: first pass / 1–2 refinements / 3rd refinement / not converged. Magnitude bands for every effect size.

Paper 244 published aggregates appear only in `orchestrator/evaluation/paper244_reference.py`.
