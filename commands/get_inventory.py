"""爬取并投递全部库存内容 - /getinventory 指令实现。

用法:
  /getinventory <steam_id>   # 按 Steam ID（17 位数字）
  /getinventory <昵称>       # 按监控账号昵称

流程：识别账号 → 爬取全部库存（分页）→ 解析 → 按饰品聚合统计 →
文本摘要 + 图片报告（inventory_report.html）投递到当前会话。
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime

from astrbot.api.event import AstrMessageEvent

from ..core.crawler.fetcher import fetch_inventory_paginated
from ..core.crawler.localize import translate_name
from ..core.crawler.parser import parse_inventory_response
from ..db.repository import get_active_users, get_user_by_steam_id
from .validators import validate_steam_id

# 单次渲染的最大分组数（超出时图片截断并提示）
MAX_GROUPS_IN_REPORT = 300


def _build_groups(items: dict) -> tuple[list[dict], int, bool]:
    """按饰品名聚合库存物品。

    Returns:
        (groups, total_count, truncated)
        groups: [{name(汉化), original, count}] 按数量降序
    """
    name_counter: Counter = Counter(i.market_hash_name for i in items.values())
    total_count = len(items)
    groups = [
        {
            "name": translate_name(name) or name,
            "original": name,
            "count": cnt,
        }
        for name, cnt in name_counter.most_common()
    ]
    truncated = len(groups) > MAX_GROUPS_IN_REPORT
    if truncated:
        groups = groups[:MAX_GROUPS_IN_REPORT]
    return groups, total_count, truncated


async def _resolve_user(steam_id_or_nickname: str):
    """解析参数为 (user, steam_id, nickname)。

    17 位数字 → 直接按 Steam ID（未监控账号也可查询公开库存）；
    否则 → 按昵称匹配监控账号（大小写不敏感包含匹配）。
    解析失败返回 (None, None, 错误信息)。
    """
    param = steam_id_or_nickname.strip()

    # 1. Steam ID（合法 17 位数字 → 直接查询，即使未监控）
    is_valid, _ = validate_steam_id(param)
    if is_valid:
        user = await get_user_by_steam_id(param)
        return user, param, user.nickname if user else None

    # 2. 昵称匹配（活跃用户）
    users = await get_active_users()
    matches = [u for u in users if u.nickname and param.lower() in u.nickname.lower()]
    if len(matches) == 1:
        return matches[0], matches[0].steam_id, matches[0].nickname
    if len(matches) > 1:
        names = "、".join(u.nickname for u in matches[:5])
        return None, None, f"昵称匹配到多个账号：{names}，请改用 Steam ID"
    return None, None, f"未找到昵称包含「{param}」的监控账号"


async def get_inventory(event: AstrMessageEvent, param: str = "", plugin_instance=None):
    """爬取账号全部库存并投递到当前会话。"""
    if not param:
        yield event.plain_result(
            "❌ 用法：\n"
            "/getinventory <steam_id>  按 Steam ID 查询\n"
            "/getinventory <昵称>      按监控账号昵称查询"
        )
        return

    param = param.strip()

    # 1. 解析账号（id 或昵称）
    user, steam_id, nickname = await _resolve_user(param)
    if steam_id is None:
        yield event.plain_result(f"❌ {nickname}")
        return

    # 2. 爬取全部库存
    yield event.plain_result(
        f"🔍 正在爬取 {nickname or steam_id} 的全部库存...\n"
        f"（库存较大时可能需要数十秒）"
    )
    try:
        raw = await fetch_inventory_paginated(steam_id)
    except Exception as exc:
        yield event.plain_result(
            f"❌ 爬取失败：{str(exc)[:120]}\n"
            f"请检查代理配置（/proxytest 可测试连通性）或稍后重试"
        )
        return

    if raw is None:
        yield event.plain_result(
            "❌ 无法获取该账号的库存数据\n"
            "可能原因：库存设置为私密、API 访问受限或触发限流\n"
            "私密库存请在插件配置中设置 steam_cookie"
        )
        return

    # 3. 解析与聚合
    items = parse_inventory_response(raw)
    if not items:
        yield event.plain_result("📭 该账号库存为空或解析结果为空")
        return

    api_total = raw.get("total_inventory_count", len(items))
    groups, total_count, truncated = _build_groups(items)
    report_groups = groups

    # 5. 文本摘要（即时反馈，不依赖渲染）
    lines = [
        f"🎒 {nickname or 'Steam 用户'} 的库存（{steam_id}）",
        f"📦 共 {total_count} 件物品 / {api_total}（API Total），{len(groups)} 种饰品\n",
    ]
    for g in report_groups[:15]:
        lines.append(f"{g['name']} ×{g['count']}")
    if len(groups) > 15:
        lines.append(f"... 共 {len(groups)} 种，完整列表见图片")
    yield event.plain_result("\n".join(lines))

    # 6. 图片报告（完整列表）
    if plugin_instance is not None:
        try:
            data = {
                "steam_id": steam_id,
                "nickname": nickname or "Steam 用户",
                "total_count": total_count,
                "api_total": api_total,
                "group_count": len(groups),
                "groups": report_groups,
                "truncated": truncated,
                "truncated_count": len(groups) - MAX_GROUPS_IN_REPORT,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            img_url = await plugin_instance.dispatcher.render_inventory_report(data)
            yield event.image_result(img_url)
        except Exception as exc:
            yield event.plain_result(f"⚠️ 报告渲染失败（已显示文本列表）：{str(exc)[:80]}")
