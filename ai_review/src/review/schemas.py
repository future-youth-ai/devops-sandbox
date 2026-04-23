"""审核 API 的 pydantic schema.

按 .coderabbit.yaml 的 api 规则要求:
  - 所有路由必须有 pydantic request/response 模型
  - 错误响应禁止泄露内部栈信息
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.review.state import ReviewState


class ReviewSubmitRequest(BaseModel):
    """提交审核任务的请求体."""

    model_config = ConfigDict(extra="forbid")

    document_name: str = Field(min_length=1, max_length=255)
    document_type: Literal["pdf", "docx", "md", "txt"]
    tenant_id: str = Field(min_length=1, max_length=64)
    # 文档 URL 或已上传的存储引用 (具体实现由部署方决定)
    document_ref: str = Field(min_length=1, max_length=2048)
    # 可选的元数据, 会被脱敏后记入审计日志
    metadata: dict[str, str] | None = None


class ReviewTask(BaseModel):
    """审核任务的公开表示 (返回给前端/调用方)."""

    task_id: str
    tenant_id: str
    state: ReviewState
    document_name: str
    document_type: str
    created_at: datetime
    updated_at: datetime
    # 终态时带: approved=True / rejected=False / 终态前为 None
    approved: bool | None = None
    # LLM 审核给出的评分 0-100 (可选)
    score: int | None = None
    # 审核意见摘要 (终态时填)
    summary: str | None = None


class ReviewSubmitResponse(BaseModel):
    """提交审核任务后的响应."""

    task: ReviewTask
    message: str = "已进入审核队列"


class ErrorResponse(BaseModel):
    """统一错误响应体 - 不暴露内部栈."""

    error_code: str
    error_message: str
    request_id: str | None = None
