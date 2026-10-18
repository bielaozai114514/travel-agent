"""景点工具层。

当前实现读取本地景点库（字段与高德 POI 对齐），后续可替换为
高德 MCP / 官方 POI 接口而不影响上层 Agent —— 上层只依赖
`search()` 与 `group_by_area()` 两个语义化方法。
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Iterable

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "attractions.json"

# 人群 -> 偏好景点类型（用于规则引擎排序）
PEOPLE_TYPE_WEIGHT: dict[str, dict[str, float]] = {
    "亲子": {"亲子": 1.4, "自然": 1.1, "人文": 1.0, "演艺": 1.2, "美食": 1.0, "商圈": 0.9},
    "老年": {"人文": 1.3, "自然": 1.2, "亲子": 0.9, "美食": 1.0, "演艺": 0.8, "商圈": 0.8},
    "情侣": {"自然": 1.3, "演艺": 1.2, "美食": 1.2, "人文": 1.0, "商圈": 1.0, "亲子": 0.8},
    "商务": {"商圈": 1.3, "人文": 1.2, "美食": 1.0, "自然": 0.9, "亲子": 0.7, "演艺": 0.8},
    "独自": {"人文": 1.3, "自然": 1.2, "美食": 1.1, "商圈": 1.0, "亲子": 0.7, "演艺": 0.9},
}


@lru_cache(maxsize=1)
def load_all() -> list[dict]:
    with DATA_PATH.open(encoding="utf-8") as f:
        payload = json.load(f)
    return payload["attractions"]


def list_cities() -> list[str]:
    return sorted({a["city"] for a in load_all()})


def search(
    city: str,
    people: str = "独自",
    *,
    exclude: Iterable[str] = (),
    limit: int | None = None,
) -> list[dict]:
    """按城市 + 人群召回候选景点，按适配度排序。"""
    exclude_set = set(exclude)
    weights = PEOPLE_TYPE_WEIGHT.get(people, PEOPLE_TYPE_WEIGHT["独自"])
    candidates = [
        a
        for a in load_all()
        if a["city"] == city and a["id"] not in exclude_set and people in a["tags"]
    ]
    candidates.sort(
        key=lambda a: weights.get(a["type"], 1.0) * a["rating"],
        reverse=True,
    )
    return candidates[:limit] if limit else candidates


def group_by_area(spots: Iterable[dict]) -> dict[str, list[dict]]:
    """按片区聚类，用于把同一天的景点排在同一片区域，减少通勤。"""
    grouped: dict[str, list[dict]] = {}
    for spot in spots:
        grouped.setdefault(spot["area"], []).append(spot)
    for items in grouped.values():
        items.sort(key=lambda s: s["duration_h"], reverse=True)
    return grouped


def get_by_id(spot_id: str) -> dict | None:
    return next((a for a in load_all() if a["id"] == spot_id), None)
