"""调整监控频率 - /editgap 指令实现（plan-v3 F7）。"""

from __future__ import annotations

from astrbot.api.event import AstrMessageEvent

from ..core.config import settings
from ..db.repository import get_user_by_steam_id, set_user_frequency
from .validators import validate_frequency, validate_steam_id


def _interval_display(frequency: str) -> str:
    """频率层级 → 显示文案（从配置读取，默认 5/10/20 分钟）。"""
    if settings.tiered_scheduling_enabled:
        interval_map = {
            "high": settings.tier_high_interval_minutes,
            "medium": settings.tier_medium_interval_minutes,
            "low": settings.tier_low_interval_minutes,
        }
        return f"{interval_map.get(frequency, '?')} 分钟"
    return {
        "high": "5 分钟",
        "medium": "10 分钟",
        "low": "20 分钟",
    }.get(frequency, frequency)


async def edit_gap(event: AstrMessageEvent, steam_id: str, frequency: str):
    """调整指定账号的监控频率。

    用法: /editgap <steam_id> <high|medium|low>
    """
    # 验证参数
    is_valid, error_msg = validate_steam_id(steam_id)
    if not is_valid:
        yield event.plain_result(f"❌ {error_msg}")
        return

    is_valid, error_msg = validate_frequency(frequency.lower())
    if not is_valid:
        yield event.plain_result(f"❌ {error_msg}")
        return

    steam_id = steam_id.strip()
    frequency = frequency.lower()

    # 查询用户
    user = await get_user_by_steam_id(steam_id)
    if not user:
        yield event.plain_result(f"❌ 未找到账号 `{steam_id}`，请先使用 /addaccount 添加")
        return

    if user.deleted_at:
        yield event.plain_result(
            f"⚠️ 该账号已在回收站中\n"
            f"请先用 /restoreaccount {steam_id} 恢复"
        )
        return

    # 更新频率
    old_frequency = user.monitor_frequency
    if not await set_user_frequency(steam_id, frequency):
        yield event.plain_result("❌ 更新频率失败")
        return

    yield event.plain_result(
        f"✅ 已调整监控频率!\n\n"
        f"👤 账号：{user.nickname or steam_id[:8]}\n"
        f"🆔 Steam ID: `{steam_id}`\n\n"
        f"📅 旧频率：{_interval_display(old_frequency)}\n"
        f"🎯 新频率：{_interval_display(frequency)}\n\n"
        f"💡 下次生效时间将在当前周期结束后"
    )
