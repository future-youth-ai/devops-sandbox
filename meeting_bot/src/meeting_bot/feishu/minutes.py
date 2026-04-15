"""飞书妙记 (Minutes) API - 获取会议转写与 AI 摘要。

⚠️ 注意:
  - 妙记 OpenAPI 需要在开放平台 "权限管理" 里开通 `minutes:*` scope,
    且租户套餐支持。如无权限, 这些接口会返回 99991672 (权限不足)。
  - 接口路径近一年有变动, 部署前请对照最新文档:
    https://open.feishu.cn/document/server-docs/docs/minutes-v1/minute/overview
"""

from __future__ import annotations

from typing import Any

from meeting_bot.feishu.client import FeishuClient


class MinutesAPI:
    """妙记 API 包装。"""

    def __init__(self, client: FeishuClient) -> None:
        self.client = client

    async def get_minute(self, minute_token: str) -> dict[str, Any]:
        """获取妙记基本信息 (含标题、URL、时长)。"""
        data = await self.client.get(f"/minutes/v1/minutes/{minute_token}")
        return data.get("data", {}).get("minute", {})  # type: ignore[no-any-return]

    async def get_transcript(self, minute_token: str) -> list[dict[str, Any]]:
        """获取分段转写 (发言人 + 时间戳 + 文本)。

        TODO: 最新路径可能是 /minutes/v1/minutes/{token}/transcript
              或 /minutes/v1/minutes/{token}/statistics/transcripts,
              请核对官方文档。
        """
        data = await self.client.get(f"/minutes/v1/minutes/{minute_token}/transcript")
        return data.get("data", {}).get("transcripts", [])  # type: ignore[no-any-return]

    async def get_summary(self, minute_token: str) -> dict[str, Any]:
        """获取妙记 AI 摘要 (标题/要点/决议/行动项)。

        返回字段示例 (以实际返回为准):
            {
                "summary": "整体摘要文本",
                "key_points": ["要点1", ...],
                "decisions": ["决议1", ...],
                "action_items": [
                    {"assignee": "张三", "task": "...", "due": "2026-04-20"}
                ]
            }
        """
        data = await self.client.get(f"/minutes/v1/minutes/{minute_token}/summary")
        return data.get("data", {})  # type: ignore[no-any-return]
