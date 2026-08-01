"""/getinventory 指令测试 — 参数解析与库存聚合逻辑（不依赖网络）。"""

from __future__ import annotations

from monitor_plugin3.commands.get_inventory import MAX_GROUPS_IN_REPORT, _build_groups
from monitor_plugin3.core.models.item import Item


def _item(aid: str, name: str) -> Item:
    return Item(asset_id=aid, classid="1", instanceid="1", market_hash_name=name)


def test_build_groups_aggregates_and_sorts():
    """相同饰品聚合计数，按数量降序。"""
    items = {
        "a1": _item("a1", "AK-47 | Redline"),
        "a2": _item("a2", "AWP | Asiimov"),
        "a3": _item("a3", "AK-47 | Redline"),
        "a4": _item("a4", "AWP | Asiimov"),
        "a5": _item("a5", "AWP | Asiimov"),
    }
    groups, total, truncated = _build_groups(items)
    assert total == 5
    assert truncated is False
    # 按数量降序：AWP ×3 在前
    assert groups[0]["original"] == "AWP | Asiimov"
    assert groups[0]["count"] == 3
    assert groups[1]["original"] == "AK-47 | Redline"
    assert groups[1]["count"] == 2
    # 名称已汉化（翻译表收录项）
    assert groups[0]["name"] != "AWP | Asiimov"


def test_build_groups_truncation():
    """超过上限截断并标记。"""
    items = {f"a{i}": _item(f"a{i}", f"Item {i}") for i in range(MAX_GROUPS_IN_REPORT + 50)}
    groups, total, truncated = _build_groups(items)
    assert total == MAX_GROUPS_IN_REPORT + 50
    assert truncated is True
    assert len(groups) == MAX_GROUPS_IN_REPORT


def test_build_groups_empty():
    """空库存。"""
    groups, total, truncated = _build_groups({})
    assert total == 0
    assert groups == []
    assert truncated is False


def test_steam_id_vs_nickname_detection():
    """参数识别：17 位数字是 Steam ID，否则为昵称。"""
    from monitor_plugin3.commands.validators import validate_steam_id

    ok, _ = validate_steam_id("76561199366136578")
    assert ok
    ok, _ = validate_steam_id("76561198000000000")
    assert ok
    ok, _ = validate_steam_id("小明")
    assert not ok
    ok, _ = validate_steam_id("7656119800000000")  # 16 位
    assert not ok
