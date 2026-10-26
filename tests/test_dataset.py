import json

import pytest

from orchestrator.infrastructure.dataset.benchmark_freeze import freeze_benchmark
from orchestrator.infrastructure.dataset.ground_truth_select import QUOTA, select_ground_truth

NS = "xmlns:android='http://schemas.android.com/apk/res/android'"


def _xml(tier: str) -> str:
    if tier == "simple":
        return f"<LinearLayout {NS}><TextView android:text='a'/></LinearLayout>"
    if tier == "medium":
        inner = "".join(f"<TextView android:text='t{i}'/>" for i in range(20))
        return f"<LinearLayout {NS}>{inner}</LinearLayout>"
    lists = "<RecyclerView/><RecyclerView/>"
    deep = "<FrameLayout>" * 9 + lists + "</FrameLayout>" * 9
    return f"<LinearLayout {NS}>{deep}</LinearLayout>"


def _screen(root, sid, tier):
    d = root / "screens" / sid
    d.mkdir(parents=True)
    (d / "layout.xml").write_text(_xml(tier), encoding="utf-8")
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
    assert all("sha256" in x for x in a["screens"])
    with pytest.raises(FileExistsError):
        freeze_benchmark(dataset_root=tmp_path, quota=q, seed=244, overwrite=False)


def test_gt_quota(tmp_path):
    screens = []
    items = []
    for i in range(12):
        sid = f"s{i:02d}"
        _screen(tmp_path, sid, "simple")
        screens.append(sid)
        items.append({"id": sid, "complexity": "simple", "sha256": "x"})
    for i in range(16):
        sid = f"m{i:02d}"
        _screen(tmp_path, sid, "medium")
        screens.append(sid)
        items.append({"id": sid, "complexity": "medium", "sha256": "x"})
    for i in range(7):
        sid = f"c{i:02d}"
        _screen(tmp_path, sid, "complex")
        screens.append(sid)
        items.append({"id": sid, "complexity": "complex", "sha256": "x"})
    bench = tmp_path / "benchmark_150.json"
    bench.write_text(json.dumps({"screens": items}), encoding="utf-8")
    gt = tmp_path / "gt"
    out = select_ground_truth(bench, dataset_root=tmp_path, ground_truth_root=gt, seed=244)
    counts = {}
    for item in out["screens"]:
        counts[item["complexity"]] = counts.get(item["complexity"], 0) + 1
    assert counts == QUOTA
    again = select_ground_truth(bench, dataset_root=tmp_path, ground_truth_root=gt, seed=244)
    assert [x["screen_id"] for x in out["screens"]] == [x["screen_id"] for x in again["screens"]]
