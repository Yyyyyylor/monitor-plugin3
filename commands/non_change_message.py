"""控制"无变化"通知 - /non-change-message 指令实现。

用法:
  /non-change-message true     # 开启：监控周期内所有账号均无变化时发送"无变化"通知
  /non-change-message false    # 关闭
  /non-change-message          # 查询当前状态
"""

from __future__ import annotations

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent


async def non_change_message(event: AstrMessageEvent, arg: str = "", plugin_instance=None):
    """控制监控周期"无变化"通知的开关。"""
    if plugin_instance is None:
        yield event.plain_result("❌ 插件未正确初始化")
        return

    arg = (arg or "").strip().lower()

    if arg == "true":
        plugin_instance.config["non_change_message"] = True
        _save(plugin_instance)
        yield event.plain_result(
            "✅ 已开启无变化通知\n\n"
            "监控周期内所有账号均无库存变化时，将向绑定会话发送\"无变化\"信息"
        )
    elif arg == "false":
        plugin_instance.config["non_change_message"] = False
        _save(plugin_instance)
        yield event.plain_result(
            "📵 已关闭无变化通知\n\n"
            "监控周期内无变化时将不再发送消息"
        )
    elif not arg:
        current = plugin_instance.config.get("non_change_message", False)
        yield event.plain_result(
            "🔔 无变化通知当前状态：" + ("开启" if current else "关闭") + "\n\n"
            "用法：/non-change-message true | false"
        )
    else:
        yield event.plain_result(
            "❌ 参数错误，请输入 true 或 false\n用法：/non-change-message true | false"
        )


def _save(plugin_instance) -> None:
    """写回配置并持久化。"""
    try:
        plugin_instance.config.save_config()
        logger.info("无变化通知开关已更新并保存")
    except Exception as exc:
        logger.warning("配置保存失败（仅内存生效）：%s", exc)
