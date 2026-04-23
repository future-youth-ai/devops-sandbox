"""VC + Minutes API 路径回归测试.

保证:
  - list_participants 打到 /open-apis/vc/v1/participant_list
    且携带 meeting_no + meeting_start_time + meeting_end_time 查询参数
  - get_transcript 打到 /minutes/v1/minutes/:token/transcript
  - get_statistics 打到 /minutes/v1/minutes/:token/statistics
  - 分页通过 has_more + page_token 正确串联
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from meeting_bot.config import Settings
from meeting_bot.feishu.client import FeishuClient
from meeting_bot.feishu.minutes import MinutesAPI
from meeting_bot.feishu.vc import VCAPI


def _tenant_token_response() -> httpx.Response:
    return httpx.Response(
        200,
        json={"code": 0, "msg": "ok", "tenant_access_token": "t-abc", "expire": 7200},
    )


@pytest.fixture
async def client(settings: Settings):  # type: ignore[no-untyped-def]
    c = FeishuClient(settings)
    yield c
    await c.close()


@pytest.mark.asyncio
@respx.mock
async def test_list_participants_calls_correct_endpoint(client: FeishuClient) -> None:
    respx.post("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal").mock(
        return_value=_tenant_token_response()
    )
    route = respx.get("https://open.feishu.cn/open-apis/vc/v1/participant_list").mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 0,
                "msg": "ok",
                "data": {
                    "participants": [{"participant_name": "Alice"}],
                    "has_more": False,
                },
            },
        )
    )

    vc = VCAPI(client)
    parts = await vc.list_participants(
        meeting_no="12345678",
        meeting_start_time=1700000000,
        meeting_end_time=1700003600,
    )

    assert parts == [{"participant_name": "Alice"}]
    assert route.called
    req = route.calls[0].request
    # 校验关键 query params
    qs = dict(httpx.QueryParams(req.url.query.decode()))
    assert qs["meeting_no"] == "12345678"
    assert qs["meeting_start_time"] == "1700000000"
    assert qs["meeting_end_time"] == "1700003600"
    # 不再包含已废弃的路径形式
    assert "/meetings/" not in req.url.path


@pytest.mark.asyncio
@respx.mock
async def test_list_participants_paginates(client: FeishuClient) -> None:
    respx.post("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal").mock(
        return_value=_tenant_token_response()
    )

    # 两页: 第一页 has_more=True + page_token, 第二页 has_more=False
    pages: list[dict[str, Any]] = [
        {
            "code": 0,
            "msg": "ok",
            "data": {
                "participants": [{"participant_name": "Alice"}],
                "has_more": True,
                "page_token": "pt-2",
            },
        },
        {
            "code": 0,
            "msg": "ok",
            "data": {
                "participants": [{"participant_name": "Bob"}],
                "has_more": False,
            },
        },
    ]
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        body = pages[call_count["n"]]
        call_count["n"] += 1
        return httpx.Response(200, json=body)

    respx.get("https://open.feishu.cn/open-apis/vc/v1/participant_list").mock(side_effect=handler)

    vc = VCAPI(client)
    parts = await vc.list_participants(
        meeting_no="12345678",
        meeting_start_time=1700000000,
        meeting_end_time=1700003600,
    )

    assert [p["participant_name"] for p in parts] == ["Alice", "Bob"]
    assert call_count["n"] == 2


@pytest.mark.asyncio
async def test_list_participants_rejects_bad_inputs(client: FeishuClient) -> None:
    vc = VCAPI(client)
    with pytest.raises(ValueError, match="meeting_no"):
        await vc.list_participants(meeting_no="", meeting_start_time=1, meeting_end_time=2)
    with pytest.raises(ValueError, match="meeting_start_time"):
        await vc.list_participants(
            meeting_no="123", meeting_start_time=0, meeting_end_time=1
        )


@pytest.mark.asyncio
@respx.mock
async def test_minutes_get_transcript(client: FeishuClient) -> None:
    respx.post("https://open.feishu.cn/open-apis/auth/v3/tenant_access_function/internal").mock(
        return_value=_tenant_token_response()
    )
    respx.post("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal").mock(
        return_value=_tenant_token_response()
    )
    route = respx.get(
        "https://open.feishu.cn/open-apis/minutes/v1/minutes/mtk123/transcript"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 0,
                "msg": "ok",
                "data": {
                    "transcripts": [
                        {"speaker": "Alice", "start": 0, "end": 5, "text": "hello"}
                    ]
                },
            },
        )
    )

    m = MinutesAPI(client)
    segs = await m.get_transcript("mtk123")
    assert segs == [{"speaker": "Alice", "start": 0, "end": 5, "text": "hello"}]
    assert route.called


@pytest.mark.asyncio
@respx.mock
async def test_minutes_get_statistics(client: FeishuClient) -> None:
    respx.post("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal").mock(
        return_value=_tenant_token_response()
    )
    route = respx.get(
        "https://open.feishu.cn/open-apis/minutes/v1/minutes/mtk123/statistics"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 0,
                "msg": "ok",
                "data": {"statistics": {"duration": 3600}},
            },
        )
    )

    m = MinutesAPI(client)
    data = await m.get_statistics("mtk123")
    # 字段可能缺失 - 验证 .get 降级安全
    assert data.get("summary", "") == ""
    assert data.get("key_points", []) == []
    assert data.get("statistics", {}).get("duration") == 3600
    assert route.called
