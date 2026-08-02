"""AstrBot Monitor Plugin v3 — Star 入口（完整版）

基于 monitor ver3.x 构建（plan-v3），通过 QQ Bot 主动推送 CS2 库存变化消息。
- 15 条指令（§7）：账号管理 / 频率 / 投递控制 / 对比 / 手动爬取 / 连通性测试 / 导入导出
- 三个后台循环（§5.3）：监控循环 / 消息投递循环 / 每日维护循环
- 生命周期：`terminate()` 统一取消 Task、关闭 httpx 客户端与数据库引擎（NF2）

注意（重要）：
- 本模块位于插件包根，包内导入一律使用单点相对导入（`.commands.xxx`），
  不可使用 `..xxx`（会解析到 data.plugins.core 导致加载失败）。
- `__init__` 在 AstrBot 事件循环内执行，禁止 asyncio.run；全部异步初始化
  委托给延迟任务。
"""

from __future__ import annotations

import asyncio
from typing import Any

from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star

from .core.config import setup_settings
from .db.database import close_db, init_db
from .notifier.dispatcher import MessageDispatcher, set_dispatcher
from .scheduler.message_queue import MessageQueue
from .scheduler.monitor import MonitorController, set_message_queue


class MonitorPlugin(Star):
    """Steam CS2 库存监控插件 v3"""

    def __init__(self, context: Context, config: dict[str, Any]):
        super().__init__(context)
        self.config = config  # _conf_schema.json 注入（AstrBotConfig，dict 子类）

        # 配置适配器（core 层通过 settings 单例读取）
        setup_settings(config)

        # 消息队列 + 调度控制器 + 分发器
        self._queue = MessageQueue()
        set_message_queue(self._queue)
        self.monitor_controller = MonitorController(self)
        self.dispatcher = MessageDispatcher(self)
        set_dispatcher(self.dispatcher)

        # 投递开关（/stopmessage 控制）
        self._message_enabled = True
        # 整体运行开关（/stopall 控制）
        self._monitor_enabled = True

        # 延迟初始化：DB init + 预置账号 + 启动后台循环
        asyncio.create_task(self._startup_initializer())

    # ==================== 生命周期 ====================

    async def _startup_initializer(self) -> None:
        """启动初始化流程（异步非阻塞）。"""
        try:
            # 1. 数据库初始化（建表 + schema 迁移）
            await init_db()
            logger.info("数据库初始化完成：%s", "monitor.db")

            # 2. 预置账号（配置 steam_ids；无绑定会话，仅监控不投递）
            from .db.repository import init_default_users
            await init_default_users()

            # 3. 启动三个后台循环
            await self.monitor_controller.start()

            logger.info("Monitor Plugin v3 已完全启动")
        except Exception as exc:
            logger.exception("启动初始化失败：%s", exc)

    async def terminate(self) -> None:
        """取消所有后台任务，优雅退出（NF2 优雅终止）。"""
        try:
            logger.info("正在停止 Monitor Plugin v3...")
            self._monitor_enabled = False
            self._message_enabled = False

            # 停止监控/投递/维护三个后台循环
            await self.monitor_controller.stop()

            # 清空消息队列
            self._queue.clear()

            # 关闭 httpx 客户端
            from .core.crawler.fetcher import close_client
            await close_client()

            # 关闭数据库引擎
            await close_db()

            logger.info("Monitor Plugin v3 已成功停止")
        except Exception as exc:
            logger.exception("停止过程中出现异常：%s", exc)

    # ==================== 指令 Handler（委托 commands/） ====================

    @filter.command("addaccount")
    async def cmd_add_account(self, event: AstrMessageEvent, steam_id: str = "", nickname: str = ""):
        """添加监控目标账号"""
        from .commands.add_account import add_account
        async for result in add_account(event, steam_id.strip(), nickname.strip(), self):
            yield result

    @filter.command("listaccounts")
    async def cmd_list_accounts(self, event: AstrMessageEvent):
        """列出所有监控账号"""
        from .commands.list_accounts import list_accounts
        async for result in list_accounts(event, self):
            yield result

    @filter.command("editgap")
    async def cmd_edit_gap(self, event: AstrMessageEvent, steam_id: str = "", frequency: str = ""):
        """调整指定账号的监控频率"""
        from .commands.edit_gap import edit_gap
        async for result in edit_gap(event, steam_id.strip(), frequency.strip()):
            yield result

    @filter.command("stopmessage")
    async def cmd_stop_message(self, event: AstrMessageEvent, action: str = ""):
        """暂停/恢复消息投递（监控不停）"""
        from .commands.stop_message import stop_message
        async for result in stop_message(event, action.strip(), self):
            yield result

    @filter.command("stopall")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def cmd_stop_all(self, event: AstrMessageEvent):
        """停止所有监控任务和消息投递（管理员）"""
        from .commands.stop_all import stop_all
        message = await stop_all(self)
        yield event.plain_result(message)

    @filter.command("startall")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def cmd_start_all(self, event: AstrMessageEvent):
        """恢复被停止的监控和投递（管理员）"""
        from .commands.stop_all import start_all
        message = await start_all(self)
        yield event.plain_result(message)

    @filter.command("compare")
    async def cmd_compare(self, event: AstrMessageEvent, steam_id: str = "", date1: str = "", date2: str = ""):
        """对比两个日期的归档快照差异（图片报告）"""
        from .commands.compare import compare
        async for result in compare(event, steam_id.strip(), date1.strip(), date2.strip(), self):
            yield result

    @filter.command("messagegap")
    async def cmd_message_gap(self, event: AstrMessageEvent, minutes: str = ""):
        """调整消息投递间隔（0=立即投递）"""
        from .commands.message_gap import message_gap
        async for result in message_gap(event, minutes.strip(), self):
            yield result

    @filter.command("nickname")
    async def cmd_nickname(self, event: AstrMessageEvent, steam_id: str = "", nickname: str = ""):
        """修改监控账号昵称"""
        from .commands.nickname import nickname
        async for result in nickname(event, steam_id.strip(), nickname.strip()):
            yield result

    @filter.command("crap")
    async def cmd_crawl_now(self, event: AstrMessageEvent):
        """立即触发一轮爬取"""
        from .commands.crawl_now import crawl_now
        async for result in crawl_now(event, self):
            yield result

    @filter.command("proxytest")
    async def cmd_proxy_test(self, event: AstrMessageEvent):
        """代理检测与 Steam API 连通性测试"""
        from .commands.proxy_test import proxy_test
        async for result in proxy_test(event, self):
            yield result

    @filter.command("delaccount")
    async def cmd_del_account(self, event: AstrMessageEvent, steam_id: str = ""):
        """软删除账号（进入回收站）；--purge 永久删除"""
        from .commands.del_account import del_account
        async for result in del_account(event, steam_id.strip(), self):
            yield result

    @filter.command("restoreaccount")
    async def cmd_restore_account(self, event: AstrMessageEvent, steam_id: str = ""):
        """从回收站还原账号；不带参数列出回收站"""
        from .commands.restore_account import restore_account
        async for result in restore_account(event, steam_id.strip()):
            yield result

    @filter.command("non-change-message")
    async def cmd_non_change_message(self, event: AstrMessageEvent, arg: str = ""):
        """控制监控周期"无变化"通知开关（true/false）"""
        from .commands.non_change_message import non_change_message
        async for result in non_change_message(event, arg.strip(), self):
            yield result

    @filter.command("getinventory")
    async def cmd_get_inventory(self, event: AstrMessageEvent, param: str = ""):
        """爬取全部库存内容并投递（按 ID 或昵称）"""
        from .commands.get_inventory import get_inventory
        async for result in get_inventory(event, param.strip(), self):
            yield result

    @filter.command("monexport")
    async def cmd_mon_export(self, event: AstrMessageEvent):
        """导出全部数据为 .cs2mon 文件"""
        from .commands.export_import import mon_export
        async for result in mon_export(event, self):
            yield result

    @filter.command("monimport")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def cmd_mon_import(self, event: AstrMessageEvent):
        """导入 .cs2mon 数据（管理员，需回复文件）"""
        from .commands.export_import import mon_import
        async for result in mon_import(event, self):
            yield result
