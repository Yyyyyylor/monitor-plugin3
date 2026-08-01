"""修改监控账号昵称 - /nickname 指令实现（plan-v3 §7.1）。"""

from __future__ import annotations

from astrbot.api.event import AstrMessageEvent

from ..db.repository import get_user_by_steam_id, set_user_nickname
from .validators import validate_steam_id


async def nickname(event: AstrMessageEvent, steam_id: str, nickname: str = ""):
    """修改监控账号昵称。

    用法: /nickname <steam_id> <新昵称>
    """
    if not steam_id:
        yield event.plain_result("❌ 用法：/nickname <steam_id> <新昵称>")
        return

    if not nickname:
        yield event.plain_result("❌ 昵称不能为空\n用法：/nickname <steam_id> <新昵称>")
        return

    is_valid, error_msg = validate_steam_id(steam_id)
    if not is_valid:
        yield event.plain_result(f"❌ {error_msg}")
        return

    steam_id = steam_id.strip()
    nickname = nickname.strip()

    user = await get_user_by_steam_id(steam_id)
    if not user:
        yield event.plain_result(f"❌ 未找到账号 `{steam_id}`，请先使用 /addaccount 添加")
        return

    if user.deleted_at:
        yield event.plain_result(
            f"⚠️ 该账号已在回收站中\n请先用 /restoreaccount {steam_id} 恢复"
        )
        return

    if not await set_user_nickname(steam_id, nickname):
        yield event.plain_result("❌ 修改昵称失败")
        return

    yield event.plain_result(
        f"✅ 昵称已更新\n\n"
        f"🆔 Steam ID: {steam_id}\n"
        f"👤 新昵称：{nickname}"
    )
