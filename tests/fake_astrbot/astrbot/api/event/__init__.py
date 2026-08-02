"""最小 astrbot.api.event 桩 — filter 装饰器 / AstrMessageEvent / MessageChain。"""

from __future__ import annotations

from enum import Enum
from typing import Any


class PermissionType(Enum):
    ADMIN = "admin"
    GROUP_ADMIN = "group_admin"
    MEMBER = "member"
    ALL = "all"


class EventMessageType(Enum):
    ALL = "all"
    PRIVATE_MESSAGE = "private"
    GROUP_MESSAGE = "group"


class PlatformAdapterType(Enum):
    AIOCQHTTP = "aiocqhttp"
    QQQFFICIAL = "qq_official"
    TELEGRAM = "telegram"
    WEBCHAT = "webchat"
    ALL = "all"


class MessageChain:
    """消息链最小桩（仅满足插件投递路径的链式调用）。"""

    def __init__(self, chain: list | None = None):
        self.chain: list = chain or []

    def message(self, text: str) -> "MessageChain":
        from ..message_components import Plain
        self.chain.append(Plain(text=text))
        return self

    def file_image(self, path: str) -> "MessageChain":
        from ..message_components import Image
        self.chain.append(Image.fromFileSystem(path))
        return self

    def url_image(self, url: str) -> "MessageChain":
        from ..message_components import Image
        self.chain.append(Image.fromURL(url))
        return self

    def __bool__(self) -> bool:
        return bool(self.chain)


class AstrMessageEvent:
    """消息事件最小桩（导入期使用；字段在运行期由真实框架注入）。"""

    def __init__(self, **kwargs):
        self.unified_msg_origin: str = kwargs.get("unified_msg_origin", "test:session:1")
        self.message_str: str = kwargs.get("message_str", "")
        self._messages: list = kwargs.get("messages", [])

    def plain_result(self, text: str):
        return {"type": "plain", "data": text}

    def image_result(self, url: str):
        return {"type": "image", "data": url}

    def chain_result(self, chain):
        return {"type": "chain", "data": chain}

    def get_messages(self) -> list:
        return self._messages

    def get_sender_name(self) -> str:
        return "test_user"

    def get_sender_id(self) -> str:
        return "12345"

    def get_platform_name(self) -> str:
        return "test"

    def is_admin(self) -> bool:
        return True


class filter:
    """filter 装饰器命名空间桩（不注册，仅返回原函数）。"""

    PermissionType = PermissionType
    EventMessageType = EventMessageType
    PlatformAdapterType = PlatformAdapterType

    @staticmethod
    def command(name: str, alias=None, priority: int = 0):
        def deco(fn):
            fn.__astrbot_command__ = name
            return fn
        return deco

    @staticmethod
    def command_group(name: str):
        def deco(fn):
            return fn
        return deco

    @staticmethod
    def permission_type(pt):
        def deco(fn):
            fn.__astrbot_permission__ = pt
            return fn
        return deco

    @staticmethod
    def event_message_type(mt):
        def deco(fn):
            return fn
        return deco

    @staticmethod
    def platform_adapter_type(pat):
        def deco(fn):
            return fn
        return deco

    @staticmethod
    def on_astrbot_loaded():
        def deco(fn):
            return fn
        return deco
