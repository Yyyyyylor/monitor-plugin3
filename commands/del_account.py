"""删除账号 - /delaccount 指令实现（plan-v3 §7.2，对应 Web DELETE /api/users）。

用法:
  /delaccount <steam_id>          # 软删除（进入回收站，数据保留）
  /delaccount <steam_id> --purge  # 永久删除（需管理员，不可恢复）
"""

from __future__ import annotations

from astrbot.api.event import AstrMessageEvent

from ..db.repository import (
    get_user_by_steam_id,
    permanent_delete_user,
    soft_delete_user,
)
from .validators import validate_steam_id


async def del_account(event: AstrMessageEvent, steam_id: str, plugin_instance=None):
    """软删除账号（进入回收站）；--purge 永久删除。"""
    if not steam_id:
        yield event.plain_result(
            "❌ 用法：/delaccount <steam_id> [--purge]\n"
            "不带 --purge 为软删除（可 /restoreaccount 恢复）\n"
            "--purge 永久删除（管理员）"
        )
        return

    # 解析 --purge 参数
    purge = False
    if steam_id.endswith("--purge"):
        purge = True
        steam_id = steam_id[:-7].strip()
    elif " --purge" in steam_id:
        parts = steam_id.split()
        steam_id = parts[0]
        purge = True

    is_valid, error_msg = validate_steam_id(steam_id)
    if not is_valid:
        yield event.plain_result(f"❌ {error_msg}")
        return

    user = await get_user_by_steam_id(steam_id)
    if not user:
        yield event.plain_result(f"❌ 未找到账号 `{steam_id}`")
        return

    display = user.nickname or f"Steam_{steam_id[:8]}"

    if purge:
        # 永久删除（不可恢复，仅管理员）
        if not event.is_admin():
            yield event.plain_result("❌ 永久删除需要管理员权限")
            return
        await permanent_delete_user(steam_id)
        yield event.plain_result(
            f"🗑️ 已永久删除账号\n\n"
            f"👤 {display}\n"
            f"🆔 {steam_id}\n\n"
            f"⚠️ 该账号的所有数据（快照/事件/归档）已不可恢复"
        )
        return

    # 软删除
    if user.deleted_at:
        yield event.plain_result(
            f"⚠️ 该账号已在回收站中\n"
            f"使用 /restoreaccount {steam_id} 恢复，或 /delaccount {steam_id} --purge 永久删除"
        )
        return

    if not await soft_delete_user(steam_id):
        yield event.plain_result("❌ 软删除失败")
        return

    yield event.plain_result(
        f"🗑️ 已将账号移入回收站\n\n"
        f"👤 {display}\n"
        f"🆔 {steam_id}\n\n"
        f"监控已停止，数据已保留\n"
        f"使用 /restoreaccount {steam_id} 恢复，或 /delaccount {steam_id} --purge 永久删除"
    )
