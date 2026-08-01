"""事件格式化模块 — 将变化事件转换为中文文本与报告数据。

保留 monitor/src/notifications/user_notifier.py 的格式化语义
（plan-v3 §5.4）：ADDED 含磨损、MODIFIED 含属性差异、SWAPPED 含新旧
asset_id，文案走 localize 汉化。
"""

from __future__ import annotations

import html as _html
from datetime import datetime
from typing import Any

from ..core.crawler.localize import translate_name
from ..core.models.item import ChangeEvent, ChangeType


def _extract_item_name(event: ChangeEvent) -> str:
    """从变化事件详情中提取物品名称（返回原文，适配不同事件类型的嵌套结构）。"""
    # SWAPPED: market_hash_name 在顶层
    if "market_hash_name" in event.detail:
        raw = event.detail["market_hash_name"]
    # MODIFIED: market_hash_name 在 current_state 里
    elif "current_state" in event.detail:
        raw = event.detail["current_state"].get("market_hash_name", "Unknown Item")
    # ADDED / REMOVED: market_hash_name 在 item 里
    elif "item" in event.detail:
        raw = event.detail["item"].get("market_hash_name", "Unknown Item")
    else:
        raw = "Unknown Item"
    return raw


def _display_name(event: ChangeEvent) -> str:
    """显示名称（原文按 translation_map 汉化，未收录项保留原文，AC11）。"""
    raw = _extract_item_name(event)
    return translate_name(raw) or raw


def format_event_text(event: ChangeEvent) -> str:
    """根据变化类型格式化单个事件的中文文本。"""
    name = _display_name(event)

    if event.change_type == ChangeType.ADDED:
        item = event.detail.get("item", {})
        wear = item.get("attributes", {}).get("paint_wear")
        wear_str = f" (磨损 {wear:.4f})" if wear is not None else ""
        return f"✅ 新增: {name}{wear_str}"
    elif event.change_type == ChangeType.REMOVED:
        return f"❌ 移除: {name}"
    elif event.change_type == ChangeType.MODIFIED:
        changes = event.detail.get("changes", {})
        parts = [f"{k}: {v[0]} → {v[1]}" for k, v in changes.items()]
        text = f"📝 修改: {name}"
        if parts:
            text += "\n  " + "\n  ".join(parts)
        return text
    elif event.change_type == ChangeType.SWAPPED:
        attr_diffs = event.detail.get("attribute_diffs", {})
        parts = [f"{k}: {v[0]} → {v[1]}" for k, v in attr_diffs.items()]
        base = (
            f"🔄 交换: {name}\n"
            f"  旧 asset_id: {event.old_asset_id}\n"
            f"  新 asset_id: {event.asset_id}"
        )
        if parts:
            base += "\n  " + "\n  ".join(parts)
        return base
    return f"❓ 未知变化: {name} ({event.change_type.value})"


def build_report(steam_id: str, events: list[ChangeEvent], activity: Any) -> dict[str, Any]:
    """生成完整的报告数据（文本与 HTML 模板共用）。"""
    added = sum(1 for e in events if e.change_type == ChangeType.ADDED)
    removed = sum(1 for e in events if e.change_type == ChangeType.REMOVED)
    modified = sum(1 for e in events if e.change_type == ChangeType.MODIFIED)
    swapped = sum(1 for e in events if e.change_type == ChangeType.SWAPPED)

    summary_parts = ["检测到库存变动"]
    if added:
        summary_parts.append(f"新增{added}")
    if removed:
        summary_parts.append(f"移除{removed}")
    if modified:
        summary_parts.append(f"修改{modified}")
    if swapped:
        summary_parts.append(f"交换{swapped}")
    summary = "，".join(summary_parts) + f"，共{len(events)}次变化"

    details = []
    for event in events:
        details.append({
            "type": event.change_type.value,
            "text": format_event_text(event),
            "name": _extract_item_name(event),
            "asset_id": event.asset_id,
        })

    activity_summary = ""
    if activity is not None and activity.category != "unchanged":
        activity_summary = activity.summary_line()

    return {
        "steam_id": steam_id,
        "summary": summary,
        "details": details,
        "activity_summary": activity_summary,
        "stats": {
            "added": added,
            "removed": removed,
            "modified": modified,
            "swapped": swapped,
            "total": len(events),
        },
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        # 纯文本消息（≤150 字时直接投递）
        "text_message": _build_text_message(summary, activity_summary, details),
    }


def _build_text_message(summary: str, activity_summary: str, details: list[dict]) -> str:
    """生成纯文本消息。"""
    lines = [summary]
    if activity_summary:
        lines.append("")
        lines.append(f"━━━ {activity_summary} ━━━")
    lines.append("")
    for d in details:
        lines.append(d["text"])
    return "\n".join(lines)
