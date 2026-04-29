"""update_feishu_task 单测."""

from __future__ import annotations

import json

import responses

import update_feishu_task


def test_no_task_tag_in_message_skips(monkeypatch) -> None:
    monkeypatch.setenv("COMMIT_MESSAGE", "feat: 普通提交")
    assert update_feishu_task.main() == 0


def test_no_message_skips(monkeypatch) -> None:
    monkeypatch.delenv("COMMIT_MESSAGE", raising=False)
    assert update_feishu_task.main() == 0


def test_done_tag_but_missing_secrets(monkeypatch) -> None:
    monkeypatch.setenv("COMMIT_MESSAGE", "fix: x [DONE-TASK-abc]")
    monkeypatch.delenv("FEISHU_APP_ID", raising=False)
    monkeypatch.delenv("FEISHU_APP_SECRET", raising=False)
    assert update_feishu_task.main() == 0  # warning 但不 fail


@responses.activate
def test_done_tag_calls_patch(monkeypatch, tmp_path) -> None:
    tasks_json = tmp_path / ".planning" / "tasks.json"
    monkeypatch.setattr(update_feishu_task, "TASKS_JSON", tasks_json)
    tasks_json.parent.mkdir(parents=True)
    tasks_json.write_text(json.dumps({"issue#1": [{"guid": "g-abc12345-full", "title": "x"}]}))

    responses.add(
        responses.POST,
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"code": 0, "tenant_access_token": "t-abc", "expire": 7200},
    )
    responses.add(
        responses.PATCH,
        "https://open.feishu.cn/open-apis/task/v2/tasks/g-abc12345-full",
        json={"code": 0, "data": {}},
    )

    monkeypatch.setenv("FEISHU_APP_ID", "app")
    monkeypatch.setenv("FEISHU_APP_SECRET", "secret")
    # commit 里写短前缀 g-abc12345, 应能匹配到 g-abc12345-full
    monkeypatch.setenv("COMMIT_MESSAGE", "fix: 修 bug [DONE-TASK-g-abc12345]")

    assert update_feishu_task.main() == 0
    assert len(responses.calls) == 2  # token + patch


@responses.activate
def test_unknown_task_warns_no_call(monkeypatch, tmp_path) -> None:
    tasks_json = tmp_path / ".planning" / "tasks.json"
    monkeypatch.setattr(update_feishu_task, "TASKS_JSON", tasks_json)
    tasks_json.parent.mkdir(parents=True)
    tasks_json.write_text(json.dumps({"issue#1": [{"guid": "g-real", "title": "x"}]}))

    responses.add(
        responses.POST,
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"code": 0, "tenant_access_token": "t-abc", "expire": 7200},
    )

    monkeypatch.setenv("FEISHU_APP_ID", "app")
    monkeypatch.setenv("FEISHU_APP_SECRET", "secret")
    monkeypatch.setenv("COMMIT_MESSAGE", "fix: x [DONE-TASK-nonexistent]")

    assert update_feishu_task.main() == 0
    # 只有 token 调用, 没 PATCH 调用
    assert len(responses.calls) == 1


@responses.activate
def test_non_done_tag_does_not_patch(monkeypatch, tmp_path) -> None:
    """普通 [TASK-xxx] 不该触发 PATCH (当前实现)."""
    tasks_json = tmp_path / ".planning" / "tasks.json"
    monkeypatch.setattr(update_feishu_task, "TASKS_JSON", tasks_json)
    tasks_json.parent.mkdir(parents=True)
    tasks_json.write_text(json.dumps({"issue#1": [{"guid": "g-abc", "title": "x"}]}))

    responses.add(
        responses.POST,
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"code": 0, "tenant_access_token": "t-abc", "expire": 7200},
    )

    monkeypatch.setenv("FEISHU_APP_ID", "app")
    monkeypatch.setenv("FEISHU_APP_SECRET", "secret")
    monkeypatch.setenv("COMMIT_MESSAGE", "feat: 进行中 [TASK-g-abc]")

    assert update_feishu_task.main() == 0
    # 只 token 调用
    assert len(responses.calls) == 1


@responses.activate
def test_multiple_tasks_in_one_commit(monkeypatch, tmp_path) -> None:
    tasks_json = tmp_path / ".planning" / "tasks.json"
    monkeypatch.setattr(update_feishu_task, "TASKS_JSON", tasks_json)
    tasks_json.parent.mkdir(parents=True)
    tasks_json.write_text(
        json.dumps(
            {
                "issue#1": [
                    {"guid": "g-one", "title": "a"},
                    {"guid": "g-two", "title": "b"},
                ]
            }
        )
    )

    responses.add(
        responses.POST,
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"code": 0, "tenant_access_token": "t-abc", "expire": 7200},
    )
    responses.add(
        responses.PATCH,
        "https://open.feishu.cn/open-apis/task/v2/tasks/g-one",
        json={"code": 0, "data": {}},
    )
    responses.add(
        responses.PATCH,
        "https://open.feishu.cn/open-apis/task/v2/tasks/g-two",
        json={"code": 0, "data": {}},
    )

    monkeypatch.setenv("FEISHU_APP_ID", "app")
    monkeypatch.setenv("FEISHU_APP_SECRET", "secret")
    monkeypatch.setenv(
        "COMMIT_MESSAGE",
        "feat: 完成两件事 [DONE-TASK-g-one] [DONE-TASK-g-two]",
    )

    assert update_feishu_task.main() == 0
    assert len(responses.calls) == 3  # token + 2 PATCH
