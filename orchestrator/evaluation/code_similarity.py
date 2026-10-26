from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path

from orchestrator.config import GROUND_TRUTH, RESULTS
from orchestrator.evaluation.collect import collect_rows

_KOTLIN_KW = {
    "class", "fun", "val", "var", "if", "else", "when", "for", "while", "return",
    "data", "object", "interface", "override", "private", "public", "internal",
    "Composable", "ViewModel", "StateFlow", "MutableStateFlow", "collectAsStateWithLifecycle",
}


def _mask_strings(text: str) -> str:
    return re.sub(r'"(?:\\.|[^"\\])*"', '"STR"', text)


def _tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-z_][A-Za-z0-9_]*|[^\s]", _mask_strings(text))


def _ngrams(tokens: list[str], n: int) -> Counter:
    return Counter(tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1))


def bleu4(hyp: str, ref: str, eps: float = 1e-9) -> float:
    ht, rt = _tokens(hyp), _tokens(ref)
    if not ht or not rt:
        return 0.0
    precs = []
    for n in range(1, 5):
        hc, rc = _ngrams(ht, n), _ngrams(rt, n)
        overlap = sum(min(hc[g], rc[g]) for g in hc)
        precs.append((overlap + 1) / (max(sum(hc.values()), 1) + 1))
    bp = 1.0 if len(ht) >= len(rt) else math.exp(1 - len(rt) / max(len(ht), 1))
    return bp * math.exp(sum(math.log(p + eps) for p in precs) / 4)


def keyword_unigram(hyp: str, ref: str, weight: float = 5.0) -> float:
    ht, rt = _tokens(hyp), _tokens(ref)
    def weighted(ts):
        c = Counter()
        for t in ts:
            c[t] += weight if t in _KOTLIN_KW else 1.0
        return c
    hc, rc = weighted(ht), weighted(rt)
    overlap = sum(min(hc[k], rc[k]) for k in hc)
    return overlap / max(sum(hc.values()), 1)


def subtree_match(hyp: str, ref: str, depth: int = 3) -> float:
    try:
        import tree_sitter_kotlin as tskotlin
        from tree_sitter import Language, Parser
    except ImportError as exc:
        raise RuntimeError("tree-sitter-kotlin is required for code-similarity") from exc
    lang = Language(tskotlin.language())
    parser = Parser(lang)

    def collect(src: str) -> Counter:
        tree = parser.parse(bytes(src, "utf8"))
        counts: Counter = Counter()

        def walk(node, d, path):
            label = node.type
            np = path + (label,)
            if 1 <= len(np) <= depth:
                counts[np] += 1
            if d >= depth:
                return
            for i in range(node.child_count):
                walk(node.child(i), d + 1, np)

        walk(tree.root_node, 0, ())
        return counts

    hc, rc = collect(hyp), collect(ref)
    if not hc or not rc:
        return 0.0
    overlap = sum(min(hc[k], rc[k]) for k in hc)
    return overlap / max(sum(hc.values()), 1)


def codebleu_adapted(hyp: str, ref: str) -> float:
    return (bleu4(hyp, ref) + keyword_unigram(hyp, ref) + subtree_match(hyp, ref)) / 3


def run_code_similarity() -> Path:
    rows = [r for r in collect_rows() if r["scenario"] in ("s1", "s4", "b0")]
    out_rows = []
    for r in rows:
        ref = GROUND_TRUTH / "manual" / f"{r['screen_id']}.kt"
        if not ref.exists():
            continue
        src = Path(r["source"])
        data = src.read_text(encoding="utf-8")
        import json

        hyp = json.loads(data).get("code", "")
        if not hyp:
            continue
        out_rows.append(
            {
                "screen_id": r["screen_id"],
                "model": r["model"],
                "scenario": r["scenario"],
                "codebleu_adapted": codebleu_adapted(hyp, ref.read_text(encoding="utf-8")),
            }
        )
    dest = RESULTS / "tables" / "code_similarity.csv"
    dest.parent.mkdir(parents=True, exist_ok=True)
    import csv

    with dest.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["screen_id", "model", "scenario", "codebleu_adapted"])
        w.writeheader()
        w.writerows(out_rows)
    return dest
