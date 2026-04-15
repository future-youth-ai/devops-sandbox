"""飞书多维表格 (Bitable) API - 写入会议索引。

文档: https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table-record/create
"""

from __future__ import annotations

from typing import Any

from meeting_bot.feishu.client import FeishuClient


class BitableAPI:
    """多维表格 API 包装。"""

    def __init__(self, client: FeishuClient) -> None:
        self.client = client

    async def create_record(
        self,
        app_token: str,
        table_id: str,
        fields: dict[str, Any],
    ) -> str:
        """新增一行, 返回 record_id。

        fields 的 key 必须与表结构字段名完全匹配 (大小写敏感)。
        多选字段传 list, 日期字段传毫秒时间戳。
        """
        data = await self.client.post(
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/records",
            json={"fields": fields},
        )
        record = data.get("data", {}).get("record", {})
        return record.get("record_id", "")  # type: ignore[no-any-return]
