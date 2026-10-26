import json

import pytest

from orchestrator.infrastructure.dataset.benchmark_freeze import freeze_benchmark
from orchestrator.infrastructure.dataset.ground_truth_select import QUOTA, select_ground_truth


def _screen(root, sid, tier):
    d = root / "screens" / sid
    d.mkdir(parents=True)
    (d / "layout.xml").write_text("<LinearLayout xmlns:android='http://schemas.android.com/apk/res/android'/>", encoding="utf-8")
    (d / "ViewModel.kt").write_text("class XViewModel", encoding="utf-8")
    (d / "meta.json").write_text(json.dumps({"layout": "layout.xml", "complexity": tier, "repo": "a/b"}), encoding="utf-8")


def test_freeze_reproducible_and_refuse(tmp_path):
    for i in range(5):
        _screen(tmp_path, f"s{i}", "simple")
    for i in range(5):
        _screen(tmp_path, f"m{i}", "medium")
    for i in range(3):
        _screen(tmp_path, f"c{i}", "complex")
    q = {"simple": 2, "medium": 2, "complex": 1}
    a = freeze_benchmark(dataset_root=tmp_path, quota=q, seed=244)
    b = freeze_benchmark(dataset_root=tmp_path, quota=q, seed=244, overwrite=True)
    assert a["screens"] == b["screens"]
    with pytest.raises(FileExistsError):
        freeze_benchmark(dataset_root=tmp_path, quota=q, seed=244, overwrite=False)


def test_gt_quota(tmp_path):
    screens = []
    for i in range(12):
        sid = f"s{i:02d}"
        _screen(tmp_path, sid, "simple")
        screens.append(sid)
    for i in range(16):
        sid = f"m{i:02d}"
        _screen(tmp_path, sid, "medium")
        screens.append(sid)
    for i in range(7):
        sid = f"c{i:02d}"
        _screen(tmp_path, sid, "complex")
        screens.append(sid)
    bench = tmp_path / "benchmark_150.json"
    bench.write_text(json.dumps({"screens": screens}), encoding="utf-8")
    gt = tmp_path / "gt"
    out = select_ground_truth(bench, dataset_root=tmp_path, ground_truth_root=gt, seed=244)
    counts = {}
    for item in out["screens"]:
        counts[item["complexity"]] = counts.get(item["complexity"], 0) + 1
    assert counts == QUOTA
    again = select_ground_truth(bench, dataset_root=tmp_path, ground_truth_root=gt, seed=244)
    assert [x["screen_id"] for x in out["screens"]] == [x["screen_id"] for x in again["screens"]]
