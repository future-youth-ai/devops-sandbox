"""飞书通讯录 (Contact) API - 邮箱/手机号 → open_id 映射。

文档: https://open.feishu.cn/document/server-docs/contact-v3/user/batch_get_id
"""

from __future__ import annotations

from meeting_bot.feishu.client import FeishuClient


class ContactAPI:
    """通讯录 API 包装。"""

    def __init__(self, client: FeishuClient) -> None:
        self.client = client

    async def emails_to_open_ids(self, emails: list[str]) -> dict[str, str]:
        """批量把邮箱转成 open_id, 找不到的邮箱会从结果中缺失。"""
        if not emails:
            return {}

        data = await self.client.post(
            "/contact/v3/users/batch_get_id",
            params={"user_id_type": "open_id"},
            json={"emails": emails},
        )
        result: dict[str, str] = {}
        for item in data.get("data", {}).get("user_list", []):
            email = item.get("email")
            open_id = item.get("user_id")
            if email and open_id:
                result[email] = open_id
        return result
