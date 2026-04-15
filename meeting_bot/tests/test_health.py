"""测试 healthz 端点。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from meeting_bot.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_healthz(client: TestClient) -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body
