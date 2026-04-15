"""基于 SQLite 的事件幂等去重。

飞书 webhook 可能重复投递同一个事件 (event_id), 用 SQLite 持久化已处理的事件 ID,
避免重复生成文档/任务/邮件。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import aiosqlite


class DedupStore:
    """轻量的 event_id 去重存储, 单进程 OK, 多进程部署请换 Redis。"""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    async def init(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS processed_events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    processed_at TEXT NOT NULL
                )
                """
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_processed_at ON processed_events(processed_at)"
            )
            await db.commit()

    async def is_processed(self, event_id: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT 1 FROM processed_events WHERE event_id = ? LIMIT 1",
                (event_id,),
            )
            row = await cur.fetchone()
            return row is not None

    async def mark_processed(self, event_id: str, event_type: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO processed_events VALUES (?, ?, ?)",
                (event_id, event_type, datetime.utcnow().isoformat()),
            )
            await db.commit()
