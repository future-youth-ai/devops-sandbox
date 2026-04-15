"""共享 fixture - 提供测试用的 Settings。"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from meeting_bot.config import Settings, get_settings


@pytest.fixture(autouse=True)
def _isolate_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """给每个测试注入最小可用的环境变量。"""
    env = {
        "FEISHU_APP_ID": "cli_test",
        "FEISHU_APP_SECRET": "test-secret",
        "FEISHU_EVENT_ENCRYPT_KEY": "0123456789abcdef0123456789abcdef",
        "FEISHU_BITABLE_APP_TOKEN": "bascntest",
        "FEISHU_BITABLE_TABLE_ID": "tblXXX",
        "FEISHU_DOC_TEMPLATE_TOKEN": "doxcnXXX",
        "FEISHU_SUMMARY_CHAT_ID": "oc_test",
        "APP_SQLITE_PATH": str(tmp_path / "dedup.sqlite"),
    }
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def settings() -> Settings:
    return get_settings()
