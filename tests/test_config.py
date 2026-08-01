"""配置适配器回归测试 — 验证可变单例注入模式。

背景（真实运行 bug）：各模块 `from ..config import settings` 是值拷贝，
若采用"先 None 后赋值"模式，拷贝得到的永远是 None（NoneType 报错）。
本测试验证：settings 导入即存在、setup_settings 只更新内部引用、
从其他模块导入的引用在注入后立即生效。
"""

from __future__ import annotations


def test_settings_never_none():
    """settings 导入即为有效实例（非 None）。"""
    from monitor_plugin3.core import config as core_config

    assert core_config.settings is not None
    # 未注入配置时所有属性返回默认值
    assert core_config.settings.steam_proxy_mode == "auto"
    assert core_config.settings.fetch_interval_minutes == 60
    assert core_config.settings.request_delay_seconds == 1.2
    assert core_config.settings.consecutive_fail_threshold == 3


def test_setup_settings_updates_inplace():
    """setup_settings 更新内部引用，不重新赋值变量。"""
    from monitor_plugin3.core import config as core_config

    ref_before = core_config.settings
    core_config.setup_settings({
        "proxy": {"mode": "manual", "manual_url": "http://127.0.0.1:7890", "hosts_override": ""},
        "crawler_settings": {"request_delay_seconds": 0.5, "page_size": 1000,
                             "request_timeout_seconds": 15, "max_retries": 2},
        "tiered_scheduling": {"enabled": True, "high_interval_minutes": 3,
                              "medium_interval_minutes": 6, "low_interval_minutes": 12,
                              "user_spacing_seconds": 1.0},
        "admin_notify": {"enabled": True, "admin_umos": "qq:admin:1", "consecutive_fail_threshold": 2},
        "retention": {"change_retention_days": 14, "archive_retention_days": 30,
                      "compact_hour": 5, "snapshot_interval_hours": 6},
    })
    # 变量未被重新赋值（同一对象）
    assert core_config.settings is ref_before
    assert core_config.settings.steam_proxy_mode == "manual"
    assert core_config.settings.steam_proxy_url == "http://127.0.0.1:7890"
    assert core_config.settings.tiered_scheduling_enabled is True
    assert core_config.settings.tier_high_interval_minutes == 3
    assert core_config.settings.snapshot_interval_hours == 6
    assert core_config.settings.admin_notify_enabled is True
    assert core_config.settings.admin_webhook_url == "qq:admin:1"
    assert core_config.settings.request_delay_seconds == 0.5

    # 恢复默认配置，避免污染其他测试
    core_config.setup_settings({})


def test_imported_reference_sees_updates():
    """从其他模块导入的 settings 引用在注入后立即生效（本次 bug 的回归点）。"""
    from monitor_plugin3.core import config as core_config
    # fetcher 模块通过 from ..config import settings 拿到引用
    from monitor_plugin3.core.crawler import fetcher

    core_config.setup_settings({
        "proxy": {"mode": "hosts", "manual_url": "", "hosts_override": "127.0.0.1:443"},
        "crawler_settings": {"request_delay_seconds": 1.2, "page_size": 2000,
                             "request_timeout_seconds": 30, "max_retries": 3},
    })
    # fetcher 中的 settings 与 core.config 的是同一个对象
    assert fetcher.settings is core_config.settings
    assert fetcher.settings.steam_proxy_mode == "hosts"
    assert fetcher.settings.steam_hosts_override == "127.0.0.1:443"

    # 调度器与分发器同样生效
    from monitor_plugin3.scheduler.monitor import settings as sched_settings
    from monitor_plugin3.notifier.dispatcher import settings as disp_settings
    assert sched_settings is core_config.settings
    assert disp_settings is core_config.settings

    core_config.setup_settings({})
