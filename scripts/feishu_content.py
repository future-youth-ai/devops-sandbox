"""按 (kind, token) 调飞书 OpenAPI 拿文本内容.

支持的 kind:
  - minutes: 妙记 transcript (说话人 + 时间戳 + 文本)
  - docx:    新版云文档, blocks 拼接成 markdown-ish 文本
  - docs:    老版云文档, raw_content
  - wiki:    Wiki 节点, 先解析 obj_token + obj_type 再派发到 docx/doc

约定:
  - 所有 API 调用走 tenant_access_token, 调用方自己拿
  - code != 0 抛 FeishuFetchError, 不静默吞错
  - 分页接口必须吃完 has_more / page_token
"""

from __future__ import annotations

from typing import Any

import requests

FEISHU_BASE = "https://open.feishu.cn/open-apis"
TIMEOUT = 30


class FeishuFetchError(RuntimeError):
    """飞书接口调用失败."""


def _get(path: str, token: str, params: dict | None = None) -> dict[str, Any]:
    r = requests.get(
        f"{FEISHU_BASE}{path}",
        headers={"Authorization": f"Bearer {token}"},
        params=params,
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 0:
        raise FeishuFetchError(
            f"飞书 API 失败: code={data.get('code')} msg={data.get('msg')} path={path}"
        )
    return data  # type: ignore[no-any-return]


def get_tenant_token(app_id: str, app_secret: str) -> str:
    """获取 tenant_access_token (有效期 2 小时, 调用方自己处理缓存)."""
    r = requests.post(
        f"{FEISHU_BASE}/auth/v3/tenant_access_token/internal",
        json={"app_id": app_id, "app_secret": app_secret},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 0:
        raise FeishuFetchError(f"获取 tenant_access_token 失败: {data}")
    return data["tenant_access_token"]  # type: ignore[no-any-return]


def fetch_minutes(tenant_token: str, minute_token: str) -> str:
    """拼接妙记 transcript 各段为一个长字符串.

    格式: [发言人] 内容
    """
    data = _get(f"/minutes/v1/minutes/{minute_token}/transcript", tenant_token)
    segs = data.get("data", {}).get("transcripts", [])
    lines: list[str] = []
    for s in segs:
        speaker = s.get("speaker_name") or s.get("user_id") or "未知"
        # 不同版本字段名差异: text / sentence / content
        text = s.get("text") or s.get("sentence") or s.get("content") or ""
        if isinstance(text, str) and text.strip():
            lines.append(f"[{speaker}] {text.strip()}")
    return "\n".join(lines)


def fetch_docx(tenant_token: str, doc_id: str) -> str:
    """拉 docx 全部 blocks, 拼成可读文本 (heading 加 `## ` 前缀)."""
    all_blocks: list[dict[str, Any]] = []
    page_token: str | None = None
    while True:
        params: dict[str, Any] = {"page_size": 500}
        if page_token:
            params["page_token"] = page_token
        data = _get(f"/docx/v1/documents/{doc_id}/blocks", tenant_token, params)
        body = data.get("data", {})
        all_blocks.extend(body.get("items", []))
        if not body.get("has_more"):
            break
        page_token = body.get("page_token")
        if not page_token:
            break
    return _blocks_to_text(all_blocks)


def _blocks_to_text(blocks: list[dict[str, Any]]) -> str:
    """简化提取 text + heading1-9 的文字内容, 忽略图片/表格/代码块."""
    out: list[str] = []
    for b in blocks:
        t = b.get("block_type")
        if t == 2:  # text
            text = "".join(
                e.get("text_run", {}).get("content", "")
                for e in b.get("text", {}).get("elements", [])
            )
            if text.strip():
                out.append(text.strip())
        elif isinstance(t, int) and 3 <= t <= 11:  # heading 1-9 (block_type 3..11)
            level = t - 2  # heading{level}
            field = f"heading{level}"
            text = "".join(
                e.get("text_run", {}).get("content", "")
                for e in b.get(field, {}).get("elements", [])
            )
            if text.strip():
                prefix = "#" * min(level, 6)
                out.append(f"{prefix} {text.strip()}")
    return "\n\n".join(out)


def fetch_docs_legacy(tenant_token: str, doc_id: str) -> str:
    """老版 docs API: GET /doc/v2/{doc_id}/raw_content."""
    data = _get(f"/doc/v2/{doc_id}/raw_content", tenant_token)
    return data.get("data", {}).get("content", "") or ""  # type: ignore[no-any-return]


def fetch_wiki(tenant_token: str, wiki_token: str) -> str:
    """Wiki 节点: 先解析到底层 obj_token + obj_type, 再派发."""
    data = _get(
        "/wiki/v2/spaces/get_node",
        tenant_token,
        {"token": wiki_token},
    )
    node = data.get("data", {}).get("node", {})
    obj_type = node.get("obj_type")
    obj_token = node.get("obj_token")
    if not obj_token:
        raise FeishuFetchError(f"wiki 节点无 obj_token: {node}")
    if obj_type == "docx":
        return fetch_docx(tenant_token, obj_token)
    if obj_type == "doc":
        return fetch_docs_legacy(tenant_token, obj_token)
    raise FeishuFetchError(f"wiki 节点未支持的 obj_type: {obj_type}")


def fetch_content(kind: str, token: str, tenant_token: str) -> str:
    """统一入口, 按 kind 派发."""
    if kind == "minutes":
        return fetch_minutes(tenant_token, token)
    if kind == "docx":
        return fetch_docx(tenant_token, token)
    if kind == "docs":
        return fetch_docs_legacy(tenant_token, token)
    if kind == "wiki":
        return fetch_wiki(tenant_token, token)
    raise FeishuFetchError(f"未知 kind: {kind}")
