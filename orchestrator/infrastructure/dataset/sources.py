from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from orchestrator.config import DATASET, EXPECTED_BENCHMARK_REPOS, ROOT


def collect_repos() -> dict[str, dict]:
    screens = DATASET / "screens"
    grouped: dict[str, dict] = {}
    if not screens.exists():
        return grouped
    for folder in sorted(screens.iterdir()):
        meta_p = folder / "meta.json"
        if not folder.is_dir() or not meta_p.exists():
            continue
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
        repo = meta.get("repo") or meta.get("repository")
        if not repo:
            continue
        rec = grouped.setdefault(
            repo,
            {
                "repo": repo,
                "license": meta.get("license") or meta.get("license_spdx") or "",
                "commit_sha": meta.get("commit_sha") or "",
                "screens": [],
                "strata": defaultdict(int),
                "paths": set(),
            },
        )
        rec["screens"].append(folder.name)
        rec["strata"][str(meta.get("complexity", "unknown")).lower()] += 1
        rec["paths"].add(meta.get("layout", "layout.xml"))
        rec["paths"].add(meta.get("source_path") or meta.get("path") or "")
        if meta.get("commit_sha") and not rec["commit_sha"]:
            rec["commit_sha"] = meta["commit_sha"]
    return grouped


def distinct_benchmark_repos() -> set[str]:
    bench = DATASET / "benchmark_150.json"
    if not bench.exists():
        return set()
    raw = json.loads(bench.read_text(encoding="utf-8"))["screens"]
    ids = [x["id"] if isinstance(x, dict) else x for x in raw]
    repos: set[str] = set()
    for sid in ids:
        meta_p = DATASET / "screens" / sid / "meta.json"
        if not meta_p.exists():
            continue
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
        repo = meta.get("repo") or meta.get("repository")
        if repo:
            repos.add(repo)
    return repos


def write_dataset_sources(dest: Path | None = None) -> Path:
    dest = dest or (ROOT / "docs" / "DATASET_SOURCES.md")
    dest.parent.mkdir(parents=True, exist_ok=True)
    grouped = collect_repos()
    lines = [
        "# Dataset sources",
        "",
        "Repositories present under `data/dataset/screens`, recorded from each screen `meta.json`.",
        "",
        "| Repository | License (SPDX) | Commit SHA | Screens | Strata (S/M/C) | Paths used |",
        "|---|---|---|---|---|---|",
    ]
    for repo, rec in sorted(grouped.items()):
        strata = rec["strata"]
        smc = f"{strata.get('simple', 0)}/{strata.get('medium', 0)}/{strata.get('complex', 0)}"
        url = f"https://github.com/{repo}"
        sha = rec["commit_sha"] or "—"
        paths = ", ".join(p for p in sorted(rec["paths"]) if p)
        license_id = rec["license"] or "—"
        lines.append(
            f"| [{repo}]({url}) | {license_id} | `{sha}` | {len(rec['screens'])} | {smc} | {paths} |"
        )
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    repos = distinct_benchmark_repos()
    n = len(repos)
    print(f"Distinct repositories in benchmark_150.json: {n}")
    if n != EXPECTED_BENCHMARK_REPOS:
        print(
            f"WARNING: thesis states {EXPECTED_BENCHMARK_REPOS} distinct repositories; "
            f"computed {n}. Data was not changed."
        )
    return dest


def write_third_party_notices(dest: Path | None = None) -> Path:
    dest = dest or (ROOT / "THIRD_PARTY_NOTICES.md")
    grouped = collect_repos()
    blocks = [
        "# Third-party notices",
        "",
        "Screen excerpts are redistributed from Apache-2.0 projects with attribution from `meta.json`.",
        "",
    ]
    for repo, rec in sorted(grouped.items()):
        blocks.append(f"## {repo}")
        blocks.append("")
        blocks.append(f"- Source: https://github.com/{repo}")
        blocks.append(f"- License (SPDX, from meta.json): {rec.get('license') or 'Apache-2.0'}")
        if rec.get("commit_sha"):
            blocks.append(f"- Commit: `{rec['commit_sha']}`")
        blocks.append(f"- License URL: https://github.com/{repo}/blob/HEAD/LICENSE")
        blocks.append("")
    dest.write_text("\n".join(blocks), encoding="utf-8")
    return dest
