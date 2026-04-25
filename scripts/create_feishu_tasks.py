"""读 ACTION_ITEMS_JSON, 调飞书 Task v2 批量建任务, 维护 .planning/tasks.json 映射.

环境变量:
  FEISHU_APP_ID / FEISHU_APP_SECRET   必需
  ACTION_ITEMS_JSON                    必需 (extract step 的 JSON 数组字符串)
  ISSUE_NUMBER                         必需 (用于 tasks.json 索引 key)
  GITHUB_OUTPUT                        可选 (写 guids / task_md 给下游 step)

行为:
  - 对每个 item 调 POST /task/v2/tasks 创建任务
  - 暂不解析 assignee_name -> open_id (留 TODO, Phase 5.3 跑通后再补)
  - 把 {issue#N: [{guid, title, assignee_name, due_date}]} 写到 .planning/tasks.json
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

from feishu_content import FEISHU_BASE, get_tenant_token

TASKS_JSON_PATH = ".planning/tasks.json"


def create_task(
    tenant_token: str,
    title: str,
    description: str,
    due_date: str | None,
    assignee_open_ids: list[str],
) -> str:
    """调飞书 Task v2 创建任务, 返回 guid."""
    body: dict = {"summary": title, "description": description}
    if due_date:
        try:
            ts_ms = int(
                datetime.fromisoformat(due_date)
                .replace(tzinfo=timezone.utc)
                .timestamp()
                * 1000
            )
            body["due"] = {"timestamp": str(ts_ms), "is_all_day": True}
        except ValueError:
            # 日期格式不合法就忽略, 不让一条 item 失败拖累整批
            pass
    if assignee_open_ids:
        body["members"] = [
            {"id": oid, "type": "user", "role": "assignee"}
            for oid in assignee_open_ids
        ]
    r = requests.post(
        f"{FEISHU_BASE}/task/v2/tasks",
        headers={"Authorization": f"Bearer {tenant_token}"},
        json=body,
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 0:
        raise RuntimeError(f"create task 失败: {data}")
    return data.get("data", {}).get("task", {}).get("guid", "")  # type: ignore[no-any-return]


def load_tasks_map() -> dict:
    """读 .planning/tasks.json (不存在则返回空 dict)."""
    p = Path(TASKS_JSON_PATH)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def save_tasks_map(mapping: dict) -> None:
    """落盘 .planning/tasks.json (sorted, indent=2 便于 diff)."""
    p = Path(TASKS_JSON_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def main() -> int:
    items_raw = os.environ.get("ACTION_ITEMS_JSON", "[]")
    try:
        items = json.loads(items_raw)
    except json.JSONDecodeError as e:
        print(f"::error::ACTION_ITEMS_JSON 解析失败: {e}", file=sys.stderr)
        return 2
    if not isinstance(items, list) or not items:
        print("ℹ️ 没有 action items, 跳过任务创建")
        return 0

    app_id = os.environ.get("FEISHU_APP_ID", "")
    app_secret = os.environ.get("FEISHU_APP_SECRET", "")
    issue_num = os.environ.get("ISSUE_NUMBER", "")
    if not (app_id and app_secret and issue_num):
        print(
            "::error::缺 FEISHU_APP_ID / FEISHU_APP_SECRET / ISSUE_NUMBER",
            file=sys.stderr,
        )
        return 2

    tenant_token = get_tenant_token(app_id, app_secret)

    created: list[dict] = []
    for item in items:
        # TODO(后续优化): assignee_name -> open_id 解析 (调 contact API)
        # 当前实现: assignee 留空, 任务先建出来, 团队成员手动认领
        try:
            guid = create_task(
                tenant_token,
                title=item.get("title", "未命名"),
                description=item.get("description", ""),
                due_date=item.get("due_date"),
                assignee_open_ids=[],
            )
        except Exception as e:
            print(f"::warning::创建任务 {item.get('title')!r} 失败: {e}", file=sys.stderr)
            continue
        if guid:
            created.append(
                {
                    "guid": guid,
                    "title": item.get("title", ""),
                    "assignee_name": item.get("assignee_name", ""),
                    "due_date": item.get("due_date"),
                }
            )
            print(f"  ✅ {item.get('title')} -> {guid}")

    # 维护 tasks.json
    mapping = load_tasks_map()
    key = f"issue#{issue_num}"
    mapping.setdefault(key, []).extend(created)
    save_tasks_map(mapping)
    print(f"已写 {TASKS_JSON_PATH}, key={key}, 新增 {len(created)} 条")

    # 输出给 workflow 下游 step
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        guids = " ".join(c["guid"] for c in created)
        md_lines = "\n".join(
            f"- **{c['title']}** ({c['assignee_name'] or '未指派'}, "
            f"{c['due_date'] or '无截止'}): `{c['guid']}`"
            for c in created
        ) or "_(无)_"
        with open(gh_out, "a") as f:
            f.write(f"task_count={len(created)}\n")
            f.write(f"guids={guids}\n")
            f.write(f"task_md<<TASK_MD_EOF\n{md_lines}\nTASK_MD_EOF\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
