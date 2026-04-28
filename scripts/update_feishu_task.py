"""解析 commit 里的 [TASK-xxx] / [DONE-TASK-xxx], 更新飞书多维表格记录状态.

环境变量:
  FEISHU_APP_ID / FEISHU_APP_SECRET    必需
  COMMIT_MESSAGE                        必需 (从 sync_feishu workflow 传)
  FEISHU_BITABLE_APP_TOKEN             可选 (默认 TGzCb2Xipaw56WstSUscP9ddn8b)
  FEISHU_BITABLE_TABLE_ID              可选 (默认 tblg4XejzUeTKHsf)

行为:
  - 解析 commit subject 里的 [TASK-xxx] / [DONE-TASK-xxx]
  - 反查 .planning/tasks.json 拿真实 record_id (支持前缀匹配)
  - DONE 标签   -> 更新进展状态为 "验收完成"
  - 普通 TASK 标签 -> 更新进展状态为 "开发中"
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import requests

from feishu_content import FEISHU_BASE, get_tenant_token

TASK_RE = re.compile(r"\[(DONE-)?TASK-([A-Za-z0-9_-]+)\]")
_REPO_ROOT = Path(__file__).resolve().parent.parent
TASKS_JSON = _REPO_ROOT / ".planning" / "tasks.json"

DEFAULT_APP_TOKEN = "TGzCb2Xipaw56WstSUscP9ddn8b"
DEFAULT_TABLE_ID = "tblg4XejzUeTKHsf"


def find_record_id(commit_id: str) -> str | None:
    """从 tasks.json 找匹配的真实 record_id.

    匹配规则:
      1) 完全相等
      2) tasks.json 里的 record_id 以 commit_id 开头 (commit 里写短前缀)
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
            rid = e.get("record_id", "")
            if not rid:
                continue
            if rid == commit_id or rid.startswith(commit_id):
                return rid
    return None


def update_record_status(
    tenant_token: str,
    app_token: str,
    table_id: str,
    record_id: str,
    status: str,
) -> None:
    """更新多维表格记录的进展状态."""
    r = requests.put(
        f"{FEISHU_BASE}/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}",
        headers={"Authorization": f"Bearer {tenant_token}"},
        json={"fields": {"进展状态": status}},
        timeout=30,
    )
    if not r.ok:
        raise RuntimeError(f"update record HTTP {r.status_code}: {r.text}")
    data = r.json()
    if data.get("code") != 0:
        raise RuntimeError(f"update record 失败: {data}")
    print(f"  ✅ record {record_id} -> {status}")


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

    app_token = os.environ.get("FEISHU_BITABLE_APP_TOKEN", DEFAULT_APP_TOKEN)
    table_id = os.environ.get("FEISHU_BITABLE_TABLE_ID", DEFAULT_TABLE_ID)

    try:
        tenant_token = get_tenant_token(app_id, app_secret)
    except Exception as e:
        print(f"::error::获取 token 失败: {e}", file=sys.stderr)
        return 1

    for m in matches:
        is_done = bool(m.group(1))
        commit_id = m.group(2)
        record_id = find_record_id(commit_id)
        if not record_id:
            print(
                f"::warning::未在 .planning/tasks.json 找到 TASK-{commit_id}",
                file=sys.stderr,
            )
            continue
        status = "验收完成" if is_done else "开发中"
        try:
            update_record_status(tenant_token, app_token, table_id, record_id, status)
        except Exception as e:
            print(
                f"::warning::更新记录 {record_id} 失败: {e}",
                file=sys.stderr,
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
