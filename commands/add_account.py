"""添加监控目标账号 - /addaccount 指令实现（plan-v3 §6.3）。"""

from __future__ import annotations

from astrbot.api.event import AstrMessageEvent

from ..core.crawler.fetcher import fetch_inventory_paginated
from ..core.crawler.parser import parse_inventory_response
from ..core.models.item import InventorySnapshot
from ..db.repository import get_user_by_steam_id, save_current_snapshot, upsert_user
from .validators import validate_steam_id


async def add_account(
    event: AstrMessageEvent,
    steam_id: str,
    nickname: str = "",
    plugin_instance=None,
):
    """添加监控目标的完整流程。

    1. 校验 steam_id 格式（17 位数字）
    2. 重复检测（含回收站：已软删则提示 /restoreaccount）
    3. fetch_inventory 预检（可达性/私密性；私密提示配置 steam_cookie）
    4. repository.upsert_user(steam_id, nickname, bound_umo=event.unified_msg_origin)
    5. save_current_snapshot() 建立基准
    6. yield 成功消息
    """
    # 1. 验证 Steam ID 格式
    is_valid, error_msg = validate_steam_id(steam_id)
    if not is_valid:
        yield event.plain_result(f"❌ {error_msg}")
        return

    steam_id = steam_id.strip()
    nickname = (nickname or "").strip()

    # 2. 检查是否已存在（含回收站）
    existing = await get_user_by_steam_id(steam_id)
    if existing:
        if existing.deleted_at:
            yield event.plain_result(
                f"⚠️ 该账号已在回收站中\n"
                f"使用 /restoreaccount {steam_id} 恢复监控"
            )
            return
        yield event.plain_result(
            f"⚠️ 该账号已经在监控列表中\n"
            f"当前昵称：{existing.nickname or '未设置'}\n"
            f"如需修改请使用 /nickname {steam_id} <新昵称>"
        )
        return

    # 3. 预检库存可达性
    yield event.plain_result(f"🔍 正在预检账号 {steam_id} 的库存可达性...")
    try:
        raw = await fetch_inventory_paginated(steam_id)
    except Exception as exc:
        yield event.plain_result(
            f"❌ 无法访问该账号库存\n"
            f"错误信息：{str(exc)[:100]}\n"
            f"请检查:\n"
            f"1. steam_id 是否正确\n"
            f"2. 库存隐私设置是否为公开\n"
            f"3. 如为私密库存，请在插件配置中设置 steam_cookie"
        )
        return

    if raw is None:
        yield event.plain_result(
            "❌ 无法获取该账号的库存数据\n"
            "可能原因：库存设置为私密或 API 访问受限\n"
            "解决方案：在插件配置中添加 steam_cookie（浏览器 F12 复制 steamLoginSecure）"
        )
        return

    # 4. 解析库存
    current_items = parse_inventory_response(raw)
    if current_items is None:
        yield event.plain_result("❌ 库存解析结果为空")
        return

    api_total = raw.get("total_inventory_count", len(current_items))

    # 5. 保存用户（绑定当前会话 unified_msg_origin）
    bound_umo = getattr(event, "unified_msg_origin", None)
    display_name = nickname or f"Steam_{steam_id[:8]}"
    await upsert_user(steam_id, display_name, bound_umo)

    # 6. 建立初始基准快照
    snapshot = InventorySnapshot(
        steam_id=steam_id,
        items=current_items,
        item_count=len(current_items),
        api_total_count=api_total,
    )
    await save_current_snapshot(snapshot)

    # 7. 成功消息
    yield event.plain_result(
        f"✅ 已成功添加监控目标!\n\n"
        f"👤 昵称：{display_name}\n"
        f"🆔 Steam ID: {steam_id}\n"
        f"📦 当前库存：{len(current_items)}件物品\n"
        f"🎯 API Total: {api_total}\n\n"
        f"💡 变化消息将推送到当前会话\n"
        f"提示：使用 /listaccounts 查看所有监控账号"
    )
