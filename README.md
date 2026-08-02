# AstrBot Monitor Plugin v3

> 基于 monitor ver3.x 构建的 Steam CS2 库存监控器插件（plan-v3 完整实现）

## 项目简介

运行在 AstrBot 框架内的 Steam CS2 库存监控系统：支持多账号分层定时爬取、四类差异检测（新增/移除/修改/交换）、库存活动分类，并通过 QQ Bot 按可配置间隔自动批量推送变化消息（支持文生图渲染）。未经监控的新库存也可通过 `/getinventory` 随时查询。

## 核心特性

- ✅ **全异步架构**：httpx + SQLAlchemy asyncio + aiosqlite，不阻塞 AstrBot 事件循环
- ✅ **自动变化投递**：定时爬取 → 差异检测 → 消息队列累积 → 定时批量投递到绑定会话
- ✅ **分层调度**：统一间隔或高/中/低频三级独立队列（默认 5/10/20 分钟）
- ✅ **四类差异检测**：added/removed/modified/swapped + 指纹哈希优化 + 活动分类
- ✅ **批量合并投递**：变化事件入内存队列，按 `message_gap` 定时 flush；`/messagegap 0` 立即投递
- ✅ **无变化通知**：监控周期内所有账号均无变化时，可向绑定会话发送"无变化"汇总（`/non-change-message`）
- ✅ **四模式代理检测**：auto / manual / hosts / none，自动检测系统代理与加速器端口
- ✅ **私密库存支持**：`steam_cookie`（steamLoginSecure）配置项
- ✅ **完整库存查询**：`/getinventory` 按 ID 或昵称爬取并投递全部库存报告
- ✅ **软删除/回收站**：`/delaccount` 软删 + `/restoreaccount` 还原 + `--purge` 永久删除
- ✅ **每日快照归档**：按日/按小时归档 + 过期清理 + `/compare` 历史对比图片报告
- ✅ **中文汉化**：8677+ 条饰品名称翻译映射
- ✅ **管理员告警**：账号连续失败达阈值 → 推送到 `admin_umos` 会话
- ✅ **渲染三级降级**：外部 text_to_image 插件 → 内置 `html_render` → 纯文本
- ✅ **数据导入导出**：`/monexport` / `/monimport`（cs2mon 格式）

## 自动消息投递机制

插件启动后立即创建三个后台 asyncio Task：

```
监控循环（每 N 分钟）
  → Steam API 分页爬取库存
  → 加载上次基准快照
  → diff 差异检测（added/removed/modified/swapped）
  → 活动分类（storage_deposit / acquired / disposed 等）
  → 有变化？→ 入队 MessageQueue（按 QQ 会话 + Steam ID 分组累积）
  → 保存新快照 + 变化事件（原子事务）

消息投递循环（每 M 分钟）
  → 出队全部累积事件
  → 按物品名汉化 + 活动摘要
  → ≤150 字？→ 纯文本投递
  → >150 字？→ Jinja2 HTML → html_render 渲染图片 → send_message 投递
```

**生效前提**：账号必须通过 `/addaccount` 添加（自动绑定当前 QQ 会话）。`_conf_schema.json` 预置的 `steam_ids` 未绑定会话，仅监控入库不投递（可通过 `admin_umos` 配置兜底）。`/messagegap` 可动态控制投递间隔（`0` 立即投递累积消息），`/stopmessage off` 暂停投递但监控不停。

## 技术栈

- **AstrBot**: ≥4.16（依赖 astrbot.api：filter / AstrMessageEvent / Star / html_render / send_message）
- **Python**: ≥3.10
- **依赖库**: httpx、sqlalchemy[asyncio]、aiosqlite（requirements.txt）

## 指令一览（17 条）

| 指令 | 用法 | 说明 |
|------|------|------|
| `/addaccount` | `/addaccount <steam_id> [昵称]` | 添加监控账号并绑定当前会话 |
| `/getinventory` | `/getinventory <steam_id\|昵称>` | 爬取全部库存并投递报告（ID 或昵称均可） |
| `/listaccounts` | `/listaccounts` | 列出账号（昵称/频率/库存/失败计数），长列表转图片 |
| `/editgap` | `/editgap <steam_id> <high\|medium\|low>` | 调整账号监控频率 |
| `/stopmessage` | `/stopmessage [on\|off]` | 暂停/恢复消息投递（监控不停） |
| `/stopall` | `/stopall`（管理员） | 停止监控 + 清空队列 + 停止投递 |
| `/startall` | `/startall`（管理员） | 恢复被停止的监控与投递 |
| `/compare` | `/compare <steam_id> <date1> [date2]` | 两个日期归档快照对比（图片报告） |
| `/messagegap` | `/messagegap <minutes>` | 调整投递间隔（1-1440）；0=立即投递累积消息 |
| `/nickname` | `/nickname <steam_id> <昵称>` | 修改账号昵称 |
| `/crap` | `/crap` | 立即触发一轮爬取（与定时轮互斥） |
| `/proxytest` | `/proxytest` | 代理检测 + Steam API 连通性测试 |
| `/delaccount` | `/delaccount <steam_id> [--purge]` | 软删除（回收站）；`--purge` 永久删除（管理员） |
| `/restoreaccount` | `/restoreaccount [steam_id]` | 还原账号；不带参数列出回收站 |
| `/monexport` | `/monexport` | 全量导出 .cs2mon 文件消息 |
| `/monimport` | `/monimport`（管理员，回复文件） | 导入 .cs2mon 数据 |
| `/non-change-message` | `/non-change-message true\|false` | 控制监控周期"无变化"通知开关 |

## 安装指南

1. **安装插件**：将本目录（或打包 zip）通过 AstrBot WebUI 插件管理上传安装（目录名由 metadata.yaml 的 `name` 决定：`monitor_plugin3`）
2. **依赖**：AstrBot 自动安装 `requirements.txt`（httpx / sqlalchemy[asyncio] / aiosqlite）
3. **WebUI 配置**（`_conf_schema.json`）：
   - `steam_ids`：预置账号（推荐用 `/addaccount` 绑定推送会话，否则仅监控不投递）
   - `tiered_scheduling` / `fetch_interval_minutes`：调度模式（默认统一 60 分钟）
   - `message_interval_minutes`：消息合并投递间隔（默认 30 分钟）
   - `proxy`：四模式代理
   - `steam_cookie`：私密库存登录 Cookie（浏览器 F12 复制 steamLoginSecure）
   - `admin_notify`：管理员告警会话与阈值
   - `retention`：数据保留天数与归档调度

**数据目录**：`data/plugin_data/astrbot_plugin_monitor/`（monitor.db + exports/，防更新覆盖）

## 开发与验证

```bash
python validate.py              # 目录/文件/语法/全模块导入检查
python -m pytest tests/         # 单元测试（56 项：diff/parser/formatter/config/imports/inventory）
```

- 测试通过 `tests/fake_astrbot/` 最小 API 桩模拟 AstrBot 加载，无需 AstrBot 环境
- 数据层端到端（用户/快照/差异/原子存储/交换检测/归档/导出导入/回收站/失败计数/分层分组）已在真实 SQLite 上验证
- `tests/test_config.py` 覆盖可变单例注入回归（settings 导入引用在 setup 后立即生效）

## 修复记录

### 主动消息投递链路修复（2026-08-02）

**现象**：定时监控检测到库存变化并写入日志，但未主动推送到 QQ。

**审查结论**：入队链路正常（`bound_umo` 绑定成功、变化事件入队）；问题集中在**投递环节**：

| # | 问题 | 修复 |
|---|------|------|
| P1 | `_message_flush_loop` 启动后先等 `message_interval_minutes`（默认 30 分钟）才首次 flush | 启动后**立即 flush 一次**（处理存量队列），再按间隔循环 |
| P2 | flush 成功数为 0 时无日志 | 每轮都打印结果；空队列打 debug |
| P3 | `send_image` 用 `file_image` 传 `html_render` 返回的 http URL | 智能分支：`http(s)://` → `url_image`，否则 `file_image` |
| P4 | 投递间隔只在循环启动时读取一次，`/messagegap` 修改不生效 | 每轮从 settings 动态读取 |
| P5 | `send_message` 返回 False（平台不匹配）静默 | 记 warning；入队/未绑定会话均输出明确日志 |

**验证**：`tests/test_delivery.py` 4 项回归（文本 Plain 构造 / URL 图片 / 本地图片 / send_message False 不抛异常）+ 完整链路集成验证（入队→flush→dispatch→send_message 收到正确 umo 与 chain）。

### 配置单例注入 bug（2026-08-01）

**现象**：`/addaccount` 预检时报 `'NoneType' object has no attribute 'steam_proxy_mode'`。

**根因**：`core/config.py` 采用"先 `None` 后赋值"模式——各模块 `from ..config import settings` 值拷贝得到的是初始 `None`，`setup_settings(config)` 重新赋值全局变量后模块内引用仍为 `None`。

**修复**：改为**可变单例**模式（`settings = PluginSettings()` 导入即存在；`setup_settings` 只更新内部引用 `settings._c = config`，不重新绑定变量名）。所有属性新增嵌套安全取值与默认值保护。

**测试**：`tests/test_config.py` 3 项回归（导入即非 None / setup 后属性生效 / 从其他模块导入的引用已更新为同一对象）。

## 项目结构

```
monitor-plugin3/
├── metadata.yaml          # 插件元数据（name: monitor_plugin3）
├── main.py                # Star 入口：生命周期 + 17 条指令注册
├── _conf_schema.json      # 配置 Schema（§8）
├── requirements.txt       # httpx / sqlalchemy[asyncio] / aiosqlite
├── validate.py            # 一键验证脚本
│
├── commands/              # 17 条指令实现
│   ├── validators.py      # steam_id / frequency 校验
│   ├── add_account.py     # /addaccount（预检→绑定→建基准快照）
│   ├── get_inventory.py   # 🆕 /getinventory（ID或昵称→爬取→聚合→文本+图片报告）
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
│   ├── non_change_message.py  # /non-change-message（无变化通知开关）
│   └── export_import.py   # /monexport /monimport
│
├── scheduler/
│   ├── monitor.py         # 三个后台循环（监控/投递/维护）+ 锁与告警
│   └── message_queue.py   # (umo, steam_id) 分组缓冲队列
│
├── notifier/
│   ├── formatter.py       # 事件 → 中文文本/报告（汉化）
│   └── dispatcher.py      # QQ 投递 + 管理员告警 + 三级降级 + 报告渲染
│
├── core/
│   ├── config.py          # 可变单例配置适配器（修复 NoneType bug）
│   ├── crawler/           # fetcher/parser/localize/proxy（从 monitor 迁移）
│   ├── detector/diff.py   # 差异检测 + 活动分类
│   └── models/item.py     # Item / ChangeEvent / InventorySnapshot
│
├── db/
│   ├── database.py        # 引擎 + Base + schema 迁移（数据目录插件专属）
│   ├── models.py          # 4 表（bound_umo，无 login_rate_limit）
│   └── repository.py      # LRU 缓存/原子事务/软删/导入导出/umo 绑定
│
├── templates/             # change_report / compare_report / account_list / 🆕 inventory_report
├── translate/             # translation_map.json（8677 条）
└── tests/                 # 56 项单元测试 + fake_astrbot 桩
    ├── fake_astrbot/      # 最小 AstrBot API 桩（无 AstrBot 环境可验证加载）
    ├── test_config.py     # 🆕 配置单例注入回归防护
    ├── test_get_inventory.py  # 🆕 /getinventory 聚合与参数识别
    ├── test_delivery.py      # 🆕 投递链路回归（P3/P5）
    ├── test_non_change_message.py  # 🆕 无变化通知
    ├── test_imports.py    # 导入回归（无 src/residue + 插件加载 + 16 条指令）
    ├── test_diff.py       # 差异检测与活动分类
    ├── test_parser.py     # 库存解析
    └── test_formatter.py  # 事件格式化与汉化
```

## 与计划文档的关系

- `plan-v3.md`：本目录的实现依据（技术架构/模块设计/文件结构/指令规范/验收标准）
- `monitor-plugin2`：上一版中间产物（存在加载 bug 与半成品模块）；`monitor-plugin3` 从 monitor 源仓库直接迁移成熟实现并完成全部阶段

## 许可协议

MIT License

---

**开发者**: Reasonix Team
**版本**: 3.0.0
**最后更新**: 2026-08-01（新增 `/getinventory` + 修复配置单例注入 bug）
