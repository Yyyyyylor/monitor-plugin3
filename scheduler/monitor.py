"""核心监控任务 — 去 APScheduler 化，使用 asyncio 后台循环。

从 monitor/src/scheduler/monitor.py 迁移（plan-v3 §12.1），适配插件环境：
- APScheduler → asyncio.create_task 后台循环（三个 Task）
- 通知渠道 → 内存 MessageQueue（QQ 批量投递），不再直发 TG/钉钉/Server酱
- 失败告警 → notifier.dispatcher.notify_admin（投递到 admin_umos）

统一间隔模式（tiered_scheduling_enabled=False）：
  所有活跃用户每 fetch_interval_minutes 统一抓取一轮。
分层调度模式（tiered_scheduling_enabled=True）：
  high/medium/low 三个独立循环，各自按配置间隔运行，互不阻塞。
全局锁机制防止任务重叠：
  _monitor_lock（统一模式）+ _tier_locks（分层模式每层独立）。
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Awaitable

from astrbot.api import logger

from ..core.config import settings
from ..core.crawler.fetcher import fetch_inventory_paginated
from ..core.crawler.parser import parse_inventory_response
from ..core.detector.diff import analyze_activity, detect_changes
from ..core.models.item import InventorySnapshot
from ..db.repository import (
    get_active_users,
    get_active_users_by_frequency,
    get_user_by_steam_id,
    load_current_snapshot,
    record_failure,
    reset_failure_count,
    save_daily_archive,
    save_snapshot_and_changes,
)

# 全局互斥锁 — 防止任务重叠
_monitor_lock = asyncio.Lock()
# 分层调度锁（每层独立）
_tier_locks: dict[str, asyncio.Lock] = {
    "high": asyncio.Lock(),
    "medium": asyncio.Lock(),
    "low": asyncio.Lock(),
}
# 分层最近运行时间与统计
_tier_last_run: dict[str, str] = {"high": "", "medium": "", "low": ""}
_tier_last_stats: dict[str, dict[str, Any]] = {"high": {}, "medium": {}, "low": {}}
_last_cycle_stats: dict[str, Any] = {}

# 供外部查询的 Callback（/crap 手动触发时实时反馈）
OnUserDone = Callable[[dict[str, Any]], Awaitable[None]] | None

# 消息队列引用（由 main.py 注入）
_global_message_queue = None


def set_message_queue(queue_instance) -> None:
    """设置全局消息队列引用（由 main.py 调用）。"""
    global _global_message_queue
    _global_message_queue = queue_instance


# ---------------------------------------------------------------------------
# 监控周期入口（供定时循环与 /crap 手动触发共用）
# ---------------------------------------------------------------------------

async def monitor_all_users(
    on_user_done: OnUserDone = None,
) -> dict[str, Any]:
    """主监控循环：处理所有活跃用户（统一间隔模式）。

    返回统计信息: {"success", "fail", "total_events", "elapsed_sec"}
    """
    if _monitor_lock.locked():
        logger.warning("上一次监控任务尚未结束，跳过本次触发")
        return {"skipped": 1}

    async with _monitor_lock:
        return await _do_monitor_users(on_user_done)


async def monitor_tier(
    tier: str,
    on_user_done: OnUserDone = None,
) -> dict[str, Any]:
    """分层调度：处理指定层级的所有活跃用户。

    tier 必须是 "high" | "medium" | "low"。
    """
    lock = _tier_locks.get(tier)
    if lock is None:
        return {"skipped": 1, "error": f"unknown tier: {tier}"}

    if lock.locked():
        logger.warning("层级 %s 上一次任务尚未结束，跳过本次触发", tier)
        return {"skipped": 1, "tier": tier}

    async with lock:
        grouped = await get_active_users_by_frequency()
        users = grouped.get(tier, [])
        if not users:
            return {"success": 0, "fail": 0, "total_events": 0, "tier": tier, "elapsed_sec": 0}
        return await _do_monitor_users(on_user_done, users=users)


async def _do_monitor_users(
    on_user_done: OnUserDone = None,
    users: list[Any] | None = None,
) -> dict[str, Any]:
    """内部实现：处理给定的用户列表。"""
    start_ts = time.time()
    stats: dict[str, Any] = {"success": 0, "fail": 0, "total_events": 0}

    if users is None:
        users_record = await get_active_users()
        users = list(users_record)
    if not users:
        logger.info("没有活跃用户需要监控")
        return stats

    spacing = settings.tier_user_spacing_seconds if settings.tiered_scheduling_enabled else 1.0

    for i, user in enumerate(users):
        result = {
            "steam_id": user.steam_id,
            "nickname": user.nickname or "",
            "ok": False,
            "msg": "",
            "events": 0,
        }
        try:
            event_count = await asyncio.wait_for(
                _process_single_user(user.steam_id),
                timeout=120.0,
            )
            stats["success"] += 1
            stats["total_events"] += event_count or 0
            result["ok"] = True
            result["msg"] = "成功"
            result["events"] = event_count or 0
        except asyncio.TimeoutError:
            logger.error("用户 %s 处理超时（120s）", user.steam_id)
            fails = await record_failure(user.steam_id, "处理超时")
            stats["fail"] += 1
            result["msg"] = "超时"
            await _check_admin_alert(user.steam_id, fails)
        except Exception as exc:
            logger.exception("用户 %s 处理异常: %s", user.steam_id, exc)
            fails = await record_failure(user.steam_id, str(exc)[:500])
            stats["fail"] += 1
            result["msg"] = str(exc)[:100]
            await _check_admin_alert(user.steam_id, fails)

        if on_user_done:
            try:
                await on_user_done(result)
            except Exception:
                pass

        # 用户间间隔（最后一个不等）
        if i < len(users) - 1:
            await asyncio.sleep(spacing)

    elapsed = time.time() - start_ts
    stats["elapsed_sec"] = round(elapsed, 2)
    logger.info(
        "本轮监控完成: 成功 %d / 失败 %d, 事件 %d, 耗时 %.1fs",
        stats["success"], stats["fail"], stats["total_events"], elapsed,
    )
    _last_cycle_stats.update(stats)

    # 无变化通知：周期内所有账号均无变化且开关开启时，向绑定会话发送汇总
    if (
        stats.get("success", 0) > 0
        and stats.get("total_events", 0) == 0
        and settings.non_change_message_enabled
    ):
        try:
            from ..notifier.dispatcher import notify_no_change
            await notify_no_change(users, stats)
        except Exception as exc:
            logger.exception("无变化通知发送失败：%s", exc)

    return stats


async def _process_single_user(steam_id: str) -> int:
    """处理单个用户的完整流程。"""
    logger.info("开始处理用户 %s", steam_id)

    # 1. 抓取库存
    raw = await fetch_inventory_paginated(steam_id)
    if raw is None:
        raise RuntimeError("无法获取库存（私密库存或 API 错误）")

    # 2. 解析
    current_items = parse_inventory_response(raw)
    if current_items is None:
        raise RuntimeError("库存解析结果为空")

    api_total = raw.get("total_inventory_count", len(current_items))
    logger.info("用户 %s 库存 %d 件物品", steam_id, len(current_items))

    # 3. 加载当前基准
    previous_snapshot = await load_current_snapshot(steam_id)

    if previous_snapshot is None:
        snapshot = InventorySnapshot(
            steam_id=steam_id,
            items=current_items,
            item_count=len(current_items),
            api_total_count=api_total,
        )
        await save_snapshot_and_changes(snapshot, [])
        await reset_failure_count(steam_id)
        logger.info("用户 %s 初始基准快照已创建 (%d 件, total=%d)", steam_id, len(current_items), api_total)
        return 0

    # 4. 差异检测
    events = detect_changes(
        steam_id=steam_id,
        previous_items=previous_snapshot.items,
        current_items=current_items,
    )

    # 5. 原子存储
    new_snapshot = InventorySnapshot(
        steam_id=steam_id,
        items=current_items,
        item_count=len(current_items),
        api_total_count=api_total,
    )
    await save_snapshot_and_changes(new_snapshot, events)

    # 6. 活动分类 + 通知入队
    if events:
        activity = analyze_activity(
            events=events,
            prev_total=previous_snapshot.api_total_count,
            prev_returned=previous_snapshot.item_count,
            new_total=api_total,
            new_returned=len(current_items),
        )
        logger.info("用户 %s %s", steam_id, activity.summary_line())

        user_record = await get_user_by_steam_id(steam_id)
        if user_record and user_record.bound_umo and _global_message_queue:
            await _global_message_queue.enqueue(
                user_record.bound_umo, steam_id, events, activity
            )
            logger.debug(
                "用户 %s 变化已入队（%d 事件）→ 会话 %s",
                steam_id, len(events), user_record.bound_umo[:40],
            )
        else:
            # 未绑定会话：仅监控入库不投递（plan-v3 R8）
            logger.warning(
                "用户 %s 未绑定会话（bound_umo=%r，队列=%s），变化仅入库不投递；"
                "请用 /addaccount 重新添加以绑定推送会话",
                steam_id,
                (user_record.bound_umo if user_record else None),
                bool(_global_message_queue),
            )

    await reset_failure_count(steam_id)
    logger.info("用户 %s 处理完成: %d 个变化事件", steam_id, len(events))
    return len(events)


async def _check_admin_alert(steam_id: str, fails: int) -> None:
    """检查是否触发管理员告警阈值。"""
    threshold = settings.consecutive_fail_threshold
    if threshold > 0 and fails >= threshold:
        try:
            from ..notifier.dispatcher import notify_admin
            await notify_admin(steam_id, fails)
        except Exception as exc:
            logger.exception("管理员告警投递失败: %s", exc)


# ---------------------------------------------------------------------------
# 后台循环（asyncio Task）
# ---------------------------------------------------------------------------

async def _unified_monitor_worker(stop_flag) -> None:
    """统一模式监控循环：所有用户按 fetch_interval_minutes 统一轮询。"""
    interval = settings.fetch_interval_minutes
    logger.info("启动统一模式监控循环，间隔=%d 分钟", interval)
    while not stop_flag.is_set():
        try:
            await monitor_all_users()
        except asyncio.CancelledError:
            logger.info("统一模式监控循环已取消")
            raise
        except Exception as exc:
            logger.exception("统一模式监控循环异常：%s", exc)
        await _sleep_interruptible(interval * 60, stop_flag)


async def _tiered_monitor_worker(stop_flag) -> None:
    """分层模式监控循环：三层独立 worker 并行运行。"""
    logger.info(
        "启动分层模式监控循环：high=%d, medium=%d, low=%d 分钟",
        settings.tier_high_interval_minutes,
        settings.tier_medium_interval_minutes,
        settings.tier_low_interval_minutes,
    )
    workers = [
        _tier_worker("high", settings.tier_high_interval_minutes, stop_flag),
        _tier_worker("medium", settings.tier_medium_interval_minutes, stop_flag),
        _tier_worker("low", settings.tier_low_interval_minutes, stop_flag),
    ]
    try:
        await asyncio.gather(*workers)
    except asyncio.CancelledError:
        logger.info("分层模式监控循环已取消")
        raise


async def _tier_worker(tier: str, interval_minutes: int, stop_flag) -> None:
    """单层级 Worker 循环。"""
    logger.info("启动层级 %s 监控循环，间隔=%d 分钟", tier, interval_minutes)
    while not stop_flag.is_set():
        try:
            result = await monitor_tier(tier)
            stats = result.get("stats", result)
            if stats.get("success", 0) > 0 or stats.get("skipped", 0) == 0:
                _tier_last_run[tier] = datetime.now(timezone.utc).isoformat()
                _tier_last_stats[tier] = stats
        except asyncio.CancelledError:
            logger.info("层级 %s 监控循环已取消", tier)
            raise
        except Exception as exc:
            logger.exception("层级 %s 监控循环异常：%s", tier, exc)
        await _sleep_interruptible(interval_minutes * 60, stop_flag)


async def _message_flush_loop(stop_flag) -> None:
    """消息投递循环：定时将队列中的通知批量发送到 QQ。

    设计（修复"变化不入队/不推送"体验）：
    - 启动后**立即 flush 一次**，处理插件重启/重载时队列中的存量消息；
    - 之后每轮从 settings 动态读取投递间隔（/messagegap 修改即时生效），
      按间隔循环 flush。
    """
    logger.info("启动消息投递循环，当前间隔=%d 分钟", settings.message_interval_minutes)

    while not stop_flag.is_set():
        try:
            from ..notifier.dispatcher import flush_all_notifications
            flushed = await flush_all_notifications()
            logger.info("消息投递周期完成：成功 %d 条", flushed)
        except asyncio.CancelledError:
            logger.info("消息投递循环已取消")
            raise
        except Exception as exc:
            logger.exception("消息投递循环异常：%s", exc)
        # 动态读取间隔（/messagegap 修改后下一轮生效）
        interval = max(1, int(settings.message_interval_minutes))
        await _sleep_interruptible(interval * 60, stop_flag)


async def _daily_maintenance_loop(stop_flag) -> None:
    """每日维护循环：归档 + 清理过期数据。

    snapshot_interval_hours=0：每天 compact_hour 执行一次（首个周期对齐到下一个整点）；
    >0：每 N 小时执行一次（ver3.x 小时级归档行为）。
    """
    interval_hours = settings.snapshot_interval_hours
    compact_hour = settings.compact_hour

    if interval_hours > 0:
        logger.info("启动小时级维护循环，间隔=%d 小时", interval_hours)
        while not stop_flag.is_set():
            await _sleep_interruptible(interval_hours * 3600, stop_flag)
            try:
                await run_daily_maintenance()
            except asyncio.CancelledError:
                logger.info("小时级维护循环已取消")
                raise
            except Exception as exc:
                logger.exception("小时级维护循环异常：%s", exc)
        return

    # 每日模式：计算到下一个 compact_hour 的等待秒数，之后每 24h 一次
    now = datetime.now()
    target = now.replace(hour=compact_hour, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    wait_seconds = int((target - now).total_seconds())
    logger.info("启动每日维护循环，每日 %02d:00 执行，首次 %d 秒后", compact_hour, wait_seconds)
    await _sleep_interruptible(wait_seconds, stop_flag)
    while not stop_flag.is_set():
        try:
            await run_daily_maintenance()
        except asyncio.CancelledError:
            logger.info("每日维护循环已取消")
            raise
        except Exception as exc:
            logger.exception("每日维护循环异常：%s", exc)
        await _sleep_interruptible(24 * 3600, stop_flag)


async def _sleep_interruptible(seconds: float, stop_flag) -> None:
    """分段睡眠，可被 stop_flag 或取消提前唤醒。"""
    step = 1.0
    remaining = seconds
    while remaining > 0 and not stop_flag.is_set():
        await asyncio.sleep(min(step, remaining))
        remaining -= step


async def run_daily_maintenance() -> None:
    """执行每日维护操作：归档 + 清理。"""
    logger.info("开始执行每日维护...")
    start_ts = time.time()
    users = await get_active_users()
    archived_count = 0
    for user in users:
        snapshot = await load_current_snapshot(user.steam_id)
        if snapshot:
            await save_daily_archive(user.steam_id, snapshot.items)
            archived_count += 1

    deleted_changes = await cleanup_old_changes()
    deleted_archives = await cleanup_old_archives()
    elapsed = time.time() - start_ts
    logger.info(
        "每日维护完成：归档%d用户，清理变化事件%d条，清理归档%d条，耗时%.1fs",
        archived_count, deleted_changes, deleted_archives, elapsed,
    )


async def cleanup_old_changes() -> int:
    """清理过期变化事件（按配置保留天数）。"""
    from ..db.repository import cleanup_old_changes as _cleanup_changes
    return await _cleanup_changes()


async def cleanup_old_archives() -> int:
    """清理过期归档快照（按配置保留天数）。"""
    from ..db.repository import cleanup_old_archives as _cleanup_archives
    return await _cleanup_archives()


# ---------------------------------------------------------------------------
# MonitorController — 后台任务生命周期管理
# ---------------------------------------------------------------------------

class MonitorController:
    """监控后台任务控制器：启动、停止、状态查询（对应 plan-v3 §5.3 三个循环）。"""

    def __init__(self, plugin_instance=None):
        self.plugin = plugin_instance
        self._stop_flag = asyncio.Event()
        self._tasks: list[asyncio.Task] = []
        self._running = False

    async def start(self) -> None:
        """启动三个后台循环。"""
        if self._running:
            logger.info("监控后台任务已在运行中")
            return
        self._running = True
        self._stop_flag = asyncio.Event()
        self._tasks = []

        if settings.tiered_scheduling_enabled:
            self._tasks.append(asyncio.create_task(_tiered_monitor_worker(self._stop_flag)))
        else:
            self._tasks.append(asyncio.create_task(_unified_monitor_worker(self._stop_flag)))
        self._tasks.append(asyncio.create_task(_message_flush_loop(self._stop_flag)))
        self._tasks.append(asyncio.create_task(_daily_maintenance_loop(self._stop_flag)))
        logger.info("监控后台任务已全部启动（%d 个 Task）", len(self._tasks))

    async def stop(self) -> None:
        """停止三个后台循环（取消 Task 并等待收尾）。"""
        if not self._running:
            return
        self._running = False
        self._stop_flag.set()
        for task in self._tasks:
            if task and not task.done():
                task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []
        logger.info("监控后台任务已全部停止")

    @property
    def running(self) -> bool:
        return self._running

    def get_status(self) -> dict[str, Any]:
        """获取监控状态信息。"""
        return {
            "running": self._running,
            "mode": "tiered" if settings.tiered_scheduling_enabled else "unified",
            "interval_minutes": settings.fetch_interval_minutes,
            "message_interval_minutes": settings.message_interval_minutes,
            "last_cycle": dict(_last_cycle_stats),
            "tiers": get_tier_status(),
        }


def get_tier_status() -> dict[str, Any]:
    """返回各层级调度状态。"""
    return {
        "enabled": settings.tiered_scheduling_enabled,
        "intervals": {
            "high": settings.tier_high_interval_minutes,
            "medium": settings.tier_medium_interval_minutes,
            "low": settings.tier_low_interval_minutes,
        },
        "last_runs": dict(_tier_last_run),
        "last_stats": dict(_tier_last_stats),
        "spacing_seconds": settings.tier_user_spacing_seconds,
    }
