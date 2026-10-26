"""
Mine GitHub for Kotlin Android repos with XML layouts and ViewModel usage.

Run: python -m orchestrator.dataset.mine --max-pages 2
Requires GITHUB_TOKEN for higher rate limits.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
import zipfile
from io import BytesIO
from pathlib import Path

import requests

from orchestrator.config import DATASET
from orchestrator.infrastructure.dataset.screen_repository import rebuild_index

HEADERS = {"Accept": "application/vnd.github+json"}
ALLOWED_LICENSES = {"apache-2.0"}

# Repos known to ship XML layouts + ViewModel (modern star-search often hits Compose-only apps).
CURATED_REPOS = [
    "android/uamp",
    "android/sunflower",
    "android/architecture-components-samples",
    "android/user-interface-samples",
    "nickbutcher/plaid",
    "google/iosched",
    "android/databinding-samples",
    "android/testing-samples",
    "android/platform-samples",
]


def _headers() -> dict:
    h = dict(HEADERS)
    token = os.getenv("GITHUB_TOKEN")
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def search_repos(stars_min: int = 200, max_pages: int = 10) -> list[str]:
    repos: list[str] = []
    for page in range(1, max_pages + 1):
        r = requests.get(
            "https://api.github.com/search/repositories",
            params={
                "q": f"language:Kotlin android \"R.layout\" stars:>{stars_min}",
                "sort": "stars",
                "per_page": 50,
                "page": page,
            },
            headers=_headers(),
            timeout=60,
        )
        r.raise_for_status()
        repos.extend(x["full_name"] for x in r.json().get("items", []))
        time.sleep(2)
    return repos


def repo_has_viewmodel(zip_bytes: bytes) -> bool:
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            if not name.endswith(".kt"):
                continue
            try:
                text = zf.read(name).decode("utf-8", errors="replace")
            except Exception:
                continue
            if "ViewModel" in text:
                return True
    return False


def fetch_license(full_name: str) -> str | None:
    owner, repo = full_name.split("/", 1)
    r = requests.get(
        f"https://api.github.com/repos/{owner}/{repo}/license",
        headers=_headers(),
        timeout=30,
    )
    if r.status_code != 200:
        return None
    return (r.json().get("license") or {}).get("spdx_id", "").lower()


def download_zip(full_name: str) -> bytes | None:
    owner, repo = full_name.split("/", 1)
    for branch in ("main", "master"):
        url = f"https://github.com/{owner}/{repo}/archive/refs/heads/{branch}.zip"
        r = requests.get(url, timeout=120)
        if r.status_code == 200:
            return r.content
    return None


def _zip_kt_files(zf: zipfile.ZipFile) -> dict[str, str]:
    files: dict[str, str] = {}
    for name in zf.namelist():
        if name.endswith(".kt"):
            try:
                files[name] = zf.read(name).decode("utf-8", errors="replace")
            except Exception:
                pass
    return files


def find_screen_context(kt_files: dict[str, str], layout_stem: str) -> dict[str, str]:
    """Find Activity/Fragment inflating layout and optional ViewModel (guide §1.2)."""
    patterns = [
        rf"R\.layout\.{layout_stem}\b",
        rf"layout/{layout_stem}\b",
        rf"@layout/{layout_stem}\b",
        rf"Activity{layout_stem.title().replace('_', '')}",
    ]
    context: dict[str, str] = {}
    for path, text in kt_files.items():
        if not any(re.search(p, text) for p in patterns):
            continue
        if "Activity" in text or "Fragment" in text or "AppCompatActivity" in text:
            key = "Activity.kt" if "Activity" in path or "Activity" in text else "Fragment.kt"
            if key not in context:
                context[key] = text
            vm_match = re.search(r"(\w+ViewModel)", text)
            if vm_match:
                vm_name = vm_match.group(1)
                for vpath, vtext in kt_files.items():
                    if f"class {vm_name}" in vtext:
                        context["ViewModel.kt"] = vtext
                        break
    return context


def slice_layouts(zip_bytes: bytes, repo_name: str, license_id: str, out_root: Path) -> int:
    count = 0
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        layouts = [n for n in zf.namelist() if "/res/layout/" in n and n.endswith(".xml")]
        if not layouts:
            return 0
        kt_files = _zip_kt_files(zf)
        for layout_path in layouts[:120]:
            stem = Path(layout_path).stem
            screen_id = f"{repo_name.replace('/', '_')}_{stem}"[:80]
            dest = out_root / screen_id
            if dest.exists():
                continue
            dest.mkdir(parents=True)
            xml = zf.read(layout_path).decode("utf-8", errors="replace")
            (dest / "layout.xml").write_text(xml, encoding="utf-8")
            for fname, content in find_screen_context(kt_files, stem).items():
                (dest / fname).write_text(content, encoding="utf-8")
            widgets = sorted(set(re.findall(r"<([\w.]+)", xml)))
            depth = max((line.count("    ") for line in xml.splitlines()), default=0)
            n_widgets = len([w for w in widgets if not w.startswith("android")])
            if n_widgets <= 5:
                complexity = "simple"
            elif n_widgets <= 12:
                complexity = "medium"
            else:
                complexity = "complex"
            meta = {
                "id": screen_id,
                "repo": repo_name,
                "license": license_id,
                "license_spdx": license_id,
                "layout": "layout.xml",
                "widgets": widgets[:20],
                "container": next((w for w in widgets if "Layout" in w), "Unknown"),
                "loc_xml": len(xml.splitlines()),
                "complexity": complexity,
                "nesting_depth": depth,
            }
            (dest / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
            count += 1
    return count


def build_index(screens_dir: Path) -> None:
    rebuild_index()


def main() -> None:
    parser = argparse.ArgumentParser(description="Mine GitHub for XML screen dataset")
    parser.add_argument("--stars-min", type=int, default=200)
    parser.add_argument("--max-pages", type=int, default=2)
    parser.add_argument("--max-repos", type=int, default=5)
    parser.add_argument("--repos", nargs="*", help="Explicit repo list (owner/name)")
    args = parser.parse_args()

    screens_dir = DATASET / "screens"
    screens_dir.mkdir(parents=True, exist_ok=True)
    if args.repos:
        repos = list(args.repos)
    else:
        searched = search_repos(stars_min=args.stars_min, max_pages=args.max_pages)
        repos = list(dict.fromkeys(CURATED_REPOS + searched))[: args.max_repos]
    total = 0
    for full_name in repos:
        lic = fetch_license(full_name)
        if not lic or lic not in ALLOWED_LICENSES:
            print(f"skip {full_name}: license {lic}")
            continue
        print(f"fetching {full_name}...")
        blob = download_zip(full_name)
        if not blob:
            print("  could not download zip")
            continue
        if not repo_has_viewmodel(blob) and full_name not in CURATED_REPOS:
            print("  skip: no ViewModel signal")
            continue
        n = slice_layouts(blob, full_name, lic or "unknown", screens_dir)
        total += n
        print(f"  added {n} screens")
        time.sleep(2)
    build_index(screens_dir)
    print(f"Done. Total new screens: {total}. Index at data/dataset/index.json")


if __name__ == "__main__":
    main()
