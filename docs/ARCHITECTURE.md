# Architecture

The orchestrator is a command-line research pipeline. Layers depend inward only.

```
interfaces (CLI)
    -> evaluation
    -> infrastructure
        -> application
            -> domain
```

## Packages

- `orchestrator/domain` — `Screen`, scenarios, R1–R6, scoring. No I/O.
- `orchestrator/application` — ports, Algorithm 3.1 (`migrate_screen`), B0 transpiler, job iteration.
- `orchestrator/infrastructure` — OpenRouter client, Gradle harness, dataset mining/freeze, JSON stores.
- `orchestrator/evaluation` — collect, validate, stats, labeling, CodeBLEU-adapted, visual fidelity, figures.
- `orchestrator/interfaces/cli.py` — the only user interface (`python -m orchestrator`).

## Pipeline

1. Mine Apache-2.0 Kotlin Android screens and freeze `data/dataset/benchmark_150.json`.
2. Optionally select and verify hand-authored Compose references under `data/ground_truth/manual/`.
3. `run matrix|ablation|b0` writes one `MigrationResult` JSON per (model, scenario or preset, screen, run_index).
4. `validate` / `collect` / `stats` / `figures` consume those files. No metrics are stored in source.

Import boundaries are enforced with import-linter (`pyproject.toml`).
