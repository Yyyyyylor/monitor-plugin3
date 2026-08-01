"""调整消息投递间隔 - /messagegap 指令实现（plan-v3 §7.1）。

用法: /messagegap <minutes>（1-1440）；0 = 立即投递累积消息。
"""

from __future__ import annotations

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent


async def message_gap(event: AstrMessageEvent, minutes: str = "", plugin_instance=None):
    """调整消息投递间隔（minutes: 1-1440；0 立即投递）。"""
    try:
        interval = int(minutes)
    except (ValueError, TypeError):
        yield event.plain_result("❌ 请输入有效的数字作为时间间隔（分钟）")
        return

    if interval < 0 or interval > 1440:
        yield event.plain_result("❌ 无效的时间间隔，请输入 0-1440 之间的数字")
        return

    if interval == 0:
        # 立即投递累积消息
        from ..notifier.dispatcher import flush_immediately
        flushed = await flush_immediately()
        if flushed:
            yield event.plain_result(f"✅ 已立即投递 {flushed} 条累积消息")
        else:
            yield event.plain_result("📭 当前没有累积的消息可投递")
        return

    # 更新配置（运行时写回，AstrBot 持久化）
    if plugin_instance is not None:
        plugin_instance.config["message_interval_minutes"] = interval
        try:
            plugin_instance.config.save_config()
        except Exception:
            pass  # 部分环境不允许保存，仅内存生效
        logger.info("消息投递间隔已调整为：%d 分钟", interval)

    yield event.plain_result(
        f"✅ 消息投递间隔已设为 {interval} 分钟\n"
        f"💡 提示：输入 /messagegap 0 可立即投递当前累积的所有消息"
    )
