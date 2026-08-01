"""立即触发一轮爬取 - /crap 指令实现（plan-v3 §7.1 F10，对应 Web /api/monitor/fetch-now）。

手动触发与定时轮共用同一入口（monitor_all_users / monitor_tier），
由全局锁保证不与定时轮重叠（plan-v3 R6 / AC9）。
"""

from __future__ import annotations

from astrbot.api.event import AstrMessageEvent


async def crawl_now(event: AstrMessageEvent, plugin_instance=None):
    """立即触发一轮爬取（按当前调度模式）。"""
    from ..core.config import settings
    from ..scheduler.monitor import monitor_all_users, monitor_tier

    yield event.plain_result("🚀 正在触发一轮爬取，请稍候...")

    if settings.tiered_scheduling_enabled:
        # 分层模式：三轮并行（high/medium/low）
        import asyncio
        results = await asyncio.gather(
            monitor_tier("high"),
            monitor_tier("medium"),
            monitor_tier("low"),
        )
        stats = {"success": 0, "fail": 0, "total_events": 0, "elapsed_sec": 0.0}
        for r in results:
            s = r.get("stats", r)
            stats["success"] += s.get("success", 0)
            stats["fail"] += s.get("fail", 0)
            stats["total_events"] += s.get("total_events", 0)
            stats["elapsed_sec"] = max(stats["elapsed_sec"], s.get("elapsed_sec", 0))
    else:
        stats = await monitor_all_users()

    if stats.get("skipped"):
        yield event.plain_result("⏳ 上一轮监控任务尚未结束，已跳过本次触发（防止重叠）")
        return

    yield event.plain_result(
        f"🚀 手动触发爬取完成!\n\n"
        f"成功：{stats.get('success', 0)}\n"
        f"失败：{stats.get('fail', 0)}\n"
        f"事件：{stats.get('total_events', 0)}\n"
        f"耗时：{stats.get('elapsed_sec', 0):.1f}s"
    )
