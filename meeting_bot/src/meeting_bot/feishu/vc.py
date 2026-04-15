"""飞书视频会议 (VC) API - 获取会议信息与参会人。

文档: https://open.feishu.cn/document/server-docs/vc-v1/meeting/
"""

from __future__ import annotations

from typing import Any

from meeting_bot.feishu.client import FeishuClient


class VCAPI:
    """视频会议 API 包装。"""

    def __init__(self, client: FeishuClient) -> None:
        self.client = client

    async def get_meeting(self, meeting_id: str) -> dict[str, Any]:
        """获取会议基本信息。"""
        data = await self.client.get(f"/vc/v1/meetings/{meeting_id}")
        return data.get("data", {}).get("meeting", {})  # type: ignore[no-any-return]

    async def list_participants(
        self, meeting_id: str, page_size: int = 100
    ) -> list[dict[str, Any]]:
        """分页拉取参会人列表。"""
        # TODO: 核对最新路径 - 历史版本曾为 /vc/v1/meetings/{id}/list_by_no_meeting
        all_participants: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            params: dict[str, Any] = {"page_size": page_size}
            if page_token:
                params["page_token"] = page_token
            data = await self.client.get(
                f"/vc/v1/meetings/{meeting_id}/participants",
                params=params,
            )
            body = data.get("data", {})
            all_participants.extend(body.get("participants", []))
            if not body.get("has_more"):
                break
            page_token = body.get("page_token")
            if not page_token:
                break
        return all_participants
