"""/non-change-message 指令与无变化通知测试。"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from monitor_plugin3.notifier.dispatcher import MessageDispatcher, notify_no_change
from monitor_plugin3.notifier.dispatcher import _global_dispatcher, set_dispatcher


class _FakeContext:
    def __init__(self):
        self.sent: list[tuple[str, object]] = []

    async def send_message(self, umo, chain) -> bool:
        self.sent.append((umo, chain))
        return True


def _user(steam_id: str, umo: str | None):
    return SimpleNamespace(steam_id=steam_id, bound_umo=umo)


def _setup_dispatcher() -> tuple[_FakeContext, MessageDispatcher]:
    ctx = _FakeContext()
    dispatcher = MessageDispatcher(SimpleNamespace(context=ctx))
    set_dispatcher(dispatcher)
    return ctx, dispatcher


def test_notify_no_change_sends_to_bound_umos():
    """无变化通知发送给绑定会话。"""
    ctx, dispatcher = _setup_dispatcher()
    users = [
        _user("76561198000000001", "qq_official:FriendMessage:abc"),
        _user("76561198000000002", "qq_official:FriendMessage:abc"),  # 同会话去重
        _user("76561198000000003", "qq_official:FriendMessage:def"),
        _user("76561198000000004", None),  # 未绑定不发送
    ]
    sent = asyncio.run(notify_no_change(users, {"success": 4, "elapsed_sec": 1.2}))
    assert sent == 2  # abc 与 def 两个会话
    umos_sent = {umo for umo, _ in ctx.sent}
    assert umos_sent == {"qq_official:FriendMessage:abc", "qq_official:FriendMessage:def"}
    # 文本内容含"无库存变化"
    text = ctx.sent[0][1].chain[0].text
    assert "无库存变化" in text
    assert "4 个" in text  # 监控账号数
    set_dispatcher(None)


def test_notify_no_change_no_umo_skips():
    """无绑定会话时不发送。"""
    ctx, dispatcher = _setup_dispatcher()
    sent = asyncio.run(notify_no_change([_user("76561198000000001", None)]))
    assert sent == 0
    assert ctx.sent == []
    set_dispatcher(None)


def test_notify_no_change_dispatcher_not_initialized():
    """dispatcher 未初始化时安全返回 0。"""
    set_dispatcher(None)
    sent = asyncio.run(notify_no_change([_user("76561198000000001", "qq_official:FriendMessage:abc")]))
    assert sent == 0


def test_non_change_message_command_switch(monkeypatch):
    """指令参数解析：true/false/查询/非法参数 + save_config 持久化。"""
    from monitor_plugin3.commands.non_change_message import non_change_message
    from astrbot.api.event import AstrMessageEvent
    from astrbot import AstrBotConfig

    # 记录 save_config 被调用（AstrBotConfig 的持久化入口）
    saved_calls = []
    monkeypatch.setattr(AstrBotConfig, "save_config", lambda self: saved_calls.append(True))

    class _FakePlugin:
        def __init__(self):
            self.config = AstrBotConfig({"non_change_message": False})

    async def run(arg):
        plugin = _FakePlugin()
        event = AstrMessageEvent()
        results = []
        async for r in non_change_message(event, arg, plugin):
            results.append(r)
        return plugin, results

    # true → 开启并保存
    plugin, results = asyncio.run(run("true"))
    assert plugin.config["non_change_message"] is True
    assert saved_calls == [True]
    assert "开启" in results[0]["data"]

    # false → 关闭
    plugin, results = asyncio.run(run("false"))
    assert plugin.config["non_change_message"] is False
    assert len(saved_calls) == 2

    # 无参数 → 查询状态
    plugin, results = asyncio.run(run(""))
    assert "关闭" in results[0]["data"]

    # 非法参数
    plugin, results = asyncio.run(run("maybe"))
    assert "参数错误" in results[0]["data"]
