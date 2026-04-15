"""飞书 IM 消息 API - 发送群卡片消息。

文档: https://open.feishu.cn/document/server-docs/im-v1/message/create
"""

from __future__ import annotations

import json
from typing import Any

from meeting_bot.feishu.client import FeishuClient


class MessageAPI:
    """IM 消息 API 包装。"""

    def __init__(self, client: FeishuClient) -> None:
        self.client = client

    async def send_card_to_chat(self, chat_id: str, card: dict[str, Any]) -> str:
        """发送交互式卡片到群 (receive_id_type=chat_id), 返回 message_id。"""
        data = await self.client.post(
            "/im/v1/messages",
            params={"receive_id_type": "chat_id"},
            json={
                "receive_id": chat_id,
                "msg_type": "interactive",
                "content": json.dumps(card, ensure_ascii=False),
            },
        )
        return data.get("data", {}).get("message_id", "")  # type: ignore[no-any-return]
