"""飞书统一 HTTP 客户端 - 管理 tenant_access_token + 自动重试。"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
import structlog
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from meeting_bot.config import Settings

log = structlog.get_logger(__name__)

FEISHU_BASE = "https://open.feishu.cn/open-apis"


class FeishuAPIError(Exception):
    """飞书 API 返回 code != 0 时抛出, 便于上层捕获。"""

    def __init__(self, code: int, msg: str, endpoint: str) -> None:
        super().__init__(f"[{endpoint}] code={code} msg={msg}")
        self.code = code
        self.msg = msg
        self.endpoint = endpoint


class FeishuClient:
    """线程安全的飞书客户端, 自动管理 tenant_access_token 生命周期。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._token: str | None = None
        self._token_expires_at: float = 0.0
        self._token_lock = asyncio.Lock()
        self._http = httpx.AsyncClient(
            base_url=FEISHU_BASE,
            timeout=httpx.Timeout(30.0, connect=10.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )

    async def close(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> FeishuClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    # ---------- tenant_access_token ----------
    async def _get_token(self) -> str:
        """带并发保护的 token 获取, 提前 60 秒刷新。"""
        now = time.time()
        if self._token and now < self._token_expires_at - 60:
            return self._token

        async with self._token_lock:
            # double-check: 可能已经被别的协程刷新了
            if self._token and time.time() < self._token_expires_at - 60:
                return self._token

            resp = await self._http.post(
                "/auth/v3/tenant_access_token/internal",
                json={
                    "app_id": self._settings.feishu_app_id,
                    "app_secret": self._settings.feishu_app_secret.get_secret_value(),
                },
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != 0:
                raise FeishuAPIError(
                    code=data.get("code", -1),
                    msg=data.get("msg", "unknown"),
                    endpoint="auth/v3/tenant_access_token/internal",
                )
            self._token = data["tenant_access_token"]
            self._token_expires_at = time.time() + int(data.get("expire", 7200))
            log.info("feishu_token_refreshed", expires_in=int(data.get("expire", 7200)))
            return self._token  # type: ignore[return-value]

    async def _headers(self) -> dict[str, str]:
        token = await self._get_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }

    # ---------- 通用请求封装 ----------
    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """统一请求入口 - 自动重试 + 错误码识别。"""
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
            retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
            reraise=True,
        ):
            with attempt:
                headers = await self._headers()
                resp = await self._http.request(
                    method, path, params=params, json=json, headers=headers
                )
                if resp.status_code == 401:
                    # token 过期兜底 - 清掉再重试一次
                    self._token = None
                    raise httpx.TransportError("token expired, retrying")
                resp.raise_for_status()
                data: dict[str, Any] = resp.json()
                if data.get("code") != 0:
                    raise FeishuAPIError(
                        code=data.get("code", -1),
                        msg=data.get("msg", "unknown"),
                        endpoint=path,
                    )
                return data
        raise RuntimeError("unreachable")  # pragma: no cover

    # ---------- 便捷方法 ----------
    async def get(self, path: str, **kwargs: Any) -> dict[str, Any]:
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> dict[str, Any]:
        return await self.request("POST", path, **kwargs)

    async def patch(self, path: str, **kwargs: Any) -> dict[str, Any]:
        return await self.request("PATCH", path, **kwargs)
