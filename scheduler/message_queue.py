"""消息缓冲队列 - 按 (umo, steam_id) 分组累积变化事件。

功能：
- 缓存变化事件而非立即发送
- 按 message_interval_minutes 定时批量 flush
- 支持 /messagegap 0 触发立即投递
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class PendingNotification:
    """待投递的通知。"""
    umo: str                    # unified_msg_origin
    steam_id: str
    events: list[Any]           # ChangeEvent 列表
    activity: Any               # InventoryActivity
    accumulated_since: datetime = field(default_factory=datetime.utcnow)


class MessageQueue:
    """消息缓冲队列 — 按 (umo, steam_id) 分组累积。"""
    
    def __init__(self):
        self._buffer: dict[tuple[str, str], PendingNotification] = {}
        self._lock = asyncio.Lock()
    
    async def enqueue(self, umo: str, steam_id: str, events, activity):
        """将变化事件加入队列（或追加到现有条目）。"""
        key = (umo, steam_id)
        
        async with self._lock:
            if key in self._buffer:
                # 追加到现有条目
                notification = self._buffer[key]
                notification.events.extend(events)
                notification.activity = activity
            else:
                # 创建新条目
                self._buffer[key] = PendingNotification(
                    umo=umo,
                    steam_id=steam_id,
                    events=events,
                    activity=activity,
                    accumulated_since=datetime.utcnow(),
                )
    
    async def dequeue_all(self) -> list[PendingNotification]:
        """清空并返回所有待投递通知。"""
        async with self._lock:
            items = list(self._buffer.values())
            self._buffer.clear()
            return items
    
    def clear(self):
        """清空队列（不调用 flush）。"""
        self._buffer.clear()
    
    def size(self) -> int:
        """当前队列大小。"""
        return len(self._buffer)
    
    async def flush_specific(self, umo: str) -> list[PendingNotification]:
        """只 flush 指定 umo 的消息。"""
        async with self._lock:
            to_flush = []
            keys_to_remove = []
            
            for key, notification in self._buffer.items():
                if key[0] == umo:
                    to_flush.append(notification)
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del self._buffer[key]
            
            return to_flush
    
    def get_stats(self) -> dict[str, Any]:
        """获取队列统计信息。"""
        return {
            "queue_size": self.size(),
            "active_users": len(set(k[0] for k in self._buffer.keys())),
        }
