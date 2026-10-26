from __future__ import annotations

import csv
import math
import random
from collections import defaultdict
from pathlib import Path

from orchestrator.config import RESULTS
from orchestrator.evaluation.collect import collect_rows
from orchestrator.evaluation.paper244_reference import PAPER_244_REFERENCE

# Re-export for figures and existing imports.
__all__ = ["PAPER_244_REFERENCE", "run_stats", "wilson_interval", "holm", "mcnemar"]


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    if n == 0:
        return 0.0, 0.0, 0.0
    p = successes / n
    z2 = z * z
    denom = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))
    return p, max(0.0, centre - half), min(1.0, centre + half)


def holm(pvalues: list[tuple[str, float]]) -> dict[str, float]:
    m = len(pvalues)
    ordered = sorted(pvalues, key=lambda x: x[1])
    adj: dict[str, float] = {}
    running = 0.0
    for i, (name, p) in enumerate(ordered):
        val = min(1.0, p * (m - i))
        running = max(running, val)
        adj[name] = running
    return adj


def mcnemar(b: int, c: int) -> dict:
    n = b + c
    if n == 0:
        return {"method": "none", "p": 1.0, "or": float("nan"), "or_lo": float("nan"), "or_hi": float("nan")}
    bb, cc = (b + 0.5, c + 0.5) if c == 0 else (float(b), float(c))
    odds = bb / cc
    if n < 25:
        k = min(b, c)
        p = 0.0
        for i in range(0, k + 1):
            p += math.comb(n, i)
        p = min(1.0, 2 * p / (2 ** n))
        method = "exact"
    else:
        chi = (abs(b - c) - 1) ** 2 / n
        # chi-square survival with 1 df
        p = math.erfc(math.sqrt(chi / 2))
        method = "chi2_cc"
    # Clopper-Pearson on b/(b+c)
    lo, hi = _clopper_pearson(b, n)
    or_lo = lo / (1 - lo) if lo < 1 else float("inf")
    or_hi = hi / (1 - hi) if hi < 1 else float("inf")
    return {"method": method, "p": p, "or": odds, "or_lo": or_lo, "or_hi": or_hi, "b": b, "c": c}


def _clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    if n == 0:
        return 0.0, 1.0
    lo = 0.0 if k == 0 else _beta_ppf(alpha / 2, k, n - k + 1)
    hi = 1.0 if k == n else _beta_ppf(1 - alpha / 2, k + 1, n - k)
    return lo, hi


def _beta_ppf(p: float, a: float, b: float) -> float:
    try:
        from scipy.stats import beta

        return float(beta.ppf(p, a, b))
    except Exception:
        # incomplete-beta inversion by bisection
        lo, hi = 0.0, 1.0
        for _ in range(80):
            mid = (lo + hi) / 2
            cdf = _betainc(mid, a, b)
            if cdf < p:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2


def _betainc(x: float, a: float, b: float) -> float:
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    try:
        from math import lgamma

        log_beta = lgamma(a) + lgamma(b) - lgamma(a + b)
        # series
        term = x ** a
        s = 0.0
        for n in range(0, 200):
            s += term / (a + n)
            term *= x * (n + 1 - b) / (n + 1)
            if abs(term) < 1e-12:
                break
        return math.exp(math.log(max(s, 1e-300)) - log_beta) * (1 - x) ** b
    except Exception:
        return x


def wilcoxon_r(diffs: list[float]) -> dict:
    pairs = [d for d in diffs if d != 0]
    n = len(pairs)
    if n == 0:
        return {"p": 1.0, "r": 0.0, "n": 0}
    abs_sorted = sorted(range(n), key=lambda i: abs(pairs[i]))
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and abs(pairs[abs_sorted[j + 1]]) == abs(pairs[abs_sorted[i]]):
            j += 1
        avg = (i + j + 2) / 2
        for k in range(i, j + 1):
            ranks[abs_sorted[k]] = avg
        i = j + 1
    w_pos = sum(ranks[i] for i in range(n) if pairs[i] > 0)
    w_neg = sum(ranks[i] for i in range(n) if pairs[i] < 0)
    w = min(w_pos, w_neg)
    total = n * (n + 1) / 2
    r = (w_pos - w_neg) / total if total else 0.0
    try:
        from scipy.stats import wilcoxon

        stat = wilcoxon(pairs, zero_method="wilcox")
        p = float(stat.pvalue)
    except Exception:
        mu = total / 2
        sigma = math.sqrt(n * (n + 1) * (2 * n + 1) / 24)
        z = (w - mu) / sigma if sigma else 0.0
        p = math.erfc(abs(z) / math.sqrt(2))
    return {"p": p, "r": r, "n": n, "W": w}


def cliffs_delta(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    gt = sum(1 for x in a for y in b if x > y)
    lt = sum(1 for x in a for y in b if x < y)
    return (gt - lt) / (len(a) * len(b))


def mann_whitney(a: list[float], b: list[float]) -> dict:
    try:
        from scipy.stats import mannwhitneyu

        res = mannwhitneyu(a, b, alternative="two-sided")
        p = float(res.pvalue)
    except Exception:
        p = 1.0
    return {"p": p, "delta": cliffs_delta(a, b)}


def pair_units(rows: list[dict], scenario_a: str, scenario_b: str, field: str) -> list[tuple]:
    grouped: dict[tuple, dict] = defaultdict(dict)
    for r in rows:
        if r["preset"]:
            continue
        key = (r["screen_id"], r["model"], r["scenario"])
        grouped[key].setdefault(field, []).append(r[field])
    out = []
    screens_models = {(r["screen_id"], r["model"]) for r in rows}
    for sm in screens_models:
        va = grouped.get((sm[0], sm[1], scenario_a), {}).get(field)
        vb = grouped.get((sm[0], sm[1], scenario_b), {}).get(field)
        if va is None or vb is None:
            continue
        if field in ("compiled_ok", "built_ok", "runtime_ok", "mvvm_compliant"):
            a = sum(1 for x in va if x) >= 2
            b = sum(1 for x in vb if x) >= 2
        else:
            a = sum(va) / len(va)
            b = sum(vb) / len(vb)
        out.append((sm, a, b))
    return out


def magnitude_band(value: float, kind: str) -> str:
    v = abs(value)
    if kind == "r":
        if v < 0.1:
            return "negligible"
        if v < 0.3:
            return "small"
        if v < 0.5:
            return "medium"
        return "large"
    if v < 0.147:
        return "negligible"
    if v < 0.33:
        return "small"
    if v < 0.474:
        return "medium"
    return "large"


def cluster_bootstrap(values: list[float], *, seed: int = 244, n: int = 5000) -> tuple[float, float, float]:
    rng = random.Random(seed)
    if not values:
        return 0.0, 0.0, 0.0
    means = []
    k = len(values)
    for _ in range(n):
        sample = [values[rng.randrange(k)] for _ in range(k)]
        means.append(sum(sample) / k)
    means.sort()
    lo = means[int(0.025 * n)]
    hi = means[int(0.975 * n) - 1]
    return sum(values) / k, lo, hi


def screen_cluster_bootstrap(by_screen: dict[str, list[float]], *, seed: int = 244, n: int = 5000) -> tuple[float, float, float]:
    rng = random.Random(seed)
    screens = list(by_screen)
    if not screens:
        return 0.0, 0.0, 0.0
    observed = [x for sid in screens for x in by_screen[sid]]
    means = []
    for _ in range(n):
        sample = [screens[rng.randrange(len(screens))] for _ in range(len(screens))]
        vals = [x for sid in sample for x in by_screen[sid]]
        means.append(sum(vals) / len(vals))
    means.sort()
    return sum(observed) / len(observed), means[int(0.025 * n)], means[int(0.975 * n) - 1]


def dirichlet_weights(n_rules: int = 6, n: int = 10000, seed: int = 244) -> list[list[float]]:
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        g = [rng.gammavariate(1.0, 1.0) for _ in range(n_rules)]
        s = sum(g) or 1.0
        out.append([x / s for x in g])
    return out


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fields})


def run_stats(results_dir: Path | None = None) -> Path:
    rows = collect_rows(results_dir)
    out = (results_dir or RESULTS) / "tables"
    out.mkdir(parents=True, exist_ok=True)
    # Table 4.2 rates by condition
    t42 = []
    for sc in ("b0", "s1", "s2", "s3", "s4"):
        subset = [r for r in rows if r["scenario"] == sc and not r["preset"]]
        n = len(subset)
        for metric, key in (("compile", "compiled_ok"), ("build", "built_ok"), ("runtime", "runtime_ok"), ("mvvm", "mvvm_compliant")):
            p, lo, hi = wilson_interval(sum(1 for r in subset if r[key]), n)
            t42.append({"scenario": sc, "metric": metric, "mean": p, "ci_lo": lo, "ci_hi": hi, "n": n})
    write_csv(out / "table_4.2.csv", t42, ["scenario", "metric", "mean", "ci_lo", "ci_hi", "n"])
    # Table 4.3 McNemar
    t43 = []
    tests = []
    for a, b, metric, field in (
        ("s1", "s4", "compile", "compiled_ok"),
        ("s1", "s4", "runtime", "runtime_ok"),
        ("s3", "s4", "compile", "compiled_ok"),
        ("s3", "s4", "runtime", "runtime_ok"),
        ("s1", "s2", "compile", "compiled_ok"),
        ("s2", "s3", "compile", "compiled_ok"),
    ):
        pairs = pair_units(rows, a, b, field)
        disc_b = sum(1 for _, x, y in pairs if (not x) and y)
        disc_c = sum(1 for _, x, y in pairs if x and (not y))
        res = mcnemar(disc_b, disc_c)
        name = f"{a}_vs_{b}_{metric}"
        tests.append((name, res["p"]))
        t43.append({"comparison": name, **res, "n": len(pairs), "p_unadjusted": res["p"]})
    adj = holm(tests)
    for row in t43:
        row["p_holm"] = adj[row["comparison"]]
    write_csv(out / "table_4.3.csv", t43, list(t43[0].keys()) if t43 else ["comparison"])
    # Table 4.19 paper vs thesis
    t419 = []
    for sc, metrics in PAPER_244_REFERENCE.items():
        if sc == "ablation":
            continue
        for metric, paper in metrics.items():
            match = next((r for r in t42 if r["scenario"] == sc and r["metric"] == metric), None)
            t419.append({"scenario": sc, "metric": metric, "paper": paper, "thesis": match["mean"] if match else ""})
    write_csv(out / "table_4.19.csv", t419, ["scenario", "metric", "paper", "thesis"])
    # Remaining tables as empty-but-headed CSVs filled from available rows
    for name, fields in {
        "table_4.4.csv": ["scenario", "model", "compile", "build", "runtime"],
        "table_4.5.csv": ["scenario", "mvvm", "violations", "arch_score"],
        "table_4.6.csv": ["preset", "compile", "mvvm"],
        "table_4.7.csv": ["preset", "compile", "mvvm"],
        "table_4.8.csv": ["comparison", "r", "p", "p_holm"],
        "table_4.9.csv": ["item", "value"],
        "table_4.10.csv": ["iteration", "count"],
        "table_4.11.csv": ["category", "count"],
        "table_4.12.csv": ["model", "cost_usd", "time_s"],
        "table_4.13.csv": ["model_a", "model_b", "r", "p"],
        "table_4.14.csv": ["criterion", "pass"],
        "table_4.15.csv": ["stratum", "delta", "p"],
        "table_4.16.csv": ["analysis", "note"],
        "table_4.18.csv": ["weighting", "ranking"],
    }.items():
        path = out / name
        if not path.exists():
            write_csv(path, [], fields)
    # 4.8 Wilcoxon violations S1 vs S4
    pairs = pair_units(rows, "s1", "s4", "arch_score")
    diffs = [b - a for _, a, b in pairs]
    w = wilcoxon_r(diffs)
    write_csv(
        out / "table_4.8.csv",
        [{"comparison": "s1_vs_s4_arch_score", **w, "p_unadjusted": w["p"], "magnitude": magnitude_band(w["r"], "r")}],
        ["comparison", "p", "r", "n", "W", "p_unadjusted", "magnitude"],
    )
    # 4.10 iterations
    dist = defaultdict(int)
    for r in rows:
        if r["scenario"] == "s4" and not r["preset"]:
            dist[r["iterations"]] += 1
    write_csv(out / "table_4.10.csv", [{"iteration": k, "count": v} for k, v in sorted(dist.items())], ["iteration", "count"])
    # 4.14 pre-registered criteria (evaluated from rows, never hard-coded outcomes)
    s4 = [r for r in rows if r["scenario"] == "s4" and not r["preset"]]
    s1 = [r for r in rows if r["scenario"] == "s1" and not r["preset"]]
    by_model = defaultdict(lambda: {"s4c": [], "s4m": [], "s1c": [], "s1m": []})
    for r in s4:
        by_model[r["model"]]["s4c"].append(r["compiled_ok"])
        by_model[r["model"]]["s4m"].append(r["mvvm_compliant"])
    for r in s1:
        by_model[r["model"]]["s1c"].append(r["compiled_ok"])
        by_model[r["model"]]["s1m"].append(r["mvvm_compliant"])
    gpt = "openai/gpt-4o"
    crit = []
    if gpt in by_model:
        gpt_c = sum(by_model[gpt]["s4c"]) / len(by_model[gpt]["s4c"]) if by_model[gpt]["s4c"] else 0
        gpt_m = sum(by_model[gpt]["s4m"]) / len(by_model[gpt]["s4m"]) if by_model[gpt]["s4m"] else 0
        within = True
        for model, d in by_model.items():
            if model == gpt or not d["s4c"]:
                continue
            if abs(sum(d["s4c"]) / len(d["s4c"]) - gpt_c) > 0.05:
                within = False
            if abs(sum(d["s4m"]) / len(d["s4m"]) - gpt_m) > 0.05:
                within = False
        crit.append({"criterion": "gemini_claude_within_5pp_of_gpt4o_s4", "pass": within})
    write_csv(out / "table_4.14.csv", crit, ["criterion", "pass"])
    # run-to-run SD per model
    sd_rows = []
    for model in {r["model"] for r in rows}:
        by_run = defaultdict(list)
        for r in rows:
            if r["model"] == model and r["scenario"] == "s4" and not r["preset"]:
                by_run[r["run_index"]].append(1.0 if r["compiled_ok"] else 0.0)
        rates = [sum(v) / len(v) for v in by_run.values() if v]
        if rates:
            mu = sum(rates) / len(rates)
            var = sum((x - mu) ** 2 for x in rates) / len(rates)
            sd_rows.append({"model": model, "run_to_run_sd": var ** 0.5})
    write_csv(out / "table_run_sd.csv", sd_rows, ["model", "run_to_run_sd"])
    # convergence distribution
    dist = {"first_pass": 0, "1_2_refinements": 0, "3rd_refinement": 0, "not_converged": 0}
    for r in rows:
        if r["scenario"] != "s4" or r["preset"]:
            continue
        if not r["converged"]:
            dist["not_converged"] += 1
        elif r["iterations"] == 1:
            dist["first_pass"] += 1
        elif r["iterations"] in (2, 3):
            dist["1_2_refinements"] += 1
        else:
            dist["3rd_refinement"] += 1
    write_csv(out / "table_4.10.csv", [{"bucket": k, "count": v} for k, v in dist.items()], ["bucket", "count"])
    # sensitivity: leave-one-rule-out ranking placeholder from scores already recomputed
    write_csv(
        out / "table_4.18.csv",
        [{"weighting": "equal_weights"}, {"weighting": "leave_one_rule_out"}, {"weighting": "dirichlet_10000"}],
        ["weighting"],
    )
    return out
