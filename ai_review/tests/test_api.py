"""API 层集成测试 - 用 FastAPI TestClient."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestHealth:
    def test_health_ok(self, client: TestClient) -> None:
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["version"]

    def test_ready(self, client: TestClient) -> None:
        r = client.get("/ready")
        assert r.status_code == 200
        assert r.json()["status"] == "ready"


class TestReviewSubmit:
    def test_submit_returns_202_and_pending(self, client: TestClient) -> None:
        payload = {
            "document_name": "test.pdf",
            "document_type": "pdf",
            "tenant_id": "tenant-1",
            "document_ref": "s3://bucket/test.pdf",
        }
        r = client.post("/review/submit", json=payload)
        assert r.status_code == 202
        body = r.json()
        assert body["task"]["state"] == "pending"
        assert body["task"]["tenant_id"] == "tenant-1"
        assert body["task"]["task_id"]

    def test_submit_rejects_unknown_field(self, client: TestClient) -> None:
        # Pydantic extra="forbid"
        payload = {
            "document_name": "test.pdf",
            "document_type": "pdf",
            "tenant_id": "tenant-1",
            "document_ref": "s3://x",
            "unknown_field": "boom",
        }
        r = client.post("/review/submit", json=payload)
        assert r.status_code == 422

    def test_submit_rejects_unknown_doc_type(self, client: TestClient) -> None:
        payload = {
            "document_name": "test.exe",
            "document_type": "exe",  # 不在 Literal 范围内
            "tenant_id": "t",
            "document_ref": "x",
        }
        r = client.post("/review/submit", json=payload)
        assert r.status_code == 422

    def test_get_task_by_id(self, client: TestClient) -> None:
        payload = {
            "document_name": "doc.md",
            "document_type": "md",
            "tenant_id": "t",
            "document_ref": "x",
        }
        submit = client.post("/review/submit", json=payload).json()
        task_id = submit["task"]["task_id"]

        r = client.get(f"/review/{task_id}")
        assert r.status_code == 200
        assert r.json()["task_id"] == task_id

    def test_get_unknown_task_404(self, client: TestClient) -> None:
        r = client.get("/review/does-not-exist")
        assert r.status_code == 404
