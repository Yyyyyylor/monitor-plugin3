"""列出监控账号 - /listaccounts 指令实现（plan-v3 F6 / §7.2）。

对应 Web API GET /api/users；长列表渲染为图片（account_list.html）。
"""

from __future__ import annotations

from datetime import datetime

from astrbot.api.event import AstrMessageEvent

from ..core.config import settings
from ..db.repository import get_active_users, get_trash_users


def _freq_display(frequency: str) -> str:
    if settings.tiered_scheduling_enabled:
        interval_map = {
            "high": settings.tier_high_interval_minutes,
            "medium": settings.tier_medium_interval_minutes,
            "low": settings.tier_low_interval_minutes,
        }
        return f"高频({interval_map.get('high', 5)}m)/中频({interval_map.get('medium', 10)}m)/低频({interval_map.get('low', 20)}m)"
    return {"high": "高频", "medium": "中频", "low": "低频"}.get(frequency, frequency)


async def list_accounts(event: AstrMessageEvent, plugin_instance=None):
    """列出所有监控账号和回收站账号。"""
    from ..db.repository import load_current_snapshot

    active_users = await get_active_users()
    trash_users = await get_trash_users()

    if not active_users and not trash_users:
        yield event.plain_result(
            "📭 当前没有任何监控目标\n\n"
            "使用方法:\n"
            "/addaccount <steam_id> [昵称]\n"
            "示例:\n"
            "/addaccount 76561198000000000 小明"
        )
        return

    # 构建数据（含库存数/最后成功时间/失败计数）
    accounts = []
    for user in active_users:
        snapshot = await load_current_snapshot(user.steam_id)
        accounts.append({
            "steam_id": user.steam_id,
            "nickname": user.nickname or "未命名",
            "frequency": _freq_display(user.monitor_frequency),
            "item_count": snapshot.item_count if snapshot else 0,
            "consecutive_fails": user.consecutive_fails or 0,
            "last_error": (user.last_error_msg or "")[:50],
            "bound": "✅" if user.bound_umo else "—",
        })

    # 短列表直接文本
    text_lines = [f"📊 当前监控的账号（{len(active_users)} 个）\n"]
    for i, acc in enumerate(accounts, 1):
        fail_mark = f" ⚠️失败{acc['consecutive_fails']}次" if acc["consecutive_fails"] else ""
        text_lines.append(
            f"{i}. {acc['nickname']}{fail_mark}\n"
            f"   Steam ID: {acc['steam_id']}\n"
            f"   频率：{acc['frequency']} | 库存：{acc['item_count']}件 | 绑定：{acc['bound']}"
        )
    if trash_users:
        text_lines.append("")
        text_lines.append(f"🗑️ 回收站：{len(trash_users)} 个（/restoreaccount 查看）")

    full_text = "\n".join(text_lines)

    if len(full_text) <= 500 and not plugin_instance:
        yield event.plain_result(full_text)
        return

    # 长列表或可用渲染器时转图片（account_list.html）
    if plugin_instance is not None:
        try:
            data = {
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "active_count": len(active_users),
                "trash_count": len(trash_users),
                "accounts": accounts,
                "trash_accounts": [
                    {
                        "steam_id": u.steam_id,
                        "nickname": u.nickname or "未命名",
                    }
                    for u in trash_users
                ],
            }
            img_url = await plugin_instance.dispatcher.render_account_list(data)
            yield event.image_result(img_url)
            return
        except Exception as exc:
            yield event.plain_result(f"⚠️ 图片渲染失败，显示文本列表\n\n{full_text}")
            return

    # 文本截断保底
    if len(full_text) > 1500:
        full_text = full_text[:1500] + f"\n...(共 {len(full_text)} 字，请用 /listaccounts 在长列表模式下查看)"
    yield event.plain_result(full_text)
