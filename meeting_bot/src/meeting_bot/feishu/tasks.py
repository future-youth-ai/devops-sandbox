"""飞书任务 (Task v2) API - 创建任务并指派负责人。

文档: https://open.feishu.cn/document/task-v2/task/create
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from meeting_bot.feishu.client import FeishuClient


class TaskAPI:
    """任务 v2 API 包装。"""

    def __init__(self, client: FeishuClient) -> None:
        self.client = client

    async def create_task(
        self,
        summary: str,
        description: str = "",
        assignee_open_ids: list[str] | None = None,
        due_time: datetime | None = None,
        reminder_offset_minutes: int = 60,
    ) -> str:
        """创建一个 Task v2 任务, 返回 guid。

        - assignee_open_ids: 负责人 open_id 列表 (role=assignee)
        - due_time: 截止时间, None 表示无
        - reminder_offset_minutes: 提醒提前多少分钟
        """
        body: dict[str, Any] = {
            "summary": summary,
            "description": description,
        }
        if due_time is not None:
            body["due"] = {
                "timestamp": str(int(due_time.timestamp() * 1000)),
                "is_all_day": False,
            }
            body["reminders"] = [{"relative_fire_minute": reminder_offset_minutes}]
        if assignee_open_ids:
            body["members"] = [
                {"id": oid, "type": "user", "role": "assignee"} for oid in assignee_open_ids
            ]

        data = await self.client.post("/task/v2/tasks", json=body)
        task = data.get("data", {}).get("task", {})
        return task.get("guid", "")  # type: ignore[no-any-return]
