"""SQLAlchemy 异步数据库引擎与会话管理（适配 AstrBot 插件环境）。

数据目录固定为 AstrBot 的 `data/plugin_data/astrbot_plugin_monitor/`
（plan-v3 §NF4，防更新覆盖）。
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

# AstrBot 数据目录：优先取运行目录下的 data/plugin_data/<插件名>/，
# 无法确定时回退到插件目录旁的 data/。
_data_root = Path("data")
if not _data_root.is_dir():
    _data_root = Path(__file__).parent.parent / "data"
DATA_DIR = _data_root / "plugin_data" / "astrbot_plugin_monitor"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_URL = f"sqlite+aiosqlite:///{DATA_DIR / 'monitor.db'}"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
    pool_size=1,
    max_overflow=0,
)

# SQLite 默认不启用外键约束，需显式开启
@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    """创建所有表，并自动执行必要的 schema 迁移。"""
    async with engine.begin() as conn:
        from .models import Base as AllModels  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)

    # ---- Schema 迁移（独立连接，不污染 create_all 的事务） ----
    migrations = [
        # monitor_frequency 列（旧库升级）
        "ALTER TABLE monitored_users ADD COLUMN monitor_frequency VARCHAR(16) DEFAULT 'medium'",
        # bound_umo 列（旧库升级，plan-v3 §12.3）
        "ALTER TABLE monitored_users ADD COLUMN bound_umo VARCHAR(512)",
        # deleted_at 列（回收站支持）
        "ALTER TABLE monitored_users ADD COLUMN deleted_at DATETIME",
    ]
    for sql_text in migrations:
        try:
            async with engine.begin() as conn:
                await conn.execute(text(sql_text))
        except Exception:
            pass  # 列已存在则忽略


async def close_db() -> None:
    """关闭数据库引擎。"""
    await engine.dispose()


def get_session():
    """获取异步会话（兼容 async with / async for 用法）。"""
    return async_session_factory()
