"""停止/恢复所有监控 - /stopall /startall 指令实现（plan-v3 §7.1/§7.2）。

/stopall 对应 Web API POST /api/monitor/stop；/startall 对应 start。
"""

from __future__ import annotations


async def stop_all(plugin_instance):
    """停止所有监控任务和消息投递。

    Returns:
        结果消息字符串
    """
    if not plugin_instance:
        return "❌ 插件未正确初始化"

    # 标记为停止状态
    plugin_instance._monitor_enabled = False
    plugin_instance._message_enabled = False

    # 停止三个后台循环
    await plugin_instance.monitor_controller.stop()

    # 清空队列
    plugin_instance._queue.clear()

    return (
        "🛑 所有监控已停止\n\n"
        "⚠️ 已停止：\n"
        "- 监控后台任务（爬取/投递/维护）\n"
        "- 消息投递功能\n"
        "- 内存中的变化队列已清空\n\n"
        "💡 提示：使用 /startall 命令恢复所有服务"
    )


async def start_all(plugin_instance):
    """恢复所有监控任务和消息投递。

    Returns:
        结果消息字符串
    """
    if not plugin_instance:
        return "❌ 插件未正确初始化"

    # 标记为启动状态
    plugin_instance._monitor_enabled = True
    plugin_instance._message_enabled = True

    # 重新启动后台任务
    await plugin_instance.monitor_controller.start()

    return (
        "✅ 所有服务已恢复\n\n"
        "✨ 当前状态:\n"
        "- 监控任务：运行中\n"
        f"- 监控模式：{'分层' if plugin_instance.config.get('tiered_scheduling', {}).get('enabled') else '统一'}\n"
        "- 消息投递：启用\n\n"
        "提示：下次监控将在配置的时间间隔后自动开始"
    )
