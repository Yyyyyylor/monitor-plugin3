# AstrBot Monitor Plugin v3

> Steam CS2 inventory monitor plugin built on monitor ver3.x (full plan-v3 implementation)

**English** | **[中文](README.md)**

## Introduction

A Steam CS2 inventory monitoring system running inside the AstrBot framework: multi-account tiered scheduled crawling, four kinds of diff detection (added / removed / modified / swapped), inventory activity classification, and automatic batched push of change messages to a QQ bot at configurable intervals (with text-to-image rendering). Unmonitored new inventories can also be queried anytime via `/getinventory`.

## Key Features

- ✅ **Fully async architecture**: httpx + SQLAlchemy asyncio + aiosqlite, never blocks the AstrBot event loop
- ✅ **Automatic change delivery**: scheduled crawl → diff detection → message queue accumulation → batched delivery to bound sessions
- ✅ **Tiered scheduling**: unified interval or high/medium/low three-tier independent queues (default 5/10/20 minutes)
- ✅ **Four kinds of diff detection**: added / removed / modified / swapped + fingerprint hash optimization + activity classification
- ✅ **Batched merged delivery**: change events enter an in-memory queue and flush on `message_gap` timer; `/messagegap 0` delivers immediately
- ✅ **No-change notification**: when no account changed during a monitoring cycle, an optional "no change" summary can be sent to bound sessions (`/non-change-message`)
- ✅ **Four-mode proxy detection**: auto / manual / hosts / none, auto-detects system proxy and accelerator ports
- ✅ **Private inventory support**: `steam_cookie` (`steamLoginSecure`) config option
- ✅ **Full inventory query**: `/getinventory` crawls by ID or nickname and delivers a complete inventory report
- ✅ **Soft delete / recycle bin**: `/delaccount` soft deletes + `/restoreaccount` restores + `--purge` permanent delete
- ✅ **Daily snapshot archiving**: per-day / per-hour archive + expiration cleanup + `/compare` historical comparison image report
- ✅ **Chinese localization**: 8677+ item name translation mappings
- ✅ **Admin alerts**: account consecutive failures reach threshold → push to `admin_umos` session
- ✅ **Three-level rendering fallback**: external text_to_image plugin → built-in `html_render` → plain text
- ✅ **Data export/import**: `/monexport` / `/monimport` (cs2mon format)

## Automatic Message Delivery

Three background asyncio Tasks are created immediately after the plugin starts:

```
Monitor loop (every N minutes)
  → fetch inventory via Steam API with pagination
  → load last baseline snapshot
  → diff detection (added/removed/modified/swapped)
  → activity classification (storage_deposit / acquired / disposed, etc.)
  → any change? → enqueue MessageQueue (grouped by QQ session + Steam ID)
  → save new snapshot + change events (atomic transaction)

Delivery loop (every M minutes)
  → dequeue all accumulated events
  → localize item names + activity summary
  → ≤150 chars? → deliver as plain text
  → >150 chars? → Jinja2 HTML → html_render to image → send_message delivery
```

**Prerequisite**: accounts must be added via `/addaccount` (auto-binds to the current QQ session). `steam_ids` preset in `_conf_schema.json` are not bound to a session — they are only monitored and stored, not delivered (can be covered by `admin_umos` config as a fallback). `/messagegap` dynamically controls the delivery interval (`0` delivers accumulated messages immediately); `/stopmessage off` pauses delivery but monitoring continues.

## Tech Stack

- **AstrBot**: ≥4.16 (depends on astrbot.api: filter / AstrMessageEvent / Star / html_render / send_message)
- **Python**: ≥3.10
- **Libraries**: httpx, sqlalchemy[asyncio], aiosqlite (requirements.txt)

## Commands (17)

| Command | Usage | Description |
|---------|-------|-------------|
| `/addaccount` | `/addaccount <steam_id> [nickname]` | Add a monitored account and bind it to the current session |
| `/getinventory` | `/getinventory <steam_id\|nickname>` | Crawl the full inventory and deliver a report (by ID or nickname) |
| `/listaccounts` | `/listaccounts` | List accounts (nickname/frequency/inventory/failure count), long lists rendered as images |
| `/editgap` | `/editgap <steam_id> <high\|medium\|low>` | Adjust an account's monitoring frequency |
| `/stopmessage` | `/stopmessage [on\|off]` | Pause/resume message delivery (monitoring continues) |
| `/stopall` | `/stopall` (admin) | Stop monitoring + clear queue + stop delivery |
| `/startall` | `/startall` (admin) | Resume stopped monitoring and delivery |
| `/compare` | `/compare <steam_id> <date1> [date2]` | Compare archived snapshots of two dates (image report) |
| `/messagegap` | `/messagegap <minutes>` | Adjust delivery interval (1-1440); 0 = deliver accumulated messages immediately |
| `/nickname` | `/nickname <steam_id> <nickname>` | Rename an account |
| `/crap` | `/crap` | Trigger one crawl round immediately (mutually exclusive with the scheduled loop) |
| `/proxytest` | `/proxytest` | Proxy detection + Steam API connectivity test |
| `/delaccount` | `/delaccount <steam_id> [--purge]` | Soft delete (recycle bin); `--purge` permanently deletes (admin) |
| `/restoreaccount` | `/restoreaccount [steam_id]` | Restore an account; without args lists the recycle bin |
| `/monexport` | `/monexport` | Export all data as .cs2mon file messages |
| `/monimport` | `/monimport` (admin, reply to file) | Import .cs2mon data |
| `/non-change-message` | `/non-change-message true\|false` | Toggle the "no change" notification per monitoring cycle |

## Installation

1. **Install the plugin**: upload this directory (or a zipped package) via the AstrBot WebUI plugin manager (directory name is determined by `metadata.yaml` `name`: `monitor_plugin3`)
2. **Dependencies**: AstrBot installs `requirements.txt` automatically (httpx / sqlalchemy[asyncio] / aiosqlite)
3. **WebUI configuration** (`_conf_schema.json`):
   - `steam_ids`: preset accounts (use `/addaccount` to bind push sessions; otherwise monitored but not delivered)
   - `tiered_scheduling` / `fetch_interval_minutes`: scheduling mode (default unified 60 minutes)
   - `message_interval_minutes`: message merge delivery interval (default 30 minutes)
   - `proxy`: four-mode proxy
   - `steam_cookie`: private inventory login cookie (copy `steamLoginSecure` via F12 in the browser)
   - `admin_notify`: admin alert session and thresholds
   - `retention`: data retention days and archive scheduling

**Data directory**: `data/plugin_data/astrbot_plugin_monitor/` (monitor.db + exports/, protected from update overwrite)

## Development & Verification

```bash
python validate.py              # directory/file/syntax/full-module import checks
python -m pytest tests/         # unit tests (56 items: diff/parser/formatter/config/imports/inventory)
```

- Tests simulate AstrBot loading via the minimal API stub in `tests/fake_astrbot/` — no AstrBot environment required
- Data-layer end-to-end (users/snapshots/diffs/atomic storage/swapped detection/archive/export-import/recycle bin/failure count/tiered grouping) verified on real SQLite
- `tests/test_config.py` covers mutable-singleton injection regression (settings import references take effect immediately after setup)

## Fix History

### Concurrent monitoring & schedule interval fix (2026-08-02, v3.3.1)

**Symptoms**: logs showed the same account crawled twice within 0.2 seconds, multiple "cycle complete" entries, and the message delivery loop triggering multiple times within 1 second; also the monitor loop only ran once at startup and then nothing for a long time.

**Root causes**:
1. **Multiple instance concurrency**: when AstrBot hot-reloads / repeatedly loads and produces multiple plugin instances, the old and new instances run monitor loops concurrently. Since old/new instances are different module objects (each with its own `_monitor_lock`), the module-level lock cannot serialize them.
2. **Interval not updated**: the unified/tiered/maintenance loops only read `interval` once at startup; WebUI config changes do not take effect.

**Fixes**:
1. **Controller registry shared across module instances** (via `sys.modules` namespace): when a new controller starts, it automatically stops still-running old controllers → only one monitor controller at any time.
2. All three background loops **read the interval dynamically each round** + log next-run time.
3. No-change notification (`non_change_message`) is on by default, and is no longer wrongly sent when `/stopmessage off` pauses delivery.

**Verification**: `tests/test_monitor_controller.py` 3 regressions (single-instance registration / new-stops-old / stop idempotent) + simulated run confirming interval 60→5 minutes takes effect dynamically.

### Proactive message delivery fix (2026-08-02)

**Symptom**: scheduled monitoring detected inventory changes and wrote logs, but did not proactively push to QQ.

**Review conclusion**: the enqueue chain is normal (`bound_umo` bound successfully, change events enqueued); the problem is concentrated in the **delivery stage**:

| # | Issue | Fix |
|---|-------|-----|
| P1 | `_message_flush_loop` waits `message_interval_minutes` (default 30 min) before first flush | **flush once immediately at startup** (handles leftover queue), then loop on the interval |
| P2 | No log when flush success count is 0 | print results every round; log debug on empty queue |
| P3 | `send_image` passed the http URL returned by `html_render` to `file_image` | smart branch: `http(s)://` → `url_image`, otherwise `file_image` |
| P4 | Delivery interval only read once at loop startup; `/messagegap` changes did not take effect | read dynamically from settings each round |
| P5 | `send_message` returning False (platform mismatch) was silent | log warning; explicit logs for enqueue/unbound-session cases |

**Verification**: `tests/test_delivery.py` 4 regressions (text Plain construction / URL image / local image / send_message False does not throw) + full-chain integration verification (enqueue→flush→dispatch→send_message receives the correct umo and chain).

### Config singleton injection bug (2026-08-01)

**Symptom**: `/addaccount` pre-check threw `'NoneType' object has no attribute 'steam_proxy_mode'`.

**Root cause**: `core/config.py` used an "assign None first, assign later" pattern — modules doing `from ..config import settings` copy the initial `None` value; after `setup_settings(config)` reassigns the global, in-module references remain `None`.

**Fix**: switched to a **mutable singleton** pattern (`settings = PluginSettings()` exists on import; `setup_settings` only updates the internal reference `settings._c = config` without rebinding the variable name). All attributes gained nested safe access and default-value protection.

**Tests**: `tests/test_config.py` 3 regressions (non-None on import / properties effective after setup / references imported from other modules updated to the same object).

## Project Structure

```
monitor-plugin3/
├── metadata.yaml          # plugin metadata (name: monitor_plugin3)
├── main.py                # Star entry: lifecycle + 17 command registrations
├── _conf_schema.json      # config schema (§8)
├── requirements.txt       # httpx / sqlalchemy[asyncio] / aiosqlite
├── validate.py            # one-click validation script
│
├── commands/              # 17 command implementations
│   ├── validators.py      # steam_id / frequency validation
│   ├── add_account.py     # /addaccount (pre-check→bind→baseline snapshot)
│   ├── get_inventory.py   # 🆕 /getinventory (ID or nickname→crawl→aggregate→text+image report)
│   ├── edit_gap.py        # /editgap
│   ├── stop_message.py    # /stopmessage
│   ├── stop_all.py        # /stopall /startall
│   ├── compare.py         # /compare (date archive comparison)
│   ├── message_gap.py     # /messagegap (0=deliver immediately)
│   ├── nickname.py        # /nickname
│   ├── crawl_now.py       # /crap
│   ├── proxy_test.py      # /proxytest
│   ├── list_accounts.py   # /listaccounts (long lists rendered as images)
│   ├── del_account.py     # /delaccount (soft delete/--purge)
│   ├── restore_account.py # /restoreaccount (recycle bin)
│   ├── non_change_message.py  # /non-change-message (no-change notification toggle)
│   └── export_import.py   # /monexport /monimport
│
├── scheduler/
│   ├── monitor.py         # three background loops (monitor/delivery/maintenance) + lock & alerts
│   └── message_queue.py   # (umo, steam_id) grouped buffer queue
│
├── notifier/
│   ├── formatter.py       # events → Chinese text/reports (localization)
│   └── dispatcher.py      # QQ delivery + admin alerts + three-level fallback + report rendering
│
├── core/
│   ├── config.py          # mutable-singleton config adapter (NoneType bug fix)
│   ├── crawler/           # fetcher/parser/localize/proxy (migrated from monitor)
│   ├── detector/diff.py   # diff detection + activity classification
│   └── models/item.py     # Item / ChangeEvent / InventorySnapshot
│
├── db/
│   ├── database.py        # engine + Base + schema migration (plugin-specific data dir)
│   ├── models.py          # 4 tables (bound_umo, no login_rate_limit)
│   └── repository.py      # LRU cache/atomic transactions/soft delete/export-import/umo binding
│
├── templates/             # change_report / compare_report / account_list / 🆕 inventory_report
├── translate/             # translation_map.json (8677 entries)
└── tests/                 # 56 unit tests + fake_astrbot stub
    ├── fake_astrbot/      # minimal AstrBot API stub (verifiable load without AstrBot env)
    ├── test_config.py     # 🆕 config singleton injection regression guard
    ├── test_get_inventory.py  # 🆕 /getinventory aggregation and argument detection
    ├── test_delivery.py      # 🆕 delivery chain regression (P3/P5)
    ├── test_non_change_message.py  # 🆕 no-change notification
    ├── test_imports.py    # import regression (no src/residue + plugin load + 16 commands)
    ├── test_diff.py       # diff detection and activity classification
    ├── test_parser.py     # inventory parsing
    └── test_formatter.py  # event formatting and localization
```

## License

This project is licensed under the [MIT License](LICENSE) (Copyright © 2026 Cheney)

---

**Developer**: Cheney
**Version**: 3.3.1
**Last updated**: 2026-08-01 (added `/getinventory` + fixed config singleton injection bug)
