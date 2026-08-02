"""消息投递回归测试 — 验证 dispatch 的文本/图片构造与 send_message 兼容性。

背景（真实运行"变化不入队/不推送"问题）：
- P3: send_image 曾用 file_image 传 html_render 返回的 http URL → 改为 URL/本地智能分支
- P5: send_message 返回 False 时需告警，不再静默
"""

from __future__ import annotations

import asyncio

from monitor_plugin3.core.config import settings
from monitor_plugin3.notifier.dispatcher import MessageDispatcher
from astrbot.api.message_components import Image, Plain


class _FakeContext:
    """记录最后一次投递的 chain 与 umo。"""

    def __init__(self):
        self.last_umo = None
        self.last_chain = None
        self.calls = 0

    async def send_message(self, umo, chain) -> bool:
        self.last_umo = umo
        self.last_chain = chain
        self.calls += 1
        return True


class _FakePlugin:
    def __init__(self, context):
        self.context = context


def _make_dispatcher() -> tuple[MessageDispatcher, _FakeContext]:
    ctx = _FakeContext()
    dispatcher = MessageDispatcher(_FakePlugin(ctx))
    return dispatcher, ctx


def test_send_text_builds_plain_chain():
    dispatcher, ctx = _make_dispatcher()
    ok = asyncio.run(dispatcher.send_text("qq_official:FriendMessage:abc123", "hello"))
    assert ok is True
    assert ctx.last_umo == "qq_official:FriendMessage:abc123"
    assert isinstance(ctx.last_chain.chain[0], Plain)
    assert ctx.last_chain.chain[0].text == "hello"


def test_send_image_uses_url_image_for_http_url():
    """html_render 返回 http URL → Image.file 应为该 URL（P3 回归点）。"""
    dispatcher, ctx = _make_dispatcher()
    ok = asyncio.run(dispatcher.send_image("qq_official:FriendMessage:abc123", "https://x.example/render.png"))
    assert ok is True
    comp = ctx.last_chain.chain[0]
    assert isinstance(comp, Image)
    assert comp.file == "https://x.example/render.png"


def test_send_image_uses_file_image_for_local_path():
    dispatcher, ctx = _make_dispatcher()
    ok = asyncio.run(dispatcher.send_image("qq_official:FriendMessage:abc123", r"C:\\tmp\\render.png"))
    assert ok is True
    comp = ctx.last_chain.chain[0]
    assert isinstance(comp, Image)
    assert comp.file == r"C:\\tmp\\render.png"


def test_send_message_false_returns_false_not_exception():
    """send_message 返回 False（平台不匹配）时 send_text 返回 False 而非抛异常。"""
    class _FailContext:
        async def send_message(self, umo, chain) -> bool:
            return False

    dispatcher = MessageDispatcher(_FakePlugin(_FailContext()))
    ok = asyncio.run(dispatcher.send_text("qq_official:FriendMessage:abc", "hi"))
    assert ok is False
