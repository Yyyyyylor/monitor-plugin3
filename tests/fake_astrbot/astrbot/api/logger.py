"""最小 astrbot.api.logger 桩 — 供无 AstrBot 环境的测试/验证使用。"""

import logging

logger = logging.getLogger("astrbot")


def _init():
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.WARNING)


_init()
