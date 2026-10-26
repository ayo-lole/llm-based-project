from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path

import requests

from orchestrator.config import DATASET, ROOT

HEADERS = {"Accept": "application/vnd.github+json"}


def _headers() -> dict:
    h = dict(HEADERS)
    token = os.getenv("GITHUB_TOKEN")
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


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
        if meta.get("commit_sha") and not rec["commit_sha"]:
            rec["commit_sha"] = meta["commit_sha"]
    return grouped


def confirm_license(repo: str) -> str:
    owner, name = repo.split("/", 1)
    r = requests.get(f"https://api.github.com/repos/{owner}/{name}/license", headers=_headers(), timeout=30)
    if r.status_code != 200:
        return "unknown"
    return ((r.json().get("license") or {}).get("spdx_id") or "unknown")


def write_dataset_sources(dest: Path | None = None) -> Path:
    dest = dest or (ROOT / "docs" / "DATASET_SOURCES.md")
    dest.parent.mkdir(parents=True, exist_ok=True)
    grouped = collect_repos()
    lines = [
        "# Dataset sources",
        "",
        "Repositories present under `data/dataset/screens`. Licenses confirmed via the GitHub License API.",
        "",
        "| Repository | License (SPDX) | Commit SHA | Screens | Strata (S/M/C) | Paths used |",
        "|---|---|---|---|---|---|",
    ]
    for repo, rec in sorted(grouped.items()):
        confirmed = confirm_license(repo)
        strata = rec["strata"]
        smc = f"{strata.get('simple', 0)}/{strata.get('medium', 0)}/{strata.get('complex', 0)}"
        url = f"https://github.com/{repo}"
        sha = rec["commit_sha"] or "—"
        paths = ", ".join(sorted(rec["paths"]))
        lines.append(
            f"| [{repo}]({url}) | {confirmed} | `{sha}` | {len(rec['screens'])} | {smc} | {paths} |"
        )
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dest


def write_third_party_notices(dest: Path | None = None) -> Path:
    dest = dest or (ROOT / "THIRD_PARTY_NOTICES.md")
    grouped = collect_repos()
    blocks = [
        "# Third-party notices",
        "",
        "Screen excerpts are redistributed from Apache-2.0 projects with attribution.",
        "",
    ]
    for repo in sorted(grouped):
        owner, name = repo.split("/", 1)
        notice = ""
        license_text = ""
        for fname in ("NOTICE", "NOTICE.txt", "NOTICE.md"):
            r = requests.get(
                f"https://raw.githubusercontent.com/{owner}/{name}/HEAD/{fname}",
                timeout=30,
            )
            if r.status_code == 200 and r.text.strip():
                notice = r.text.strip()[:8000]
                break
        r = requests.get(
            f"https://api.github.com/repos/{owner}/{name}/license",
            headers=_headers(),
            timeout=30,
        )
        if r.status_code == 200:
            content = (r.json().get("content") or "")
            import base64

            try:
                license_text = base64.b64decode(content).decode("utf-8", errors="replace")[:4000]
            except Exception:
                license_text = ""
        blocks.append(f"## {repo}")
        blocks.append("")
        blocks.append(f"- Source: https://github.com/{repo}")
        blocks.append(f"- License: https://github.com/{repo}/blob/HEAD/LICENSE")
        blocks.append("")
        if notice:
            blocks.append("NOTICE excerpt:")
            blocks.append("")
            blocks.append("```")
            blocks.append(notice)
            blocks.append("```")
            blocks.append("")
        if license_text:
            blocks.append("LICENSE excerpt:")
            blocks.append("")
            blocks.append("```")
            blocks.append(license_text)
            blocks.append("```")
            blocks.append("")
    dest.write_text("\n".join(blocks), encoding="utf-8")
    return dest
