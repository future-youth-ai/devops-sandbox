"""测试 SQLite 去重存储。"""

from __future__ import annotations

from pathlib import Path

import pytest

from meeting_bot.dedup import DedupStore


@pytest.mark.asyncio
async def test_dedup_roundtrip(tmp_path: Path) -> None:
    store = DedupStore(tmp_path / "dedup.sqlite")
    await store.init()

    assert await store.is_processed("evt_1") is False
    await store.mark_processed("evt_1", "vc.meeting.meeting_ended_v1")
    assert await store.is_processed("evt_1") is True

    # 重复 mark 不会出错
    await store.mark_processed("evt_1", "vc.meeting.meeting_ended_v1")
    assert await store.is_processed("evt_1") is True
