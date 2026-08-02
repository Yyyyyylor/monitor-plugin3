"""插件完整加载测试 — 验证 main.py 与全部模块可导入（模拟 AstrBot 加载）。

关键点（plan-v3 Phase 0 的报错根因回归）：
1. main.py 必须使用包内相对导入（.commands/.core/.db 等），
   不能出现 `..core`（会解析到 data.plugins.core 导致加载失败）
2. 全部模块不得残留 `from src.xxx`（monitor 源绝对导入）
"""

from __future__ import annotations

import importlib
import pathlib
import re


def test_no_src_absolute_imports():
    """全目录不得残留 monitor 源的 src.xxx 绝对导入。"""
    root = pathlib.Path(__file__).resolve().parent.parent
    offenders = []
    for py in root.rglob("*.py"):
        if "fake_astrbot" in str(py):
            continue
        for lineno, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            if re.match(r"^\s*(from|import)\s+src", line):
                offenders.append(f"{py.relative_to(root)}:{lineno}: {line.strip()}")
    assert not offenders, f"发现 monitor 源绝对导入残留:\n" + "\n".join(offenders)


def test_no_dotdot_imports_in_root_modules():
    """插件根目录模块（main.py 等）不得使用 `..` 相对导入（包根无上层包）。"""
    root = pathlib.Path(__file__).resolve().parent.parent
    offenders = []
    for py in root.glob("*.py"):
        for lineno, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            if re.match(r"^\s*(from|import)\s+\.\.", line):
                offenders.append(f"{py.name}:{lineno}: {line.strip()}")
    assert not offenders, f"包根出现 .. 相对导入:\n" + "\n".join(offenders)


def test_main_plugin_loadable(monkeypatch):
    """main.py 的 MonitorPlugin 可实例化（模拟 AstrBot 注入 config）。

    阻止后台任务真实启动：替换 create_task 为 no-op。
    """
    from monitor_plugin3 import main as main_module
    from astrbot.api.star import Context

    def _noop(coro, *args, **kwargs):
        return None

    monkeypatch.setattr(main_module.asyncio, "create_task", _noop)

    plugin = main_module.MonitorPlugin(Context(), {})
    assert hasattr(plugin, "config")
    assert hasattr(plugin, "monitor_controller")
    assert hasattr(plugin, "dispatcher")
    assert hasattr(plugin, "_queue")

    # 指令 handler 已注册（15 条）
    handlers = [m for m in dir(plugin) if m.startswith("cmd_")]
    assert len(handlers) >= 15, f"指令 handler 数量不足: {len(handlers)}"

    # terminate() 可调用（优雅退出路径不抛错）
    import asyncio
    asyncio.run(plugin.terminate())


def test_all_command_modules_importable():
    """全部指令模块可导入。"""
    modules = [
        "add_account", "edit_gap", "stop_message", "stop_all",
        "compare", "message_gap", "nickname", "crawl_now",
        "proxy_test", "del_account", "restore_account",
        "export_import", "list_accounts", "get_inventory",
        "non_change_message",
    ]
    for m in modules:
        importlib.import_module(f"monitor_plugin3.commands.{m}")
