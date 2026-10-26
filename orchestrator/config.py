from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from orchestrator.domain.models import ABLATION_PRESETS, MODELS, SCENARIOS

__all__ = ["ABLATION_PRESETS", "MODELS", "SCENARIOS"]

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

ORCHESTRATOR = ROOT / "orchestrator"
HARNESS = ROOT / "apps" / "harness"
DATASET = ROOT / "data" / "dataset"
GROUND_TRUTH = ROOT / "data" / "ground_truth"
RESULTS = ROOT / "outputs" / "results"
SMOKE_RESULTS = ROOT / "outputs" / "smoke"
CACHE = ROOT / "data" / "cache"
PROMPTS = ORCHESTRATOR / "prompts"
PROMPT_VERSION_DIR = PROMPTS / "v1.1-thesis"
HARNESS_PACKAGE = "harness"
GENERATED_KT = HARNESS / "app" / "src" / "main" / "java" / HARNESS_PACKAGE / "Generated.kt"

SCENARIO_TEMPLATES = {
    "s1": "s1.txt",
    "s2": "s2.txt",
    "s3": "s3.txt",
    "s4": "s3.txt",
    "refine": "refine.txt",
}
HARNESS_ENTRY_COMPOSABLE = "MigrationRoot"
EXPECTED_BENCHMARK_REPOS = 17
DEFAULT_WORKERS = 4
DEFAULT_N_RUNS = 3
MAX_ITER = 4
RUNTIME_LAUNCH_S = 10

# Thesis 3.2.2: view-hierarchy depth, widget count, nested lists / dynamic content.
COMPLEXITY_THRESHOLDS = {
    "simple_max_depth": 4,
    "simple_max_widgets": 15,
    "complex_min_depth": 8,
    "complex_min_widgets": 35,
    "list_tags": (
        "RecyclerView",
        "ListView",
        "GridView",
        "ViewPager",
        "ViewPager2",
        "ExpandableListView",
    ),
}


def generation_settings() -> dict:
    seed = os.getenv("LLM_SEED")
    return {
        "temperature": float(os.getenv("LLM_TEMPERATURE", "0.2")),
        "max_tokens": int(os.getenv("OPENROUTER_MAX_TOKENS", "8192")),
        "gemini_reasoning": os.getenv("GEMINI_REASONING", "off"),
        "seed": int(seed) if seed else None,
        "prompt_template_version": os.getenv("PROMPT_TEMPLATE_VERSION", "v1.1-thesis"),
    }


def load_templates() -> dict[str, str]:
    version = os.getenv("PROMPT_TEMPLATE_VERSION", "v1.1-thesis")
    folder = PROMPTS / version
    if not folder.is_dir():
        folder = PROMPT_VERSION_DIR
    return {key: (folder / name).read_text(encoding="utf-8") for key, name in SCENARIO_TEMPLATES.items()}
