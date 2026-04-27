"""调飞书 Task v2 PATCH 接口更新任务状态.

环境变量:
  FEISHU_APP_ID / FEISHU_APP_SECRET    必需
  COMMIT_MESSAGE                        必需 (从 sync_feishu workflow 传)

行为:
  - 解析 commit subject 里的 [TASK-xxx] / [DONE-TASK-xxx]
  - 反查 .planning/tasks.json 拿真实 task guid (支持前缀匹配)
  - DONE 标签   -> PATCH completed_at, 任务标记完成
  - 普通 TASK 标签 -> 当前仅打 log (in_progress 状态推进留给后续扩展)

设计选择:
  - 一个 commit 可以含多个 [TASK-xxx], 全部处理
  - 单条任务失败不中断整批, 只 warn
  - tasks.json 里的 guid 通常是完整的, commit 里允许写短前缀 (8+ 字符)
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

import requests

from feishu_content import FEISHU_BASE, get_tenant_token

TASK_RE = re.compile(r"\[(DONE-)?TASK-([A-Za-z0-9_-]+)\]")
# 锚定仓库根目录, 不依赖 cwd
_REPO_ROOT = Path(__file__).resolve().parent.parent
TASKS_JSON = _REPO_ROOT / ".planning" / "tasks.json"


def find_task_guid(commit_id: str) -> str | None:
    """从 tasks.json 找匹配的真实 guid.

    匹配规则:
      1) 完全相等
      2) tasks.json 里的 guid 以 commit_id 开头 (commit 里写短前缀)
    """
    if not TASKS_JSON.exists():
        return None
    try:
        mapping = json.loads(TASKS_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    for entries in mapping.values():
        if not isinstance(entries, list):
            continue
        for e in entries:
            guid = e.get("guid", "")
            if not guid:
                continue
            if guid == commit_id or guid.startswith(commit_id):
                return guid
    return None


def patch_task_complete(tenant_token: str, guid: str) -> None:
    """调 PATCH 标记任务完成.

    飞书 Task v2: PATCH /open-apis/task/v2/tasks/:guid
    body: {"task": {"completed_at": "<毫秒时间戳>"}, "update_fields": ["completed_at"]}
    """
    r = requests.patch(
        f"{FEISHU_BASE}/task/v2/tasks/{guid}",
        headers={"Authorization": f"Bearer {tenant_token}"},
        json={
            "task": {"completed_at": str(int(time.time() * 1000))},
            "update_fields": ["completed_at"],
        },
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 0:
        raise RuntimeError(f"PATCH 任务失败: {data}")
    print(f"  ✅ task {guid} 标记完成")


def main() -> int:
    msg = os.environ.get("COMMIT_MESSAGE", "")
    if not msg:
        print("ℹ️ COMMIT_MESSAGE 为空, 跳过")
        return 0

    matches = list(TASK_RE.finditer(msg))
    if not matches:
        print("ℹ️ commit 不含 [TASK-xxx] / [DONE-TASK-xxx], 跳过")
        return 0

    app_id = os.environ.get("FEISHU_APP_ID", "")
    app_secret = os.environ.get("FEISHU_APP_SECRET", "")
    if not (app_id and app_secret):
        print("::warning::缺 FEISHU_APP_ID/SECRET, 跳过", file=sys.stderr)
        return 0

    try:
        tenant_token = get_tenant_token(app_id, app_secret)
    except Exception as e:
        print(f"::error::获取 token 失败: {e}", file=sys.stderr)
        return 1

    for m in matches:
        is_done = bool(m.group(1))
        commit_id = m.group(2)
        guid = find_task_guid(commit_id)
        if not guid:
            print(
                f"::warning::未在 .planning/tasks.json 找到 TASK-{commit_id}",
                file=sys.stderr,
            )
            continue
        if is_done:
            try:
                patch_task_complete(tenant_token, guid)
            except Exception as e:
                print(
                    f"::warning::标记任务 {guid} 完成失败: {e}",
                    file=sys.stderr,
                )
        else:
            # 后续扩展点: PATCH 任务状态为 in_progress
            print(f"  ℹ️ 引用 task {guid} (非 DONE, 暂不改状态)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
