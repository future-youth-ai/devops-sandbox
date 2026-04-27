"""create_feishu_tasks 单测."""
from __future__ import annotations

import json

import responses

import create_feishu_tasks


@responses.activate
def test_create_tasks_writes_mapping(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        create_feishu_tasks, "TASKS_JSON_PATH", tmp_path / ".planning" / "tasks.json"
    )

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
def test_due_date_with_explicit_tz_is_preserved(tmp_path, monkeypatch) -> None:
    """due_date 含时区不应被覆盖成 UTC."""
    from datetime import datetime

    monkeypatch.setattr(
        create_feishu_tasks, "TASKS_JSON_PATH", tmp_path / ".planning" / "tasks.json"
    )
    responses.add(
        responses.POST,
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"code": 0, "tenant_access_token": "t-abc", "expire": 7200},
    )

    captured: dict = {}

    def handler(request):
        captured["body"] = json.loads(request.body)
        return (200, {}, json.dumps({"code": 0, "data": {"task": {"guid": "g-1"}}}))

    responses.add_callback(
        responses.POST,
        "https://open.feishu.cn/open-apis/task/v2/tasks",
        callback=handler,
    )

    monkeypatch.setenv("FEISHU_APP_ID", "app")
    monkeypatch.setenv("FEISHU_APP_SECRET", "secret")
    monkeypatch.setenv("ISSUE_NUMBER", "1")
    # +08:00 时区, 不应被覆盖成 UTC
    monkeypatch.setenv(
        "ACTION_ITEMS_JSON",
        json.dumps(
            [{"title": "x", "due_date": "2026-04-30T10:00:00+08:00"}]
        ),
    )
    assert create_feishu_tasks.main() == 0
    body = captured["body"]
    expected_ts_ms = int(
        datetime.fromisoformat("2026-04-30T10:00:00+08:00").timestamp() * 1000
    )
    assert int(body["due"]["timestamp"]) == expected_ts_ms


def test_invalid_action_items_filtered_by_pydantic(tmp_path, monkeypatch) -> None:
    """ACTION_ITEMS_JSON 里非法 item 应被 pydantic 过滤掉, 全非法时返 0 不调外部."""
    monkeypatch.setenv("ACTION_ITEMS_JSON", json.dumps([
        {"title": ""},                # 空 title 不合法 (min_length=1)
        "not a dict",                  # 非 dict 直接跳
        {"title": "x" * 500},          # title 超 200 字符不合法
    ]))
    monkeypatch.setenv("FEISHU_APP_ID", "x")
    monkeypatch.setenv("FEISHU_APP_SECRET", "y")
    monkeypatch.setenv("ISSUE_NUMBER", "1")
    # 全部不合法 -> 走"没有合法 action items"早退分支, 不调任何 API
    assert create_feishu_tasks.main() == 0


@responses.activate
def test_one_failed_task_does_not_abort_batch(tmp_path, monkeypatch) -> None:
    """单条 item 创建失败不应让整批失败."""
    monkeypatch.setattr(
        create_feishu_tasks, "TASKS_JSON_PATH", tmp_path / ".planning" / "tasks.json"
    )

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
