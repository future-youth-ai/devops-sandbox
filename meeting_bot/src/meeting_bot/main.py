"""FastAPI 入口 - /webhook/feishu 接收事件, 后台处理。

启动:
    uvicorn meeting_bot.main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import structlog
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

from meeting_bot import __version__
from meeting_bot.config import Settings, get_settings
from meeting_bot.dedup import DedupStore
from meeting_bot.email_sender import EmailSender
from meeting_bot.feishu.client import FeishuClient
from meeting_bot.feishu.events import (
    EventVerificationError,
    decrypt_payload,
    extract_event_id,
    extract_event_type,
    verify_signature,
)
from meeting_bot.pipeline import Pipeline


# ---------- logging ----------
def _configure_logging(level: str) -> None:
    logging.basicConfig(level=level.upper(), format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
    )


log = structlog.get_logger(__name__)


# ---------- lifespan ----------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    _configure_logging(settings.app_log_level)

    dedup = DedupStore(settings.app_sqlite_path)
    await dedup.init()

    feishu = FeishuClient(settings)
    email = EmailSender(settings)
    pipeline = Pipeline(settings, feishu, email)

    app.state.settings = settings
    app.state.dedup = dedup
    app.state.feishu = feishu
    app.state.pipeline = pipeline

    log.info("meeting_bot_started", version=__version__)
    try:
        yield
    finally:
        await feishu.close()
        log.info("meeting_bot_stopped")


app = FastAPI(
    title="Meeting Bot",
    version=__version__,
    description="飞书会议妙记自动化 - webhook → 云文档/Bitable/任务/群消息/邮件",
    lifespan=lifespan,
)


# ---------- healthcheck ----------
@app.get("/healthz")
async def healthz() -> dict[str, Any]:
    return {"status": "ok", "version": __version__}


# ---------- webhook ----------
@app.post("/webhook/feishu")
async def feishu_webhook(  # noqa: PLR0913
    request: Request,
    background: BackgroundTasks,
    x_lark_request_timestamp: str | None = Header(default=None),
    x_lark_request_nonce: str | None = Header(default=None),
    x_lark_signature: str | None = Header(default=None),
) -> JSONResponse:
    """飞书事件订阅回调。

    流程:
        1. 读原始 body
        2. 如果加密, 先验签再解密
        3. 处理 URL verification (返回 challenge)
        4. 正常事件: 幂等检查 → 后台任务 → 立即 200
    """
    settings: Settings = request.app.state.settings
    dedup: DedupStore = request.app.state.dedup
    pipeline: Pipeline = request.app.state.pipeline

    raw_body = await request.body()
    try:
        body_json = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"invalid json: {e}") from e

    encrypt_key = settings.feishu_event_encrypt_key.get_secret_value()

    # 签名校验 (仅加密模式发送这些 header)
    if x_lark_signature and x_lark_request_timestamp and x_lark_request_nonce:
        ok = verify_signature(
            timestamp=x_lark_request_timestamp,
            nonce=x_lark_request_nonce,
            encrypt_key=encrypt_key,
            raw_body=raw_body,
            signature_header=x_lark_signature,
        )
        if not ok:
            log.warning("feishu_signature_mismatch")
            raise HTTPException(status_code=401, detail="signature mismatch")

    # 解密
    payload: dict[str, Any]
    if "encrypt" in body_json:
        try:
            payload = decrypt_payload(body_json["encrypt"], encrypt_key)
        except EventVerificationError as e:
            raise HTTPException(status_code=400, detail=f"decrypt failed: {e}") from e
    else:
        payload = body_json

    # URL 验证 challenge
    if payload.get("type") == "url_verification":
        return JSONResponse({"challenge": payload.get("challenge")})

    # 正常事件
    event_id = extract_event_id(payload) or ""
    event_type = extract_event_type(payload) or ""

    if not event_id or not event_type:
        log.warning("feishu_event_missing_header", payload_keys=list(payload.keys()))
        return JSONResponse({"ok": True})

    if await dedup.is_processed(event_id):
        log.info("feishu_event_duplicate", event_id=event_id)
        return JSONResponse({"ok": True, "deduped": True})

    await dedup.mark_processed(event_id, event_type)

    # 根据事件类型分派
    background.add_task(_dispatch_event, pipeline, event_type, payload)
    return JSONResponse(
        {"ok": True, "queued": True, "event_type": event_type},
        status_code=status.HTTP_200_OK,
    )


async def _dispatch_event(
    pipeline: Pipeline, event_type: str, payload: dict[str, Any]
) -> None:
    """后台分派 - 根据事件类型调 pipeline。"""
    event = payload.get("event", {})

    try:
        # 妙记完成事件 (具体事件名以飞书文档为准)
        if event_type.startswith("vc.meeting.meeting_ended"):
            meeting_id = event.get("meeting", {}).get("id") or event.get("meeting_id")
            if not meeting_id:
                log.error("event_missing_meeting_id", event=event)
                return
            # 尝试从事件里拿 minute_token (可能为空, 需要后续用 meeting_id 查)
            minute_token = event.get("meeting", {}).get("minute_token")
            result = await pipeline.process(meeting_id, minute_token)
            log.info("pipeline_result", meeting_id=meeting_id, errors=result.errors)
            return

        if event_type.startswith("minutes."):
            minute_token = event.get("minute", {}).get("token") or event.get("minute_token")
            meeting_id = event.get("minute", {}).get("meeting_id") or ""
            if minute_token:
                result = await pipeline.process(meeting_id, minute_token)
                log.info("pipeline_result", minute_token=minute_token, errors=result.errors)
                return

        log.info("event_ignored", event_type=event_type)
    except Exception as e:
        log.exception("dispatch_failed", error=str(e), event_type=event_type)
