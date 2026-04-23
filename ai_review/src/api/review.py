"""审核任务路由.

实现范围: 仅骨架 - 提交任务会返回 PENDING 状态的 ReviewTask.
真实 LLM 编排会由后续 PR 接入.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status

from src.review.schemas import (
    ErrorResponse,
    ReviewSubmitRequest,
    ReviewSubmitResponse,
    ReviewTask,
)
from src.review.state import ReviewState

router = APIRouter(prefix="/review", tags=["review"])

# 进程内内存存储 - 仅用于骨架 demo, 真实部署需替换为 DB
_TASKS: dict[str, ReviewTask] = {}


@router.post(
    "/submit",
    response_model=ReviewSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={400: {"model": ErrorResponse}},
)
async def submit_review(payload: ReviewSubmitRequest) -> ReviewSubmitResponse:
    """提交审核任务, 返回 PENDING 态 task."""
    task_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    task = ReviewTask(
        task_id=task_id,
        tenant_id=payload.tenant_id,
        state=ReviewState.PENDING,
        document_name=payload.document_name,
        document_type=payload.document_type,
        created_at=now,
        updated_at=now,
    )
    _TASKS[task_id] = task
    return ReviewSubmitResponse(task=task)


@router.get(
    "/{task_id}",
    response_model=ReviewTask,
    responses={404: {"model": ErrorResponse}},
)
async def get_review(task_id: str) -> ReviewTask:
    """查询审核任务状态."""
    task = _TASKS.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return task
