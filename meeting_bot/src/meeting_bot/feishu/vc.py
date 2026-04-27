"""飞书视频会议 (VC) API - 获取会议信息与参会人。

官方文档 / SDK (v2_main):
  - 会议详情:   https://open.feishu.cn/document/server-docs/vc-v1/meeting/get
                GET /open-apis/vc/v1/meetings/:meeting_id
  - 参会人列表: https://open.feishu.cn/document/server-docs/vc-v1/meeting/get_participant_list
                GET /open-apis/vc/v1/participant_list  (注意: 不是子路径!)
  - SDK 源:     lark_oapi/api/vc/v1/model/get_participant_list_request.py

参会人列表 API 设计说明:
  - Feishu 使用 meeting_no + 会议时间范围定位参会人列表, 而不是 meeting_id
    (历史版本曾是 /vc/v1/meetings/{id}/list_by_no_meeting 形式, 现已废弃)
  - 因此调用方需要先 get_meeting 拿到 meeting_no + start_time + end_time,
    再调用 list_participants
"""

from __future__ import annotations

from typing import Any

from meeting_bot.feishu.client import FeishuClient


class VCAPI:
    """视频会议 API 包装。"""

    def __init__(self, client: FeishuClient) -> None:
        self.client = client

    async def get_meeting(self, meeting_id: str) -> dict[str, Any]:
        """获取会议基本信息 (含 meeting_no / start_time / end_time / topic)。

        Endpoint: GET /vc/v1/meetings/:meeting_id
        """
        data = await self.client.get(f"/vc/v1/meetings/{meeting_id}")
        return data.get("data", {}).get("meeting", {})  # type: ignore[no-any-return]

    async def list_participants(
        self,
        meeting_no: str,
        meeting_start_time: int,
        meeting_end_time: int,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        """分页拉取参会人列表。

        Endpoint: GET /vc/v1/participant_list
        Required query params: meeting_no, meeting_start_time, meeting_end_time
        Optional: page_size (<=100), page_token, meeting_status, user_id, room_id,
                  webinar_user_role, user_id_type

        Args:
            meeting_no: 会议号 (通常 8-10 位数字, 对应会议室号)
            meeting_start_time: 会议开始时间, 秒级 Unix 时间戳
            meeting_end_time: 会议结束时间, 秒级 Unix 时间戳
            page_size: 单页大小, 最大 100

        Returns:
            所有分页的参会人记录合并 (list[dict])
        """
        if not meeting_no:
            raise ValueError("list_participants: meeting_no 不能为空")
        if meeting_start_time <= 0 or meeting_end_time <= 0:
            raise ValueError(
                "list_participants: meeting_start_time / meeting_end_time 必须为正 Unix 时间戳"
            )
        if meeting_end_time < meeting_start_time:
            raise ValueError(
                "list_participants: meeting_end_time 必须 >= meeting_start_time "
                f"(got start={meeting_start_time}, end={meeting_end_time})"
            )
        if page_size <= 0:
            raise ValueError(f"list_participants: page_size 必须 > 0, got {page_size}")

        # 飞书上限为 100, 同时做下限 1 防止 0 或负数透传
        effective_page_size = min(max(page_size, 1), 100)

        all_participants: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            params: dict[str, Any] = {
                "meeting_no": meeting_no,
                "meeting_start_time": meeting_start_time,
                "meeting_end_time": meeting_end_time,
                "page_size": effective_page_size,
            }
            if page_token:
                params["page_token"] = page_token
            data = await self.client.get("/vc/v1/participant_list", params=params)
            body = data.get("data", {})
            all_participants.extend(body.get("participants", []))
            if not body.get("has_more"):
                break
            page_token = body.get("page_token")
            if not page_token:
                break
        return all_participants
