"""领域模型 - 会议纪要、行动项、参会人。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class Attendee(BaseModel):
    """参会人 (来自飞书 VC participants 接口)。"""

    model_config = ConfigDict(extra="ignore")

    open_id: str | None = None
    user_id: str | None = None
    name: str
    email: EmailStr | None = None


class ActionItem(BaseModel):
    """行动项 / 待办。"""

    model_config = ConfigDict(extra="ignore")

    title: str = Field(..., description="任务标题, 展示在飞书任务列表")
    description: str = Field("", description="任务详情")
    owner_open_id: str | None = Field(default=None, description="负责人 open_id (从参会人解析)")
    owner_name: str = Field("", description="负责人展示名")
    due_time: datetime | None = Field(default=None, description="截止时间")
    source_meeting_id: str = Field(..., description="来源会议 ID, 用于追溯")


class MeetingSummary(BaseModel):
    """结构化的会议纪要 - pipeline 的中间表示。"""

    model_config = ConfigDict(extra="ignore")

    meeting_id: str
    minute_token: str | None = None
    title: str
    start_time: datetime
    end_time: datetime
    attendees: list[Attendee] = Field(default_factory=list)
    summary: str = Field("", description="妙记生成的整体摘要")
    key_points: list[str] = Field(default_factory=list, description="要点/关键议题")
    decisions: list[str] = Field(default_factory=list, description="会议决议")
    action_items: list[ActionItem] = Field(default_factory=list)
    transcript_url: str | None = None
    minutes_url: str | None = None


class PipelineResult(BaseModel):
    """管道执行结果, 便于日志和测试。"""

    model_config = ConfigDict(extra="ignore")

    meeting_id: str
    docx_url: str | None = None
    bitable_record_id: str | None = None
    task_ids: list[str] = Field(default_factory=list)
    group_message_id: str | None = None
    email_sent_to: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
