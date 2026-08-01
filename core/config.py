"""配置适配器 — 将 AstrBotConfig 映射为 monitor settings 风格的接口。

core/crawler/detector/scheduler 等模块依赖 `settings` 单例属性访问配置，
本模块提供适配器，从 AstrBotConfig 中读取配置并模拟原项目的 settings 行为。

重要设计（修复真实运行 bug）：
- `settings` 是**模块级可变单例**（导入时即存在），`setup_settings` 只更新其
  内部引用，绝不重新赋值 `settings` 变量本身。
- 原因：各模块用 `from ..config import settings` 做值拷贝——若采用
  "先 None 后赋值"模式，拷贝得到的永远是 None（NoneType 无属性报错）。
- 所有属性带默认值保护：即使 config 尚未注入也返回合理默认值。
"""

from __future__ import annotations

from typing import Any


class PluginSettings:
    """AstrBotConfig → Settings 风格的配置适配器（可变单例）。"""

    def __init__(self, config: dict[str, Any] | None = None):
        self._c: dict[str, Any] = config or {}

    def _get(self, *keys: str, default: Any = None) -> Any:
        """安全嵌套取值：中间层缺失时返回默认值。"""
        cur: Any = self._c
        for k in keys:
            if isinstance(cur, dict):
                cur = cur.get(k)
            else:
                return default
        return cur if cur is not None else default

    @property
    def database_url(self) -> str:
        from ..db.database import DATABASE_URL
        return DATABASE_URL

    @property
    def steam_ids(self) -> str:
        return self._get("steam_ids", default="")

    @property
    def steam_id_list(self) -> list[str]:
        """返回解析后的 Steam ID 列表。"""
        raw = self.steam_ids
        if not raw or not raw.strip():
            return []
        return [s.strip() for s in raw.split(",") if s.strip()]

    @property
    def fetch_interval_minutes(self) -> int:
        return self._get("fetch_interval_minutes", default=60)

    @property
    def request_delay_seconds(self) -> float:
        return self._get("crawler_settings", "request_delay_seconds", default=1.2)

    @property
    def page_size(self) -> int:
        return self._get("crawler_settings", "page_size", default=2000)

    @property
    def request_timeout_seconds(self) -> int:
        return self._get("crawler_settings", "request_timeout_seconds", default=30)

    @property
    def max_retries(self) -> int:
        return self._get("crawler_settings", "max_retries", default=3)

    # ---- 分层调度 ----
    @property
    def tiered_scheduling_enabled(self) -> bool:
        return self._get("tiered_scheduling", "enabled", default=False)

    @property
    def tier_high_interval_minutes(self) -> int:
        return self._get("tiered_scheduling", "high_interval_minutes", default=5)

    @property
    def tier_medium_interval_minutes(self) -> int:
        return self._get("tiered_scheduling", "medium_interval_minutes", default=10)

    @property
    def tier_low_interval_minutes(self) -> int:
        return self._get("tiered_scheduling", "low_interval_minutes", default=20)

    @property
    def tier_user_spacing_seconds(self) -> float:
        return self._get("tiered_scheduling", "user_spacing_seconds", default=1.5)

    # ---- Steam API ----
    @property
    def steam_inventory_url(self) -> str:
        return "https://steamcommunity.com/inventory/{steam_id}/730/2"

    @property
    def steam_user_agent(self) -> str:
        return (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

    @property
    def steam_cookie(self) -> str:
        return self._get("steam_cookie", default="")

    # ---- 代理设置 ----
    @property
    def steam_proxy_mode(self) -> str:
        return self._get("proxy", "mode", default="auto")

    @property
    def steam_proxy_url(self) -> str:
        return self._get("proxy", "manual_url", default="")

    @property
    def steam_hosts_override(self) -> str:
        return self._get("proxy", "hosts_override", default="")

    # ---- 通知（暂未使用）----
    @property
    def user_notify_enabled(self) -> bool:
        return False  # QQ 消息由 dispatcher 统一处理

    # ---- 管理员告警 ----
    @property
    def admin_notify_enabled(self) -> bool:
        return self._get("admin_notify", "enabled", default=False)

    @property
    def admin_webhook_url(self) -> str | None:
        admin_umos = self._get("admin_notify", "admin_umos", default="") or ""
        if not admin_umos.strip():
            return None
        return admin_umos.split(",")[0]  # 仅取第一个作为默认

    @property
    def consecutive_fail_threshold(self) -> int:
        return self._get("admin_notify", "consecutive_fail_threshold", default=3)

    # ---- 数据保留 ----
    @property
    def change_retention_days(self) -> int:
        return self._get("retention", "change_retention_days", default=7)

    @property
    def archive_retention_days(self) -> int:
        return self._get("retention", "archive_retention_days", default=90)

    @property
    def compact_hour(self) -> int:
        return self._get("retention", "compact_hour", default=3)

    @property
    def snapshot_interval_hours(self) -> int:
        return self._get("retention", "snapshot_interval_hours", default=0)

    # ---- 消息投递间隔 ----
    @property
    def message_interval_minutes(self) -> int:
        return self._get("message_interval_minutes", default=30)


# 模块级可变单例：导入即存在（非 None），setup_settings 只更新其内部引用
settings = PluginSettings()


def setup_settings(config: dict[str, Any]) -> None:
    """注入 AstrBotConfig（只更新单例内部引用，不重新赋值 settings 变量）。

    各模块通过 `from ..config import settings` 拿到的引用始终有效。
    """
    settings._c = config or {}
