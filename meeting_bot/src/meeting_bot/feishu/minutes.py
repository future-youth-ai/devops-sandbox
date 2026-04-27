"""飞书妙记 (Minutes) API - 获取会议转写与统计信息。

官方文档 / SDK (v2_main):
  - 获取妙记信息:   https://open.feishu.cn/document/server-docs/docs/minutes-v1/minute/get
                    GET /open-apis/minutes/v1/minutes/:minute_token
  - 获取转写:       https://open.feishu.cn/document/server-docs/docs/minutes-v1/minute-transcript/get
                    GET /open-apis/minutes/v1/minutes/:minute_token/transcript
  - 获取统计:       https://open.feishu.cn/document/server-docs/docs/minutes-v1/minute-statistics/get
                    GET /open-apis/minutes/v1/minutes/:minute_token/statistics
  - SDK 源:         lark_oapi/api/minutes/v1/model/*_request.py

⚠️ 注意:
  - 妙记 OpenAPI 需要在开放平台 "权限管理" 里开通 `minutes:*` scope,
    且租户套餐支持。如无权限, 这些接口会返回 99991672 (权限不足)。
  - Feishu OpenAPI 并不直接暴露 "AI 摘要 / 行动项 / 要点 / 决议" 这类字段,
    那些字段是妙记 UI 层基于转写生成的; 如需在自动化管道里使用,
    需要客户端侧基于 transcript 做 LLM 后处理, 或从别的摘要源拿。
"""

from __future__ import annotations

from typing import Any

from meeting_bot.feishu.client import FeishuClient


class MinutesAPI:
    """妙记 API 包装。"""

    def __init__(self, client: FeishuClient) -> None:
        self.client = client

    async def get_minute(self, minute_token: str) -> dict[str, Any]:
        """获取妙记基本信息 (含 title / url / duration / cover / owner_id)。

        Endpoint: GET /minutes/v1/minutes/:minute_token
        """
        data = await self.client.get(f"/minutes/v1/minutes/{minute_token}")
        return data.get("data", {}).get("minute", {})  # type: ignore[no-any-return]

    async def get_transcript(self, minute_token: str) -> list[dict[str, Any]]:
        """获取分段转写 (发言人 + 时间戳 + 文本)。

        Endpoint: GET /minutes/v1/minutes/:minute_token/transcript
        """
        data = await self.client.get(f"/minutes/v1/minutes/{minute_token}/transcript")
        return data.get("data", {}).get("transcripts", [])  # type: ignore[no-any-return]

    async def get_statistics(self, minute_token: str) -> dict[str, Any]:
        """获取妙记统计信息。

        Endpoint: GET /minutes/v1/minutes/:minute_token/statistics

        ⚠️ 字段对齐说明:
            Feishu 返回的 statistics 字段是会议时长/发言占比等结构化数据,
            并不包含 "summary/key_points/decisions/action_items"。
            调用方 (pipeline.py) 通过 dict.get(..., default) 安全降级:
            如果某字段缺失, 结果会是空字符串或空列表, 不会抛异常。
            若需要真正的 AI 摘要, 请基于 get_transcript() 做 LLM 后处理。
        """
        data = await self.client.get(f"/minutes/v1/minutes/{minute_token}/statistics")
        return data.get("data", {})  # type: ignore[no-any-return]
