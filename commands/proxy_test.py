"""代理检测与连通性测试 - /proxytest 指令实现（plan-v3 §7.1 F11，对应 Web /api/test-connection）。"""

from __future__ import annotations

import time

from astrbot.api.event import AstrMessageEvent


async def proxy_test(event: AstrMessageEvent, plugin_instance=None):
    """代理检测 + Steam API 连通性测试。"""
    from ..core.config import settings
    from ..core.crawler.proxy import detect_proxy, resolve_proxy_config
    from ..core.crawler.fetcher import get_client

    lines = ["🔧 代理与连通性测试\n"]

    # 1. 当前配置
    lines.append(f"配置模式: {settings.steam_proxy_mode}")
    if settings.steam_proxy_mode == "manual":
        lines.append(f"手动代理: {settings.steam_proxy_url or '(未设置)'}")
    elif settings.steam_proxy_mode == "hosts":
        lines.append(f"Hosts 覆盖: {settings.steam_hosts_override or '(未设置)'}")
    elif settings.steam_proxy_mode == "auto":
        try:
            detected = detect_proxy("auto")
            lines.append(f"自动检测: {detected.get('message') or detected.get('proxy') or '直连'}")
        except Exception as exc:
            lines.append(f"自动检测失败: {str(exc)[:80]}")
    else:
        lines.append("模式 none：直连（不使用代理）")
    lines.append("")

    # 2. 解析后的代理配置
    proxy_cfg = resolve_proxy_config(
        proxy_mode=settings.steam_proxy_mode,
        proxy_url=settings.steam_proxy_url,
        hosts_override=settings.steam_hosts_override,
    )
    lines.append(f"解析代理: {proxy_cfg.get('proxy') or '直连'}")
    lines.append("")

    # 3. 连通性测试（Steam Community API）
    yield event.plain_result("\n".join(lines) + "⏳ 正在测试 Steam API 连通性...")

    client = await get_client()
    test_url = "https://steamcommunity.com/"
    try:
        start_ts = time.time()
        resp = await client.get(test_url, timeout=15)
        elapsed = time.time() - start_ts
        lines.append(f"Steam Community ({resp.status_code}) — {elapsed:.1f}s")
        if resp.status_code == 200:
            lines.append("✅ Steam API 连通正常")
        elif resp.status_code == 429:
            lines.append("⚠️ 收到 429 限流（请求过于频繁，请等待或配置 steam_cookie）")
        else:
            lines.append(f"⚠️ 返回状态码 {resp.status_code}（可能是地区/风控限制）")
    except Exception as exc:
        lines.append(f"❌ 连接失败: {str(exc)[:120]}")
        lines.append("建议：切换代理模式（auto/manual/hosts/none）后重试")

    yield event.plain_result("\n".join(lines))
