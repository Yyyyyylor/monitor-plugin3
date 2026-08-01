"""历史快照对比 - /compare 指令实现（plan-v3 F9，对应 Web /api/users/{id}/compare）。

用法: /compare <steam_id> <date1> [date2]
  date 格式: YYYY-MM-DD；date2 缺省为当前日期（当前库存）。
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime

from astrbot.api.event import AstrMessageEvent

from ..db.repository import get_archives_by_date, load_archive_items
from .validators import validate_steam_id


def _parse_date(raw: str) -> date | None:
    """解析 YYYY-MM-DD 日期。"""
    try:
        return datetime.strptime(raw.strip(), "%Y-%m-%d").date()
    except (ValueError, AttributeError):
        return None


async def compare(event: AstrMessageEvent, steam_id: str, date1: str, date2: str, plugin_instance=None):
    """对比两个日期的归档快照，生成差异图片报告。"""
    # 1. 参数校验
    is_valid, error_msg = validate_steam_id(steam_id)
    if not is_valid:
        yield event.plain_result(f"❌ {error_msg}")
        return

    d1 = _parse_date(date1)
    if d1 is None:
        yield event.plain_result("❌ 日期格式错误，请使用 YYYY-MM-DD\n例如：/compare 76561198000000000 2026-07-01")
        return

    d2 = _parse_date(date2) if date2 else date.today()
    if date2 and d2 is None:
        yield event.plain_result("❌ 日期格式错误，请使用 YYYY-MM-DD\n例如：/compare 76561198000000000 2026-07-01 2026-07-31")
        return

    # 2. 获取归档快照
    archive_a = await get_archives_by_date(steam_id, d1)
    if archive_a is None:
        yield event.plain_result(f"❌ 未找到 {d1} 的快照归档\n（归档每日维护时自动生成，可先用 /addaccount 建立基准）")
        return

    items_a = await load_archive_items(archive_a)

    if d2 == date.today():
        # date2 缺省：对比当前库存
        from ..db.repository import load_current_snapshot
        current = await load_current_snapshot(steam_id)
        if current is None:
            yield event.plain_result("❌ 未找到当前库存快照，请先 /crap 触发一轮爬取")
            return
        items_b = current.items
        date_b_label = f"{d2}（当前库存）"
        archive_b_captured = current.captured_at
    else:
        archive_b = await get_archives_by_date(steam_id, d2)
        if archive_b is None:
            yield event.plain_result(f"❌ 未找到 {d2} 的快照归档")
            return
        items_b = await load_archive_items(archive_b)
        date_b_label = str(d2)
        archive_b_captured = archive_b.captured_at

    # 3. 按饰品名统计数量差异
    names_a = Counter(i.market_hash_name for i in items_a.values())
    names_b = Counter(i.market_hash_name for i in items_b.values())

    diff = []
    for name in sorted(set(names_a) | set(names_b)):
        ca = names_a.get(name, 0)
        cb = names_b.get(name, 0)
        if ca != cb:
            diff.append({
                "name": name,
                "count_a": ca,
                "count_b": cb,
                "delta": cb - ca,
            })
    diff.sort(key=lambda x: abs(x["delta"]), reverse=True)

    # 4. 渲染图片报告
    data = {
        "steam_id": steam_id,
        "date_a": d1.isoformat(),
        "date_b": date_b_label,
        "count_a": len(items_a),
        "count_b": len(items_b),
        "diff_count": len(diff),
        "diff": diff[:80],  # 最多展示 80 条
        "truncated": len(diff) > 80,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    if plugin_instance is not None:
        try:
            img_url = await plugin_instance.dispatcher.render_compare_report(data)
            yield event.image_result(img_url)
            return
        except Exception as exc:
            yield event.plain_result(f"⚠️ 报告渲染失败，显示文本：{str(exc)[:80]}")

    # 文本兜底
    lines = [
        f"📊 快照对比: {steam_id}",
        f"📅 {d1} ({len(items_a)}件) → {date_b_label} ({len(items_b)}件)",
        f"差异: {len(diff)} 种物品",
        "",
    ]
    for d in diff[:20]:
        arrow = "+" if d["delta"] > 0 else "-"
        lines.append(f"{arrow} {d['name']}: {d['count_a']} → {d['count_b']}")
    if len(diff) > 20:
        lines.append(f"... 共 {len(diff)} 种差异")
    yield event.plain_result("\n".join(lines))
