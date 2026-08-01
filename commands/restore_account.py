"""回收站还原 - /restoreaccount 指令实现（plan-v3 §7.2）。

用法:
  /restoreaccount              # 列出回收站中的账号
  /restoreaccount <steam_id>   # 从回收站还原账号
"""

from __future__ import annotations

from astrbot.api.event import AstrMessageEvent

from ..db.repository import get_trash_users, restore_user
from .validators import validate_steam_id


async def restore_account(event: AstrMessageEvent, steam_id: str = ""):
    """从回收站还原账号；不带参数列出回收站。"""
    # 不带参数：列出回收站
    if not steam_id:
        trash = await get_trash_users()
        if not trash:
            yield event.plain_result("🗑️ 回收站是空的")
            return
        lines = [f"🗑️ 回收站中的账号（{len(trash)} 个）:\n"]
        for i, user in enumerate(trash, 1):
            lines.append(f"{i}. {user.nickname or '未命名'} — {user.steam_id}")
        lines.append("")
        lines.append("使用 /restoreaccount <steam_id> 还原")
        yield event.plain_result("\n".join(lines))
        return

    is_valid, error_msg = validate_steam_id(steam_id)
    if not is_valid:
        yield event.plain_result(f"❌ {error_msg}")
        return

    steam_id = steam_id.strip()
    if not await restore_user(steam_id):
        yield event.plain_result(f"❌ 未找到回收站中的账号 `{steam_id}`")
        return

    yield event.plain_result(
        f"✅ 已从回收站还原账号\n\n"
        f"🆔 {steam_id}\n\n"
        f"监控将在下一轮自动恢复"
    )
