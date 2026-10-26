# Setup guide — Architecture-Constrained UI Migration

Command-line research pipeline only. There is no web UI.

Companion DOCX: `docs/SETUP_GUIDE.docx`. Protocol constants: `docs/PROTOCOL.md`.

## 1. Environment

- Windows 11 + PowerShell (Linux/macOS also supported)
- Python ≥ 3.11, JDK 17, Android SDK, API 34 emulator
- OpenRouter API key (never commit `.env`)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
```

Edit `.env` and set `OPENROUTER_API_KEY`. `.env.example` leaves it empty.

`python -m orchestrator --help` and `python -m orchestrator.main --help` are the same CLI. Epilog: “Command-line research pipeline only.”

## 2. Dataset

```powershell
python -m orchestrator mine
python -m orchestrator dataset-sources
python -m orchestrator freeze-benchmark
python -m orchestrator select-ground-truth
python -m orchestrator verify-ground-truth
```

`freeze-benchmark` refuses to overwrite an existing `data/dataset/benchmark_150.json`. It prints eligible pool counts per stratum and raises if a quota cannot be filled. Do not invent screens to match the thesis repository count.

`verify-ground-truth` builds each `data/ground_truth/manual/<id>.kt` in the harness, launches the emulator, and requires R1–R6 with zero violations. Template stubs are rejected.

## 3. Preflight and workers

```powershell
python -m orchestrator preflight
python -m orchestrator make-workers
```

Default worker count is 4. Each copy is bound to its own `adb -s` serial.

## 4. Experiment

```powershell
python -m orchestrator run b0 --workers 4 --n-runs 3
python -m orchestrator b0 --workers 4
python -m orchestrator run matrix --workers 4 --n-runs 3
python -m orchestrator run ablation --workers 4 --n-runs 3
```

Strict mode is on: an emulator is required. `--limit` or `--n-runs` less than 3 writes to `outputs/smoke` so smoke records never enter aggregation.

## 5. Evaluation

```powershell
python -m orchestrator collect
python -m orchestrator validate
python -m orchestrator stats
python -m orchestrator labeling prepare
python -m orchestrator labeling score
python -m orchestrator code-similarity
python -m orchestrator visual-fidelity
python -m orchestrator figures
```

`validate` must pass before treating `stats` as thesis results (5,400 matrix + 4,050 ablation + 150 B0 records; no mocks; emulator runtime; no truncated outputs).

Visual fidelity requires the same emulator; there is no screenshot substitute.

## 6. Checks

```powershell
pytest
ruff check .
lint-imports
```
