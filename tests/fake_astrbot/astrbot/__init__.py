"""astrbot 包最小桩 — 供无 AstrBot 环境的测试/验证使用。

仅实现插件代码用到的 API 表面（logger/filter/MessageChain/Star 等），
不实现任何真实功能。
"""

from __future__ import annotations


class AstrBotConfig(dict):
    """配置桩：dict 子类，支持 save_config。"""

    def save_config(self) -> None:
        pass
