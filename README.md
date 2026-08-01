# AstrBot Monitor Plugin v3

> 基于 monitor ver3.x 构建的 Steam CS2 库存监控器插件（plan-v3 完整实现）

## 项目简介

运行在 AstrBot 框架内的 Steam CS2 库存监控系统：支持多账号分层定时爬取、四类差异检测（新增/移除/修改/交换）、库存活动分类，并通过 QQ Bot 按可配置间隔批量推送变化消息（支持文生图渲染）。

## 核心特性

- ✅ **全异步架构**：httpx + SQLAlchemy asyncio + aiosqlite，不阻塞 AstrBot 事件循环
- ✅ **分层调度**：统一间隔或高/中/低频三级独立队列（默认 5/10/20 分钟）
- ✅ **四类差异检测**：added/removed/modified/swapped + 指纹哈希优化 + 活动分类
- ✅ **批量合并投递**：变化事件入内存队列，按 message_gap 定时 flush 到绑定会话
- ✅ **四模式代理检测**：auto/manual/hosts/none，自动检测系统代理与加速器端口
- ✅ **私密库存支持**：steamLoginSecure cookie（`steam_cookie` 配置项）
- ✅ **软删除/回收站**：`/delaccount` 软删 + `/restoreaccount` 还原 + `--purge` 永久删除
- ✅ **每日快照归档**：按日/按小时归档 + 过期清理 + `/compare` 历史对比图片报告
- ✅ **中文汉化**：8677+ 条饰品名称翻译映射
- ✅ **管理员告警**：账号连续失败达阈值 → 推送到 admin_umos 会话
- ✅ **渲染三级降级**：外部 text_to_image 插件 → 内置 html_render → 纯文本
- ✅ **数据导入导出**：`/monexport` / `/monimport`（cs2mon 格式）

## 技术栈

- **AstrBot**: ≥4.16（依赖 astrbot.api：filter / AstrMessageEvent / Star / html_render / send_message）
- **Python**: ≥3.10
- **依赖库**: httpx、sqlalchemy[asyncio]、aiosqlite（requirements.txt）

## 指令一览（15 条）

| 指令 | 用法 | 说明 |
|------|------|------|
| `/addaccount` | `/addaccount <steam_id> [昵称]` | 添加监控账号并绑定当前会话 |
| `/listaccounts` | `/listaccounts` | 列出账号（昵称/频率/库存/失败计数），长列表转图片 |
| `/editgap` | `/editgap <steam_id> <high\|medium\|low>` | 调整账号监控频率 |
| `/stopmessage` | `/stopmessage [on\|off]` | 暂停/恢复消息投递（监控不停） |
| `/stopall` | `/stopall`（管理员） | 停止监控 + 清空队列 + 停止投递 |
| `/startall` | `/startall`（管理员） | 恢复被停止的监控与投递 |
| `/compare` | `/compare <steam_id> <date1> [date2]` | 两个日期归档快照对比（图片报告） |
| `/messagegap` | `/messagegap <minutes>` | 调整投递间隔（1-1440）；0=立即投递 |
| `/nickname` | `/nickname <steam_id> <昵称>` | 修改账号昵称 |
| `/crap` | `/crap` | 立即触发一轮爬取（与定时轮互斥） |
| `/proxytest` | `/proxytest` | 代理检测 + Steam API 连通性测试 |
| `/delaccount` | `/delaccount <steam_id> [--purge]` | 软删除（回收站）；`--purge` 永久删除（管理员） |
| `/restoreaccount` | `/restoreaccount [steam_id]` | 还原账号；不带参数列出回收站 |
| `/monexport` | `/monexport` | 全量导出 .cs2mon 文件消息 |
| `/monimport` | `/monimport`（管理员，回复文件） | 导入 .cs2mon 数据 |

## 安装指南

1. **安装插件**：将本目录（或打包 zip）通过 AstrBot WebUI 插件管理上传安装（目录名由 metadata.yaml 的 `name` 决定：`monitor_plugin3`）
2. **依赖**：AstrBot 自动安装 `requirements.txt`（httpx / sqlalchemy[asyncio] / aiosqlite）
3. **WebUI 配置**（`_conf_schema.json`）：
   - `steam_ids`：预置账号（推荐用 `/addaccount` 绑定推送会话）
   - `tiered_scheduling` / `fetch_interval_minutes`：调度模式
   - `proxy`：四模式代理
   - `steam_cookie`：私密库存登录 Cookie
   - `admin_notify`：管理员告警会话与阈值
   - `retention`：数据保留天数与归档调度

**数据目录**：`data/plugin_data/astrbot_plugin_monitor/`（monitor.db + exports/，防更新覆盖）

## 开发与验证

```bash
python validate.py              # 目录/文件/语法/全模块导入检查
python -m pytest tests/         # 单元测试（41 项：diff/parser/formatter/加载回归）
```

- 测试通过 `tests/fake_astrbot/` 最小 API 桩模拟 AstrBot 加载，无需 AstrBot 环境
- 数据层端到端（用户/快照/差异/原子存储/归档/导出导入/回收站）已在真实 SQLite 上验证

## 项目结构

```
monitor-plugin3/
├── metadata.yaml          # 插件元数据（name: monitor_plugin3）
├── main.py                # Star 入口：生命周期 + 15 条指令注册
├── _conf_schema.json      # 配置 Schema（§8）
├── requirements.txt       # httpx / sqlalchemy[asyncio] / aiosqlite
├── validate.py            # 一键验证脚本
│
├── commands/              # 15 条指令实现
│   ├── validators.py      # steam_id / frequency 校验
│   ├── add_account.py     # /addaccount（预检→绑定→建基准快照）
│   ├── edit_gap.py        # /editgap
│   ├── stop_message.py    # /stopmessage
│   ├── stop_all.py        # /stopall /startall
│   ├── compare.py         # /compare（日期归档对比）
│   ├── message_gap.py     # /messagegap（0=立即投递）
│   ├── nickname.py        # /nickname
│   ├── crawl_now.py       # /crap
│   ├── proxy_test.py      # /proxytest
│   ├── list_accounts.py   # /listaccounts（长列表转图片）
│   ├── del_account.py     # /delaccount（软删/--purge）
│   ├── restore_account.py # /restoreaccount（回收站）
│   └── export_import.py   # /monexport /monimport
│
├── scheduler/
│   ├── monitor.py         # 三个后台循环（监控/投递/维护）+ 锁与告警
│   └── message_queue.py   # (umo, steam_id) 分组缓冲队列
│
├── notifier/
│   ├── formatter.py       # 事件 → 中文文本/报告（汉化）
│   └── dispatcher.py      # QQ 投递 + 管理员告警 + 三级降级
│
├── core/
│   ├── config.py          # AstrBotConfig 适配器（settings 单例）
│   ├── crawler/           # fetcher/parser/localize/proxy（从 monitor 迁移）
│   ├── detector/diff.py   # 差异检测 + 活动分类
│   └── models/item.py     # Item / ChangeEvent / InventorySnapshot
│
├── db/
│   ├── database.py        # 引擎 + Base + schema 迁移（数据目录插件专属）
│   ├── models.py          # 4 表（bound_umo，无 login_rate_limit）
│   └── repository.py      # LRU 缓存/原子事务/软删/导入导出/umo 绑定
│
├── templates/             # change_report / compare_report / account_list
├── translate/             # translation_map.json（8677 条）
└── tests/                 # 41 项单元测试 + fake_astrbot 桩
```

## 与计划文档的关系

- `plan-v3.md`：本目录的实现依据（技术架构/模块设计/文件结构/指令规范/验收标准）
- `monitor-plugin2`：上一版中间产物（存在加载 bug 与半成品模块）；`monitor-plugin3` 从 monitor 源仓库直接迁移成熟实现并完成全部阶段

## 许可协议

MIT License

---

**开发者**: Reasonix Team
**版本**: 3.0.0
**最后更新**: 2026-07-31
