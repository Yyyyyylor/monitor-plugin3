# Changelog

本项目的所有重要变更均记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)（SemVer）。

## [Unreleased]

### 计划中
- Phase 5 可选项：外部 text_to_image 插件对接联调、Plugin Pages 监控仪表盘（见 plan-v3 §14）

## [3.3.0] - 2026-08-02

### Added
- 新增 `/non-change-message true|false` 指令：控制监控周期内所有账号均无库存变化时，是否向绑定会话发送"无变化"汇总通知（`/non-change-message` 不带参数可查询当前状态）
- `_conf_schema.json` 新增 `non_change_message` bool 配置项（默认 `false`），支持 WebUI 与指令持久化（`config.save_config()`）双重控制
- `notifier/dispatcher.py` 新增 `notify_no_change()`：监控周期无变化时按 `bound_umo` 会话**去重**投递（一个 QQ 会话监控多个账号仅发一条）
- `scheduler/monitor.py` 监控周期末尾触发逻辑：当 `success > 0` 且 `total_events == 0` 且开关开启时调用 `notify_no_change`
- 新增 `tests/test_non_change_message.py`（4 项：会话去重 / 无绑定跳过 / dispatcher 未初始化安全 / 指令参数解析与持久化）

### Changed
- 指令总数增至 **17 条**

## [3.2.0] - 2026-08-02

### Added
- 新增 `/getinventory <steam_id|昵称>` 指令：按 Steam ID（17 位数字）或监控账号昵称爬取全部库存，投递"文本摘要 + 图片报告"（`inventory_report.html`，按饰品聚合、汉化名称、超过 300 种自动截断）到当前会话
- `templates/inventory_report.html` 库存报告模板（支持亮/暗主题）
- 新增 `tests/test_get_inventory.py`（4 项：聚合排序与汉化 / 截断 / 空库存 / ID 与昵称识别）
- 新增 `tests/test_delivery.py`（4 项：文本 Plain 构造 / http URL 图片 / 本地图片 / send_message False 不抛异常）

### Fixed
- **主动消息投递链路**（P1–P5）：
  - P1：`_message_flush_loop` 启动后先等 `message_interval_minutes`（默认 30 分钟）才首次 flush → 改为启动后**立即 flush 一次**（处理存量队列），再按间隔循环
  - P2：flush 成功数为 0 时无日志 → 每轮打印结果，空队列打 debug
  - P3：`send_image` 用 `file_image` 传 `html_render` 返回的 http URL → 智能分支：`http(s)://` 用 `url_image`，本地路径用 `file_image`
  - P4：投递间隔只在循环启动时读取 → 每轮从 `settings` 动态读取（`/messagegap` 修改即时生效）
  - P5：`send_message` 返回 False（平台不匹配）静默 → 记 warning；入队/未绑定会话输出明确日志

## [3.1.0] - 2026-08-01

### Added
- **monitor-plugin3 完整重构版**：从 monitor 源仓库迁移成熟实现（plan-v3 Phase 0–4 全部完成）
- 完整指令体系（16 条）：账号管理（addaccount/listaccounts/editgap/nickname/delaccount/restoreaccount）、投递控制（stopmessage/stopall/startall/messagegap）、对比查询（compare/crap/proxytest）、导入导出（monexport/monimport）
- 三个后台 asyncio 循环（监控 / 消息投递 / 每日维护），替换 APScheduler（plan-v3 §2 决策树）
- HTML 模板：`change_report.html` / `compare_report.html` / `account_list.html`
- 测试体系：从 monitor/tests 迁移 `test_diff.py` / `test_parser.py`，改造 `test_formatter.py`；新增 `tests/fake_astrbot/` 最小 API 桩（无需 AstrBot 环境即可验证插件加载）；新增 `tests/test_imports.py` 导入回归防护；`validate.py` 一键验证脚本

### Fixed
- **插件加载失败**（报错：`No module named 'data.plugins.core'`）：main.py 与 core 层残留 monitor 源 `from src.xxx` / `..xxx` 绝对导入 → 全部改为包内相对导入
- `db/models.py` 使用未定义的 `Base` 及 `db/database.py` 循环导入 → 重写（`Base` 定义于 database.py）
- `db/repository.py` 的 `SessionLocal` 未定义、`row[0]` 取值错误、伪原子事务、缺导入导出 → 从 monitor 源迁移成熟实现（LRU 快照缓存 / 原子事务 / 软删除三件套 / cs2mon 导入导出）
- `scheduler/monitor.py` 停止逻辑失效（`_global_running` 永不置 False）、每日维护仅执行一次 → 重写为 `stop_flag` + 三个可取消 Task
- `notifier/dispatcher.py` 发送逻辑缺失（`send_message` 全部注释、`notify_admin` 占位）→ 重写为真实投递 + 管理员告警 + 三级渲染降级
- `_conf_schema.json` 与 `metadata.yaml` 对齐 plan-v3 §8/§9

### Changed
- 数据目录规范为 AstrBot 的 `data/plugin_data/astrbot_plugin_monitor/`（§NF4，防更新覆盖）

## [3.0.0] - 2026-07-31

### Added
- monitor-plugin2 基线版：依据 plan-v3 完成核心链路迁移（爬取 → 差异检测 → 消息队列 → QQ 投递）并注册 9 条指令

### Known Issues
- **插件无法在 AstrBot 中加载**：main.py 使用 `from ..core.config`（解析到不存在的 `data.plugins.core`）及 `from commands.xxx` 绝对导入；`db/models.py` 未定义 `Base`
- 大量模块为半成品（`dispatcher` 发送逻辑注释、`notify_admin` 占位、多个指令占位符）
- **该版本存在缺陷，未对外发布**；功能完整实现见 3.1.0
