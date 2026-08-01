"""数据导入导出 - /monexport /monimport 指令实现（plan-v3 §7.2 F12）。

- /monexport: 全量数据导出为 .cs2mon 文件消息（对应 Web /api/export）
- /monimport: 导入 .cs2mon 数据（管理员，回复文件消息，对应 Web /api/import）

导出文件保存在 data/plugin_data/astrbot_plugin_monitor/exports/。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import astrbot.api.message_components as Comp
from astrbot.api.event import AstrMessageEvent

from ..db.database import DATA_DIR
from ..db.repository import export_all_data, import_all_data

EXPORT_DIR = DATA_DIR / "exports"


async def mon_export(event: AstrMessageEvent, plugin_instance=None):
    """导出全部数据为 .cs2mon 文件消息。"""
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    yield event.plain_result("⏳ 正在导出全量数据...")

    try:
        data = await export_all_data()
        filename = f"monitor_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.cs2mon"
        filepath = EXPORT_DIR / filename
        filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        yield event.plain_result(f"❌ 导出失败：{str(exc)[:200]}")
        return

    user_count = data.get("user_count", 0)
    size_kb = filepath.stat().st_size / 1024

    try:
        chain = [Comp.File(file=str(filepath), name=filename)]
        yield event.chain_result(chain)
    except Exception as exc:
        yield event.plain_result(f"⚠️ 文件消息发送失败：{str(exc)[:100]}\n文件已保存：{filepath}")

    yield event.plain_result(
        f"✅ 导出完成\n\n"
        f"📄 文件：{filename}\n"
        f"👥 用户数：{user_count}\n"
        f"💾 大小：{size_kb:.1f} KB\n\n"
        f"💡 新环境导入：/monimport（管理员，回复该文件）"
    )


async def mon_import(event: AstrMessageEvent, plugin_instance=None):
    """导入 .cs2mon 数据（管理员）。需回复包含 .cs2mon 文件的消息。"""
    # 从回复的消息中提取文件
    file_path = None
    try:
        for msg in event.get_messages():
            if getattr(msg, "type", "") == "file" or hasattr(msg, "file"):
                file_path = getattr(msg, "file", None)
                if file_path:
                    break
    except Exception:
        pass

    if not file_path:
        yield event.plain_result(
            "❌ 未找到 .cs2mon 文件\n\n"
            "用法：回复一条包含 .cs2mon 文件的消息并输入 /monimport"
        )
        return

    if not str(file_path).lower().endswith(".cs2mon"):
        yield event.plain_result("❌ 文件格式不正确，需要 .cs2mon 扩展名")
        return

    yield event.plain_result("⏳ 正在导入数据，请稍候...")

    try:
        path = Path(str(file_path))
        data = json.loads(path.read_text(encoding="utf-8"))
        stats = await import_all_data(data)
    except ValueError as exc:
        yield event.plain_result(f"❌ 导入失败：{exc}")
        return
    except Exception as exc:
        yield event.plain_result(f"❌ 导入失败：{str(exc)[:200]}")
        return

    yield event.plain_result(
        f"✅ 导入完成\n\n"
        f"🆕 新建账号：{stats.get('created', 0)} 个\n"
        f"🔄 更新账号：{stats.get('updated', 0)} 个\n"
        f"⏭️ 跳过：{stats.get('skipped', 0)} 个\n\n"
        f"💡 已导入账号的会话绑定将保持为空，请用 /addaccount 重新绑定推送"
    )
