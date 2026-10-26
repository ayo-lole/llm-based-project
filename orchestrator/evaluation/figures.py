from __future__ import annotations

from collections import defaultdict

from orchestrator.config import ROOT
from orchestrator.evaluation.collect import collect_rows
from orchestrator.evaluation.stats import PAPER_244_REFERENCE


def run_figures():
    import matplotlib.pyplot as plt

    dest = ROOT / "outputs" / "figures"
    dest.mkdir(parents=True, exist_ok=True)
    rows = collect_rows()
    scenarios = ["b0", "s1", "s2", "s3", "s4"]
    x = list(range(len(scenarios)))

    def rate(sc, field):
        subset = [r for r in rows if r["scenario"] == sc and not r["preset"]]
        if not subset:
            return float("nan")
        return sum(1 for r in subset if r[field]) / len(subset)

    def save(name: str):
        plt.tight_layout()
        plt.savefig(dest / f"{name}.png", dpi=150)
        plt.savefig(dest / f"{name}.svg")
        plt.close()

    paper_c = [PAPER_244_REFERENCE[s]["compile"] for s in scenarios]
    thesis_c = [rate(s, "compiled_ok") for s in scenarios]
    plt.figure()
    plt.plot(x, paper_c, marker="o", label="Paper 244")
    plt.plot(x, thesis_c, marker="s", label="Thesis")
    plt.xticks(x, scenarios)
    plt.ylabel("Compilation rate")
    plt.legend()
    save("figure_4.1")

    paper_m = [PAPER_244_REFERENCE[s]["mvvm"] for s in scenarios]
    thesis_m = [rate(s, "mvvm_compliant") for s in scenarios]
    plt.figure()
    plt.plot(x, paper_m, marker="o", label="Paper 244")
    plt.plot(x, thesis_m, marker="s", label="Thesis")
    plt.xticks(x, scenarios)
    plt.ylabel("MVVM compliance")
    plt.legend()
    save("figure_4.2")

    presets = ["no_feedback_loop", "no_arch_constraint", "no_static_analysis"]
    compile_ab = []
    mvvm_ab = []
    for p in presets:
        subset = [r for r in rows if r["preset"] == p]
        compile_ab.append(sum(1 for r in subset if r["compiled_ok"]) / len(subset) if subset else float("nan"))
        mvvm_ab.append(sum(1 for r in subset if r["mvvm_compliant"]) / len(subset) if subset else float("nan"))
    plt.figure()
    plt.plot(presets, compile_ab, marker="o", label="compile")
    plt.plot(presets, mvvm_ab, marker="s", label="mvvm")
    plt.legend()
    save("figure_4.3")

    cats = defaultdict(int)
    for r in rows:
        if r["scenario"] == "s4" and not r["preset"]:
            for k, v in (r.get("error_types") or {}).items():
                cats[k] += int(v or 0)
    plt.figure()
    if cats:
        plt.bar(list(cats.keys()), list(cats.values()))
        plt.xticks(rotation=30, ha="right")
    save("figure_4.4")

    plt.figure()
    plt.plot(x, paper_c, marker="o", label="Paper 244 compile")
    plt.plot(x, thesis_c, marker="s", label="Thesis compile")
    plt.xticks(x, scenarios)
    plt.legend()
    save("figure_4.5")
    return dest
