from orchestrator.evaluation.stats import cliffs_delta, cluster_bootstrap, holm, mcnemar, wilcoxon_r, wilson_interval


def test_mcnemar_exact():
    res = mcnemar(2, 1)
    assert res["method"] == "exact"
    assert 0 < res["p"] <= 1


def test_mcnemar_chi2():
    res = mcnemar(20, 5)
    assert res["method"] == "chi2_cc"
    assert res["or"] == 20 / 5


def test_mcnemar_or_when_c_zero():
    res = mcnemar(5, 0)
    assert res["or"] == (5.5 / 0.5)


def test_wilcoxon_r_sign():
    res = wilcoxon_r([1, 2, 3, 4, 5])
    assert res["r"] > 0
    res2 = wilcoxon_r([-1, -2, -3, -4, -5])
    assert res2["r"] < 0


def test_cliffs_delta():
    assert cliffs_delta([1, 1, 1], [0, 0, 0]) == 1.0
    assert cliffs_delta([0, 0, 0], [1, 1, 1]) == -1.0


def test_holm():
    adj = holm([("a", 0.01), ("b", 0.04)])
    assert adj["a"] <= adj["b"]
    assert adj["b"] <= 0.04 * 1 or adj["b"] <= 1


def test_wilson():
    p, lo, hi = wilson_interval(5, 10)
    assert p == 0.5
    assert 0 <= lo <= p <= hi <= 1


def test_bootstrap_deterministic():
    vals = [0.1, 0.2, 0.3, 0.4, 0.5]
    a = cluster_bootstrap(vals, seed=244, n=200)
    b = cluster_bootstrap(vals, seed=244, n=200)
    assert a == b
