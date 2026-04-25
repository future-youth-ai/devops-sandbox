"""archive_meeting 单测."""
from __future__ import annotations

import json

import archive_meeting
from archive_meeting import build_table


def test_build_table_empty() -> None:
    assert "未提取到" in build_table([])


def test_build_table_with_items() -> None:
    md = build_table(
        [
            {"title": "登录", "assignee_name": "张三", "due_date": "2026-04-30", "guid": "g1"},
            {"title": "文档", "assignee_name": "", "due_date": None, "guid": "g2"},
        ]
    )
    assert "| 1 | 登录 | 张三 | 2026-04-30 | `g1` |" in md
    assert "| 2 | 文档 | 未指派 | — | `g2` |" in md


def test_build_table_escapes_pipe() -> None:
    md = build_table(
        [{"title": "a|b", "assignee_name": "c|d", "due_date": None, "guid": "g"}]
    )
    assert "a\\|b" in md
    assert "c\\|d" in md


def test_main_writes_file(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".planning").mkdir()
    (tmp_path / ".planning/tasks.json").write_text(
        json.dumps(
            {
                "issue#99": [
                    {
                        "title": "测试任务",
                        "assignee_name": "张三",
                        "due_date": "2026-05-01",
                        "guid": "g-1",
                    }
                ]
            }
        )
    )

    monkeypatch.setenv("MEETING_TITLE", "测试会议")
    monkeypatch.setenv("MEETING_DATE", "2026-04-23")
    monkeypatch.setenv("ISSUE_NUMBER", "99")
    monkeypatch.setenv("FEISHU_URL", "https://meetings.feishu.cn/minutes/xxx")

    rc = archive_meeting.main()
    assert rc == 0

    out = tmp_path / ".planning/meetings/2026-04-23-issue99.md"
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "# 测试会议" in content
    assert "**入口 issue**: #99" in content
    assert "https://meetings.feishu.cn/minutes/xxx" in content
    assert "| 1 | 测试任务 | 张三 | 2026-05-01 | `g-1` |" in content

    # stdout 含文件路径供 workflow 拿
    captured = capsys.readouterr()
    assert ".planning/meetings/2026-04-23-issue99.md" in captured.out


def test_main_no_tasks_json(tmp_path, monkeypatch) -> None:
    """tasks.json 不存在时归档仍能跑, 表格区为空提示."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MEETING_TITLE", "空会议")
    monkeypatch.setenv("MEETING_DATE", "2026-04-23")
    monkeypatch.setenv("ISSUE_NUMBER", "1")

    rc = archive_meeting.main()
    assert rc == 0

    out = tmp_path / ".planning/meetings/2026-04-23-issue1.md"
    assert out.exists()
    assert "未提取到" in out.read_text(encoding="utf-8")
