"""create_feishu_tasks 单测."""
from __future__ import annotations

import json

import responses

import create_feishu_tasks


@responses.activate
def test_create_tasks_writes_mapping(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    # mock token
    responses.add(
        responses.POST,
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"code": 0, "tenant_access_token": "t-abc", "expire": 7200},
    )
    # mock 2 个 create_task 调用
    responses.add(
        responses.POST,
        "https://open.feishu.cn/open-apis/task/v2/tasks",
        json={"code": 0, "data": {"task": {"guid": "g-1"}}},
    )
    responses.add(
        responses.POST,
        "https://open.feishu.cn/open-apis/task/v2/tasks",
        json={"code": 0, "data": {"task": {"guid": "g-2"}}},
    )

    monkeypatch.setenv("FEISHU_APP_ID", "app")
    monkeypatch.setenv("FEISHU_APP_SECRET", "secret")
    monkeypatch.setenv("ISSUE_NUMBER", "42")
    monkeypatch.setenv(
        "ACTION_ITEMS_JSON",
        json.dumps(
            [
                {
                    "title": "实现登录",
                    "description": "",
                    "assignee_name": "张三",
                    "due_date": "2026-04-30",
                },
                {
                    "title": "写文档",
                    "description": "API 文档",
                    "assignee_name": "李四",
                    "due_date": None,
                },
            ]
        ),
    )

    rc = create_feishu_tasks.main()
    assert rc == 0

    mapping = json.loads((tmp_path / ".planning/tasks.json").read_text())
    assert "issue#42" in mapping
    assert len(mapping["issue#42"]) == 2
    assert mapping["issue#42"][0]["guid"] == "g-1"
    assert mapping["issue#42"][1]["title"] == "写文档"


def test_no_items_returns_zero(monkeypatch) -> None:
    monkeypatch.setenv("ACTION_ITEMS_JSON", "[]")
    monkeypatch.setenv("FEISHU_APP_ID", "x")
    monkeypatch.setenv("FEISHU_APP_SECRET", "y")
    monkeypatch.setenv("ISSUE_NUMBER", "1")
    assert create_feishu_tasks.main() == 0


def test_invalid_json_returns_2(monkeypatch) -> None:
    monkeypatch.setenv("ACTION_ITEMS_JSON", "not json {{{")
    assert create_feishu_tasks.main() == 2


def test_missing_secrets_returns_2(monkeypatch) -> None:
    monkeypatch.setenv("ACTION_ITEMS_JSON", json.dumps([{"title": "x"}]))
    monkeypatch.delenv("FEISHU_APP_ID", raising=False)
    monkeypatch.delenv("FEISHU_APP_SECRET", raising=False)
    monkeypatch.delenv("ISSUE_NUMBER", raising=False)
    assert create_feishu_tasks.main() == 2


@responses.activate
def test_one_failed_task_does_not_abort_batch(tmp_path, monkeypatch) -> None:
    """单条 item 创建失败不应让整批失败."""
    monkeypatch.chdir(tmp_path)

    responses.add(
        responses.POST,
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"code": 0, "tenant_access_token": "t-abc", "expire": 7200},
    )
    # 第一条成功
    responses.add(
        responses.POST,
        "https://open.feishu.cn/open-apis/task/v2/tasks",
        json={"code": 0, "data": {"task": {"guid": "g-ok"}}},
    )
    # 第二条返回 code != 0
    responses.add(
        responses.POST,
        "https://open.feishu.cn/open-apis/task/v2/tasks",
        json={"code": 1234, "msg": "permission denied"},
    )
    # 第三条又成功
    responses.add(
        responses.POST,
        "https://open.feishu.cn/open-apis/task/v2/tasks",
        json={"code": 0, "data": {"task": {"guid": "g-ok2"}}},
    )

    monkeypatch.setenv("FEISHU_APP_ID", "app")
    monkeypatch.setenv("FEISHU_APP_SECRET", "secret")
    monkeypatch.setenv("ISSUE_NUMBER", "1")
    monkeypatch.setenv(
        "ACTION_ITEMS_JSON",
        json.dumps(
            [
                {"title": "ok-1"},
                {"title": "fail"},
                {"title": "ok-2"},
            ]
        ),
    )

    rc = create_feishu_tasks.main()
    assert rc == 0

    mapping = json.loads((tmp_path / ".planning/tasks.json").read_text())
    # 只有 2 条成功的入了映射
    assert len(mapping["issue#1"]) == 2
    assert {c["guid"] for c in mapping["issue#1"]} == {"g-ok", "g-ok2"}
