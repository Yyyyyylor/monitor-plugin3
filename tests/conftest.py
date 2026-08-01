"""测试共用夹具。"""

from __future__ import annotations

from typing import Any

import pytest

import sys
import types
from pathlib import Path

# 以 metadata name（monitor_plugin3）注册插件根为包——模拟 AstrBot 的
# data.plugins.monitor_plugin3 加载方式（目录名含连字符，无法直接作为包名）。
# 这样插件内部的相对导入（from ..core.xxx）在测试中同样成立。
_PLUGIN_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PLUGIN_ROOT))

# astrbot API 桩（无 AstrBot 环境时提供最小 API 表面）
_FAKE_ASTRBOT = Path(__file__).resolve().parent / "fake_astrbot"
sys.path.insert(0, str(_FAKE_ASTRBOT))

_pkg = types.ModuleType("monitor_plugin3")
_pkg.__path__ = [str(_PLUGIN_ROOT)]  # type: ignore[attr-defined]
sys.modules["monitor_plugin3"] = _pkg

from monitor_plugin3.core.models.item import Item


@pytest.fixture
def sample_item_data() -> dict[str, Any]:
    return {
        "asset_id": "123456789",
        "classid": "123",
        "instanceid": "456",
        "market_hash_name": "AK-47 | Redline (Field-Tested)",
        "market_name": "AK-47 | Redline (Field-Tested)",
        "icon_url": "-9a81dlWLwJ2UGlfD6e2...",
        "rarity": "Classified",
        "type_line": "Rifle",
        "tradable": True,
        "marketable": True,
        "attributes": {
            "paint_wear": 0.15,
            "paint_seed": 588,
            "stattrak_count": 42,
        },
        "tags": [],
    }


@pytest.fixture
def sample_item(sample_item_data) -> Item:
    return Item.from_dict(sample_item_data)


@pytest.fixture
def mock_raw_inventory() -> dict[str, Any]:
    """模拟 Steam API 返回的单页库存。"""
    return {
        "success": True,
        "assets": [
            {
                "appid": 730,
                "contextid": "2",
                "assetid": "1001",
                "classid": "100",
                "instanceid": "200",
                "amount": "1",
            },
            {
                "appid": 730,
                "contextid": "2",
                "assetid": "1002",
                "classid": "101",
                "instanceid": "201",
                "amount": "1",
            },
            {
                "appid": 730,
                "contextid": "2",
                "assetid": "1003",
                "classid": "102",
                "instanceid": "202",
                "amount": "1",
            },
        ],
        "descriptions": [
            {
                "classid": "100",
                "instanceid": "200",
                "market_hash_name": "AK-47 | Redline (Field-Tested)",
                "market_name": "AK-47 | Redline (Field-Tested)",
                "tradable": True,
                "marketable": True,
                "descriptions": [
                    {"value": "Wear Rating: 0.15"},
                    {"value": "Paint Seed: 588"},
                ],
                "tags": [
                    {"category": "Rarity", "name": "Classified", "localized_tag_name": "Classified"},
                ],
            },
            {
                "classid": "101",
                "instanceid": "201",
                "market_hash_name": "Desert Eagle | Blaze",
                "market_name": "Desert Eagle | Blaze",
                "tradable": True,
                "marketable": True,
                "descriptions": [],
                "tags": [],
            },
            {
                "classid": "102",
                "instanceid": "202",
                "market_hash_name": "AWP | Asiimov (Field-Tested)",
                "market_name": "AWP | Asiimov (Field-Tested)",
                "tradable": True,
                "marketable": True,
                "descriptions": [
                    {
                        "value": "Sticker: Sticker | iBUYPOWER (Holo) | Katowice 2014",
                        "app_data": {
                            "info": [
                                {"sticker_id": "12345", "slot": "0", "wear": "0.1", "name": "iBUYPOWER (Holo) | Katowice 2014"},
                            ],
                        },
                    },
                ],
                "tags": [
                    {"category": "Rarity", "name": "Covert", "localized_tag_name": "Covert"},
                ],
            },
        ],
        "total_inventory_count": 3,
        "success": 1,
        "more": False,
    }
