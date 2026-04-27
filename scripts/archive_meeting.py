"""把会议元信息 + 提取结果归档为 markdown 到 .planning/meetings/.

策略 B (链接归档): 不存原文 transcript, 只存元信息 + action items + 任务 GUIDs.
原始 transcript 留在飞书云端, 通过 issue 里的 link 点过去.

环境变量:
  MEETING_TITLE      可选, 默认 "未命名会议"
  MEETING_DATE       可选, 默认今天 UTC
  ISSUE_NUMBER       必需 (用于反查 .planning/tasks.json)
  FEISHU_URL         可选, 写在归档里方便溯源

输出:
  - 写文件 .planning/meetings/{date}-issue{n}.md
  - 把文件路径打到 stdout (workflow 用 $(python ...) 拿)
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# 路径安全: ISSUE_NUMBER 必须纯数字, MEETING_DATE 必须 YYYY-MM-DD
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ISSUE_NUM_RE = re.compile(r"^\d+$")

TEMPLATE = """# {title}

- **日期**: {date}
- **入口 issue**: #{issue_number}
- **原始链接**: {feishu_url}
- **生成时间 (UTC)**: {generated_at}

## AI 提取的 Action Items

{table}

> 归档策略 B: transcript 原文留在飞书, 此处仅留元信息和 AI 抽取结果.
"""


def _md_escape(s: str) -> str:
    """简单转义 markdown 表格里的 `|`."""
    return s.replace("|", "\\|").replace("\n", " ")


def build_table(items: list[dict]) -> str:
    """把 tasks.json 里某 issue 下的条目渲染成 markdown 表格."""
    if not items:
        return "_(本次会议未提取到 action items)_"
    lines = [
        "| # | 任务 | 负责人 | 截止 | 飞书 Task GUID |",
        "|---|---|---|---|---|",
    ]
    for i, it in enumerate(items, 1):
        title = _md_escape(it.get("title") or "")
        assignee = _md_escape(it.get("assignee_name") or "未指派")
        due = it.get("due_date") or "—"
        guid = it.get("guid") or "(创建失败)"
        lines.append(f"| {i} | {title} | {assignee} | {due} | `{guid}` |")
    return "\n".join(lines)


def main() -> int:
    title = os.environ.get("MEETING_TITLE", "").strip() or "未命名会议"
    date = os.environ.get("MEETING_DATE", "").strip()
    if not date:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # 路径安全校验: 阻断 ../ 等穿越
    if not DATE_RE.fullmatch(date):
        print(
            f"::error::MEETING_DATE 格式必须是 YYYY-MM-DD (got {date!r})",
            file=sys.stderr,
        )
        return 2

    issue_num = os.environ.get("ISSUE_NUMBER", "").strip()
    if not ISSUE_NUM_RE.fullmatch(issue_num):
        print(
            f"::error::ISSUE_NUMBER 必须为纯数字 (got {issue_num!r})",
            file=sys.stderr,
        )
        return 2

    feishu_url = os.environ.get("FEISHU_URL", "").strip() or "(未提供)"

    # 从 tasks.json 取本次的 created 条目, 做类型兜底
    tasks_path = Path(".planning/tasks.json")
    items: list[dict] = []
    if tasks_path.exists():
        try:
            mapping = json.loads(tasks_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print("::warning::tasks.json 解析失败, 归档表格留空", file=sys.stderr)
            mapping = {}
        if isinstance(mapping, dict):
            raw_items = mapping.get(f"issue#{issue_num}", [])
            if isinstance(raw_items, list):
                # 只保留 dict 项, 防脏数据让 build_table 崩
                items = [it for it in raw_items if isinstance(it, dict)]

    md = TEMPLATE.format(
        title=title,
        date=date,
        issue_number=issue_num,
        feishu_url=feishu_url,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        table=build_table(items),
    )

    out_path = Path(f".planning/meetings/{date}-issue{issue_num}.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")
    # 输出文件路径供 workflow 用 (echo "$(python archive_meeting.py)")
    print(str(out_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
