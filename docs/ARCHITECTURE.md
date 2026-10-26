# Architecture

The orchestrator is a command-line research pipeline. There is no web app, HTTP server, or dashboard. Layers depend inward only.

```
interfaces (CLI)
    -> evaluation
    -> infrastructure
        -> application
            -> domain
```

`python -m orchestrator` and `python -m orchestrator.main` share the same entry point (`orchestrator.interfaces.cli.main`).

## Packages

- `orchestrator/domain` — models, R1–R6, scoring. Imports nothing from other layers.
- `orchestrator/application` — ports, Algorithm 3.1, B0 transpiler, prompts, job iteration. Imports only domain.
- `orchestrator/infrastructure` — OpenRouter, Gradle harness, dataset mining/freeze, JSON stores. Imports inward only (not evaluation or interfaces).
- `orchestrator/evaluation` — collect, validate, stats, labeling, CodeBLEU-adapted, visual fidelity, figures. Imports inward only (not interfaces).
- `orchestrator/interfaces` — CLI.
- `orchestrator/prompts/v1.1-thesis` — Appendix B templates.
- `orchestrator/config.py`, `orchestrator/__main__.py`, `orchestrator/main.py`.

Import-linter contracts in `pyproject.toml` cover all five layers plus explicit forbidden contracts for domain, application, evaluation, and infrastructure.

## Pipeline

1. `mine` Apache-2.0 Kotlin screens; each `meta.json` records repo, commit SHA, license, path.
2. `freeze-benchmark` writes `data/dataset/benchmark_150.json` (SHA-256 per screen).
3. `select-ground-truth` / `verify-ground-truth` for hand-authored Compose under `data/ground_truth/manual/`.
4. `run matrix|ablation|b0` (alias `b0`) writes one Appendix E JSON per (model, condition, screen, run).
5. `validate` must pass before `stats`. `collect` recomputes R1–R6 from the final code of every record.

Test doubles live only under `tests/`.
