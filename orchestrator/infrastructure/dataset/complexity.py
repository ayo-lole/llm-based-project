from __future__ import annotations

import xml.etree.ElementTree as ET

from orchestrator.config import COMPLEXITY_THRESHOLDS


def _local(tag: str) -> str:
    return tag.split("}")[-1].rsplit(".", 1)[-1]


def layout_metrics(xml: str) -> dict:
    root = ET.fromstring(xml)
    list_tags = set(COMPLEXITY_THRESHOLDS["list_tags"])
    widgets = 0
    max_depth = 0
    list_nodes = 0
    nested_lists = False
    dynamic = False

    def walk(el: ET.Element, depth: int, inside_list: bool) -> None:
        nonlocal widgets, max_depth, list_nodes, nested_lists, dynamic
        tag = _local(el.tag)
        if tag in {"data", "import", "variable", "requestFocus", "tag"}:
            return
        widgets += 1
        max_depth = max(max_depth, depth)
        is_list = tag in list_tags
        if is_list:
            list_nodes += 1
            if inside_list:
                nested_lists = True
        text = " ".join(el.attrib.values())
        if "@{" in text or tag in list_tags:
            dynamic = True
        for child in el:
            walk(child, depth + 1, inside_list or is_list)

    walk(root, 1, False)
    if list_nodes >= 2:
        nested_lists = True
    return {
        "depth": max_depth,
        "widgets": widgets,
        "nested_lists": nested_lists,
        "dynamic": dynamic,
    }


def classify_complexity(xml: str) -> str:
    m = layout_metrics(xml)
    t = COMPLEXITY_THRESHOLDS
    if m["nested_lists"] or m["depth"] >= t["complex_min_depth"] or m["widgets"] >= t["complex_min_widgets"]:
        return "complex"
    if m["depth"] <= t["simple_max_depth"] and m["widgets"] <= t["simple_max_widgets"] and not m["dynamic"]:
        return "simple"
    return "medium"
