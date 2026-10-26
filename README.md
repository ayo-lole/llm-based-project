# Architecture-Constrained UI Migration

Command-line research artifact for the graduation thesis *Architecture-Constrained UI Migration: Improving LLM-based Translation from Android XML Layouts to Jetpack Compose with MVVM Compliance* (Dang Vu Quynh Huong, UEH). It re-executes the protocol of Paper 244 (Nguyen & Dang, ICAIN 2026): constraint-aware prompting plus a static-analysis-guided refinement loop (k = 4, rules R1–R6) on a stratified 150-screen Apache-2.0 benchmark.

This repository is a **CLI pipeline only**. It does not include a web app, HTTP server, `serve` command, or dashboard. `python -m orchestrator` and `python -m orchestrator.main` are the same entry point.

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for Clean Architecture layers and import-linter contracts.

## Requirements

- Python ≥ 3.11
- JDK 17
- Android SDK with an API 34 emulator
- Gradle wrapper in `apps/harness`
- OpenRouter account

Target operator environment: Windows 11 + PowerShell; Linux and macOS are also supported (`pathlib` only).

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
```

Put your own OpenRouter key in `.env` (`OPENROUTER_API_KEY` is empty in `.env.example`). Never commit `.env`. The key is never logged.

The full operator sequence is in [docs/SETUP_GUIDE.md](docs/SETUP_GUIDE.md). Protocol constants: [docs/PROTOCOL.md](docs/PROTOCOL.md). Further notes: [docs/](docs/).

## Commands (guide order)

All commands: `python -m orchestrator <command>`.

1. `mine`
2. `dataset-sources`
3. `freeze-benchmark`
4. `select-ground-truth` then `verify-ground-truth`
5. `preflight`
6. `make-workers` (default N = 4)
7. `run {b0|matrix|ablation}` (alias: `b0`); defaults `--workers 4`, `--n-runs 3`
8. `collect`
9. `validate`
10. `stats`
11. `labeling prepare` then `labeling score`
12. `code-similarity`
13. `visual-fidelity`
14. `figures`

`--limit` or `--n-runs` < 3 stores smoke-test records under `outputs/smoke`, not `outputs/results`.

`run` is strict by default: missing harness, unknown model, `model_returned` mismatch, or no emulator aborts the run.

## Data sources

Screens under `data/dataset` currently come from eight Apache-2.0 GitHub repositories (counts from `meta.json`):

| Repository | License | Screens |
|---|---|---|
| [android/architecture-components-samples](https://github.com/android/architecture-components-samples) | Apache-2.0 | 34 |
| [android/databinding-samples](https://github.com/android/databinding-samples) | Apache-2.0 | 4 |
| [android/platform-samples](https://github.com/android/platform-samples) | Apache-2.0 | 97 |
| [android/testing-samples](https://github.com/android/testing-samples) | Apache-2.0 | 10 |
| [android/uamp](https://github.com/android/uamp) | Apache-2.0 | 13 |
| [android/user-interface-samples](https://github.com/android/user-interface-samples) | Apache-2.0 | 52 |
| [google/iosched](https://github.com/google/iosched) | Apache-2.0 | 44 |
| [nickbutcher/plaid](https://github.com/nickbutcher/plaid) | Apache-2.0 | 15 |

Regenerate the provenance table with `python -m orchestrator dataset-sources` → [docs/DATASET_SOURCES.md](docs/DATASET_SOURCES.md) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). That command reports the number of distinct repositories in `benchmark_150.json` (thesis states 17) and warns if the computed number differs.

## Reproducibility

Call log: `outputs/results/_calls/calls.jsonl` (Table 11 fields). Result JSON follows Appendix E (`is_mock` is always false). Paper 244 reference charts use constants in `orchestrator/evaluation/paper244_reference.py` only.

## License and citation

No license file is present in this repository yet. Ask the author before redistributing beyond the thesis examination copy.

Cite Paper 244 as Nguyen & Dang, ICAIN 2026, and this artifact as the thesis re-execution by Dang Vu Quynh Huong.

## Author

Dang Vu Quynh Huong — huongdang1290@gmail.com
