"""飞书云文档 (Docx) API - 从模板复制并填充会议纪要。

文档: https://open.feishu.cn/document/server-docs/docs/docs/docx-v1/overview
"""

from __future__ import annotations

from typing import Any

from meeting_bot.feishu.client import FeishuClient


class DocsAPI:
    """云文档 API 包装。"""

    def __init__(self, client: FeishuClient) -> None:
        self.client = client

    async def copy_from_template(
        self, template_token: str, title: str, folder_token: str | None = None
    ) -> dict[str, Any]:
        """从模板复制一份新文档, 返回新文档 meta。

        对应接口: POST /drive/v1/files/{template_token}/copy
        body: { "name": "...", "type": "docx", "folder_token": "..." }
        """
        body: dict[str, Any] = {"name": title, "type": "docx"}
        if folder_token:
            body["folder_token"] = folder_token
        data = await self.client.post(
            f"/drive/v1/files/{template_token}/copy",
            json=body,
        )
        return data.get("data", {}).get("file", {})  # type: ignore[no-any-return]

    async def get_document(self, document_id: str) -> dict[str, Any]:
        data = await self.client.get(f"/docx/v1/documents/{document_id}")
        return data.get("data", {}).get("document", {})  # type: ignore[no-any-return]

    async def list_root_blocks(self, document_id: str) -> list[dict[str, Any]]:
        """列出文档所有 block (用于定位要填充的占位符)。"""
        all_blocks: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            params: dict[str, Any] = {"page_size": 500}
            if page_token:
                params["page_token"] = page_token
            data = await self.client.get(
                f"/docx/v1/documents/{document_id}/blocks",
                params=params,
            )
            body = data.get("data", {})
            all_blocks.extend(body.get("items", []))
            if not body.get("has_more"):
                break
            page_token = body.get("page_token")
        return all_blocks

    async def append_text_block(self, document_id: str, parent_block_id: str, text: str) -> None:
        """在指定 block 下追加一段文本。"""
        await self.client.patch(
            f"/docx/v1/documents/{document_id}/blocks/{parent_block_id}/children",
            json={
                "children": [
                    {
                        "block_type": 2,  # text block
                        "text": {
                            "elements": [
                                {
                                    "text_run": {
                                        "content": text,
                                        "text_element_style": {},
                                    }
                                }
                            ],
                            "style": {},
                        },
                    }
                ],
                "index": -1,
            },
        )

    def build_view_url(self, document_id: str) -> str:
        """构建可直接访问的文档 URL。"""
        return f"https://docs.feishu.cn/docx/{document_id}"
