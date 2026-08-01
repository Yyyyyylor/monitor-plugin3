"""暂停/恢复消息投递 - /stopmessage 指令实现（plan-v3 §7.1 F8）。"""

from __future__ import annotations

from astrbot.api.event import AstrMessageEvent


async def stop_message(event: AstrMessageEvent, action: str = "", plugin_instance=None):
    """暂停或恢复消息投递（监控不停）。

    用法: /stopmessage [on|off]；省略参数则切换状态
    """
    if not plugin_instance:
        yield event.plain_result("❌ 插件未正确初始化")
        return

    action = (action or "").strip().lower()

    # 确定动作
    if action == "on":
        plugin_instance._message_enabled = True
        yield event.plain_result(
            "📣 消息投递已恢复\n\n"
            "当前所有监控任务将继续运行，变化消息会正常推送到您的会话"
        )
    elif action == "off":
        plugin_instance._message_enabled = False
        yield event.plain_result(
            "📵 消息投递已暂停\n\n"
            "⚠️ 监控任务仍在运行，但不会发送变化通知（消息在队列中累积）\n"
            "提示：使用 /stopmessage on 或 /stopmessage 恢复投递"
        )
    else:
        # 切换状态
        plugin_instance._message_enabled = not plugin_instance._message_enabled
        if plugin_instance._message_enabled:
            yield event.plain_result(
                "✅ 消息投递已恢复\n\n"
                "变化通知将正常发送到您的会话"
            )
        else:
            yield event.plain_result(
                "📵 消息投递已暂停\n\n"
                "监控任务仍在运行，但不会推送消息\n"
                "使用 /stopmessage on 恢复"
            )
