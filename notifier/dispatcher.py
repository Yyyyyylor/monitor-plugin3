"""消息分发器 — 事件格式化 + QQ 投递 + 管理员告警 + 渲染降级。

替代 monitor 的 Telegram/钉钉/Server酱 渠道（plan-v3 §12.1）：
- 用户通知 → context.send_message(bound_umo, chain) 批量合并投递
- 管理员告警 → 复用同一投递通道，目标为配置的 admin_umos 列表
- 渲染三级降级：外部 text_to_image 插件 → 内置 html_render → 纯文本
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import astrbot.api.message_components as Comp
from astrbot.api import logger
from astrbot.api.event import MessageChain

from ..core.config import settings
from .formatter import build_report, format_event_text

# 模板目录：monitor-plugin3/templates/
TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"

# 短消息阈值（plan-v3 §6.2：≤150 字直接文本投递）
SHORT_TEXT_LIMIT = 150


def _load_template(name: str) -> str:
    """读取 HTML 模板内容（html_render 接收模板字符串而非路径）。"""
    path = TEMPLATE_DIR / name
    return path.read_text(encoding="utf-8")


class MessageDispatcher:
    """消息分发器 - 负责 QQ 投递与降级策略。"""

    def __init__(self, plugin_instance):
        self.plugin = plugin_instance
        self._template_cache: dict[str, str] = {}

    # ------------------------------------------------------------------
    # 主动投递
    # ------------------------------------------------------------------

    async def send_text(self, umo: str, text: str) -> bool:
        """发送纯文本消息到指定会话。"""
        try:
            chain = MessageChain().message(text)
            return await self.plugin.context.send_message(umo, chain)
        except Exception as exc:
            logger.exception("发送纯文本消息失败：%s", exc)
            return False

    async def send_image(self, umo: str, image_url: str) -> bool:
        """发送图片消息到指定会话。"""
        try:
            chain = MessageChain().file_image(image_url)
            return await self.plugin.context.send_message(umo, chain)
        except Exception as exc:
            logger.exception("发送图片消息失败：%s", exc)
            return False

    # ------------------------------------------------------------------
    # 变化通知分发
    # ------------------------------------------------------------------

    async def dispatch_notification(self, umo: str, report: dict[str, Any]) -> bool:
        """分发单个变化通知（文本 / 图片三级降级）。

        plan-v3 §6.2：≤150 字直接文本；否则外部插件 → html_render → 纯文本保底。
        """
        text_message = report.get("text_message", "")
        try:
            if len(text_message) <= SHORT_TEXT_LIMIT:
                return await self.send_text(umo, text_message)

            # 长文本：优先外部 text_to_image 插件
            if self._should_use_external_plugin():
                external_url = await self._render_via_external(report)
                if external_url:
                    return await self.send_image(umo, external_url)

            # 内置 html_render
            try:
                html = self._template("change_report.html")
                img_url = await self.plugin.html_render(html, report)
                return await self.send_image(umo, img_url)
            except Exception as exc:
                logger.warning("html_render 渲染失败，降级为纯文本：%s", exc)
                return await self.send_text(umo, text_message)
        except Exception as exc:
            logger.exception("分发通知失败：%s", exc)
            return False

    def _template(self, name: str) -> str:
        """读取模板（带缓存）。"""
        if name not in self._template_cache:
            self._template_cache[name] = _load_template(name)
        return self._template_cache[name]

    # ------------------------------------------------------------------
    # 外部 text_to_image 插件（预留接口，plan-v3 §11）
    # ------------------------------------------------------------------

    def _should_use_external_plugin(self) -> bool:
        cfg = settings._c.get("text_to_image_plugin", {})
        return bool(cfg.get("use_external", False))

    async def _render_via_external(self, report: dict[str, Any]) -> str | None:
        """通过外部 text_to_image 插件渲染 HTML（接口见 plan-v3 §11.1）。"""
        cfg = settings._c.get("text_to_image_plugin", {})
        plugin_name = cfg.get("plugin_name", "text_to_image")
        try:
            html = self._template("change_report.html")
            for meta in self.plugin.context.get_all_stars():
                if meta.name == plugin_name and hasattr(meta.star_cls, "render"):
                    render_fn = getattr(meta.star_cls, "render")
                    if asyncio.iscoroutinefunction(render_fn):
                        return await render_fn(html)
                    return render_fn(html)
            return None
        except Exception as exc:
            logger.warning("外部文生图插件渲染失败：%s", exc)
            return None

    # ------------------------------------------------------------------
    # 对比报告 / 账号列表渲染（指令用）
    # ------------------------------------------------------------------

    async def render_compare_report(self, data: dict[str, Any]) -> str:
        """渲染快照对比报告，返回图片 URL。"""
        html = self._template("compare_report.html")
        return await self.plugin.html_render(html, data)

    async def render_account_list(self, data: dict[str, Any]) -> str:
        """渲染账号列表长图，返回图片 URL。"""
        html = self._template("account_list.html")
        return await self.plugin.html_render(html, data)

    async def render_inventory_report(self, data: dict[str, Any]) -> str:
        """渲染库存全量报告（/getinventory），返回图片 URL。"""
        html = self._template("inventory_report.html")
        return await self.plugin.html_render(html, data)


# ============================================================================
# 全局函数（供 scheduler / 指令调用）
# ============================================================================

# 全局 dispatcher 引用（由 main.py 创建并注入）
_global_dispatcher: MessageDispatcher | None = None


def set_dispatcher(dispatcher: MessageDispatcher) -> None:
    """设置全局 dispatcher（由 main.py 调用）。"""
    global _global_dispatcher
    _global_dispatcher = dispatcher


async def flush_all_notifications() -> int:
    """从队列中取出所有通知并批量投递（消息投递循环调用）。"""
    if _global_dispatcher is None:
        logger.warning("dispatcher 未初始化，跳过消息投递")
        return 0

    from ..scheduler.monitor import _global_message_queue
    queue = _global_message_queue
    if queue is None:
        return 0

    # /stopmessage off 暂停投递（消息保留在队列中累积）
    plugin = getattr(_global_dispatcher, "plugin", None)
    if plugin is not None and not getattr(plugin, "_message_enabled", True):
        return 0

    notifications = await queue.dequeue_all()
    if not notifications:
        return 0

    success_count = 0
    for notification in notifications:
        report = build_report(
            notification.steam_id,
            notification.events,
            notification.activity,
        )
        ok = await _global_dispatcher.dispatch_notification(notification.umo, report)
        if ok:
            success_count += 1
        # 用户间间隔，降低 QQ 限流风险
        await asyncio.sleep(1.5)
    logger.info("消息投递完成：成功 %d / 共 %d 条", success_count, len(notifications))
    return success_count


async def flush_immediately() -> int:
    """立即投递队列中的全部消息（/messagegap 0 调用）。"""
    return await flush_all_notifications()


async def notify_admin(steam_id: str, fails: int) -> None:
    """管理员告警：账号连续失败达阈值 → 推送到 admin_umos（plan-v3 §5.4）。

    替代 monitor admin_notifier 的 Telegram/Webhook 渠道。
    """
    if _global_dispatcher is None:
        return
    cfg = settings._c.get("admin_notify", {})
    if not cfg.get("enabled", False):
        return
    admin_umos = str(cfg.get("admin_umos", "") or "").strip()
    if not admin_umos:
        return
    threshold = cfg.get("consecutive_fail_threshold", 3)

    text = (
        "⚠️ [监控告警]\n"
        f"账号 {steam_id} 已连续失败 {fails} 次（阈值 {threshold}）\n"
        f"最后错误：{(await _last_error_of(steam_id)) or '未知'}"
    )
    for umo in [u.strip() for u in admin_umos.split(",") if u.strip()]:
        try:
            await _global_dispatcher.send_text(umo, text)
            logger.info("管理员告警已发送至 %s", umo)
        except Exception as exc:
            logger.exception("管理员告警投递失败（%s）：%s", umo, exc)


async def _last_error_of(steam_id: str) -> str | None:
    """查询账号的最后错误信息（告警文案用）。"""
    try:
        from ..db.repository import get_user_by_steam_id
        user = await get_user_by_steam_id(steam_id)
        return user.last_error_msg if user else None
    except Exception:
        return None


def format_event_summary(events) -> str:
    """便捷函数：事件列表 → 摘要文本（/crap 结果展示等用）。"""
    from ..core.models.item import ChangeType
    added = sum(1 for e in events if e.change_type == ChangeType.ADDED)
    removed = sum(1 for e in events if e.change_type == ChangeType.REMOVED)
    modified = sum(1 for e in events if e.change_type == ChangeType.MODIFIED)
    swapped = sum(1 for e in events if e.change_type == ChangeType.SWAPPED)
    parts = [f"新增{added}", f"移除{removed}", f"修改{modified}", f"交换{swapped}"]
    return "，".join(parts)
