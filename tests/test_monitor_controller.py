"""监控控制器防多实例测试（F1）。

背景（真实运行"并发监控"问题）：AstrBot 热重载可能残留旧插件实例，
新旧实例的监控循环并发执行（同用户 0.2s 内被抓两次）。
本测试验证：共享注册表保证同一时刻仅一个控制器运行。
"""

from __future__ import annotations

import asyncio

import monitor_plugin3.scheduler.monitor as sm


def _patch_workers(monkeypatch):
    """将三个后台循环替换为立即返回的占位（避免真实启动监控/数据库访问）。"""

    async def _noop(stop_flag):
        await asyncio.sleep(0)

    monkeypatch.setattr(sm, "_unified_monitor_worker", _noop)
    monkeypatch.setattr(sm, "_tiered_monitor_worker", _noop)
    monkeypatch.setattr(sm, "_message_flush_loop", _noop)
    monkeypatch.setattr(sm, "_daily_maintenance_loop", _noop)


def test_shared_guard_single_instance(monkeypatch):
    """同一时刻仅一个控制器注册在共享表。"""
    _patch_workers(monkeypatch)
    from monitor_plugin3.scheduler.monitor import MonitorController, _get_shared_guard

    async def scenario():
        guard = _get_shared_guard()
        guard["controller"] = None  # 清理测试环境

        c1 = MonitorController()
        await c1.start()
        assert guard["controller"] is c1
        assert c1.running

        await c1.stop()
        assert guard["controller"] is None
        assert not c1.running

    asyncio.run(scenario())


def test_second_controller_stops_first(monkeypatch):
    """新控制器启动时停止仍在运行的旧控制器（F1 核心）。"""
    _patch_workers(monkeypatch)
    from monitor_plugin3.scheduler.monitor import MonitorController, _get_shared_guard

    async def scenario():
        guard = _get_shared_guard()
        guard["controller"] = None

        c1 = MonitorController()
        await c1.start()
        assert guard["controller"] is c1

        # 第二个控制器启动：应停止 c1 并接管注册
        c2 = MonitorController()
        await c2.start()
        assert guard["controller"] is c2
        assert not c1.running, "旧控制器应已被停止"
        assert c2.running

        await c2.stop()
        assert guard["controller"] is None

    asyncio.run(scenario())


def test_stop_not_running_cleans_guard(monkeypatch):
    """stop 未运行实例时也清理共享注册（幂等）。"""
    _patch_workers(monkeypatch)
    from monitor_plugin3.scheduler.monitor import MonitorController, _get_shared_guard

    async def scenario():
        guard = _get_shared_guard()
        guard["controller"] = None

        c = MonitorController()
        await c.stop()  # 未 start 直接 stop，不应抛错
        assert guard["controller"] is None

        # 手工伪造残留注册后 stop 清理
        guard["controller"] = c
        await c.stop()
        assert guard["controller"] is None

    asyncio.run(scenario())
