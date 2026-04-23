"""主编排管道 - 把妙记数据扇出到云文档/Bitable/任务/群消息/邮件。

调用入口: await Pipeline(...).process(meeting_id)
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog
from jinja2 import Environment, FileSystemLoader, select_autoescape

from meeting_bot.config import Settings
from meeting_bot.email_sender import EmailSender
from meeting_bot.feishu.bitable import BitableAPI
from meeting_bot.feishu.client import FeishuClient
from meeting_bot.feishu.contact import ContactAPI
from meeting_bot.feishu.docs import DocsAPI
from meeting_bot.feishu.messages import MessageAPI
from meeting_bot.feishu.minutes import MinutesAPI
from meeting_bot.feishu.tasks import TaskAPI
from meeting_bot.feishu.vc import VCAPI
from meeting_bot.models import ActionItem, Attendee, MeetingSummary, PipelineResult

log = structlog.get_logger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"


class Pipeline:
    """会议处理主管道。"""

    def __init__(
        self,
        settings: Settings,
        client: FeishuClient,
        email_sender: EmailSender | None = None,
    ) -> None:
        self.settings = settings
        self.client = client
        self.vc = VCAPI(client)
        self.minutes = MinutesAPI(client)
        self.docs = DocsAPI(client)
        self.bitable = BitableAPI(client)
        self.tasks = TaskAPI(client)
        self.contact = ContactAPI(client)
        self.messages = MessageAPI(client)
        self.email_sender = email_sender or EmailSender(settings)

        self.jinja_env = Environment(
            loader=FileSystemLoader(TEMPLATES_DIR),
            autoescape=select_autoescape(["html", "xml"]),
            enable_async=False,
        )

    async def process(self, meeting_id: str, minute_token: str | None = None) -> PipelineResult:
        """主入口。按顺序: 拉数据 → 结构化 → 并发扇出。"""
        result = PipelineResult(meeting_id=meeting_id)
        log.info("pipeline_start", meeting_id=meeting_id, minute_token=minute_token)

        try:
            summary = await self._collect(meeting_id, minute_token)
        except Exception as e:
            log.error("collect_failed", error=str(e), meeting_id=meeting_id)
            result.errors.append(f"collect: {e}")
            return result

        # 并发扇出 4 个飞书操作 + 邮件
        results = await asyncio.gather(
            self._create_doc(summary),
            self._write_bitable(summary),
            self._create_tasks(summary),
            self._send_group_card(summary),
            self._send_email(summary),
            return_exceptions=True,
        )

        docx_result, bitable_result, tasks_result, message_result, email_result = results

        if isinstance(docx_result, BaseException):
            result.errors.append(f"docs: {docx_result}")
        else:
            result.docx_url = docx_result

        if isinstance(bitable_result, BaseException):
            result.errors.append(f"bitable: {bitable_result}")
        else:
            result.bitable_record_id = bitable_result

        if isinstance(tasks_result, BaseException):
            result.errors.append(f"tasks: {tasks_result}")
        else:
            result.task_ids = tasks_result or []

        if isinstance(message_result, BaseException):
            result.errors.append(f"messages: {message_result}")
        else:
            result.group_message_id = message_result

        if isinstance(email_result, BaseException):
            result.errors.append(f"email: {email_result}")
        else:
            result.email_sent_to = email_result or []

        log.info(
            "pipeline_done",
            meeting_id=meeting_id,
            errors=len(result.errors),
            docx_url=result.docx_url,
        )
        return result

    # ---------- Step 1: 收集 + 结构化 ----------
    async def _collect(self, meeting_id: str, minute_token: str | None) -> MeetingSummary:
        """从飞书 VC + 妙记拉数据, 生成 MeetingSummary。"""
        meeting_info = await self.vc.get_meeting(meeting_id)

        # Feishu participant_list API 需要 meeting_no + 时间范围, 不是 meeting_id
        # (详见 meeting_bot.feishu.vc.VCAPI.list_participants 文档)
        meeting_no = str(meeting_info.get("meeting_no") or "")
        start_ts = int(meeting_info.get("start_time") or 0)
        end_ts = int(meeting_info.get("end_time") or 0)
        if meeting_no and start_ts > 0 and end_ts > 0:
            participants_raw = await self.vc.list_participants(
                meeting_no=meeting_no,
                meeting_start_time=start_ts,
                meeting_end_time=end_ts,
            )
        else:
            log.warning(
                "participants_skipped_missing_meeting_info",
                meeting_id=meeting_id,
                has_meeting_no=bool(meeting_no),
                has_start=start_ts > 0,
                has_end=end_ts > 0,
            )
            participants_raw = []

        attendees = [
            Attendee(
                name=p.get("participant_name", "未知"),
                open_id=p.get("user_id"),
                email=p.get("email"),
            )
            for p in participants_raw
        ]

        minute_data: dict[str, Any] = {}
        summary_data: dict[str, Any] = {}
        if minute_token:
            minute_data = await self.minutes.get_minute(minute_token)
            try:
                # Feishu OpenAPI 不直接返回 "AI 摘要"; 这里拉 /statistics,
                # summary/key_points/decisions/action_items 字段缺失时下方
                # .get(..., default) 会降级为空值, 不会崩溃.
                summary_data = await self.minutes.get_statistics(minute_token)
            except Exception as e:
                log.warning("minutes_statistics_unavailable", error=str(e))

        # 解析妙记行动项 - 字段名以实际 API 返回为准
        raw_actions = summary_data.get("action_items", []) or []
        name_to_openid = {a.name: a.open_id for a in attendees if a.open_id}

        action_items: list[ActionItem] = []
        for item in raw_actions:
            assignee_name = item.get("assignee") or item.get("owner") or ""
            due_str = item.get("due") or item.get("due_time")
            due_time: datetime | None = None
            if due_str:
                try:
                    due_time = datetime.fromisoformat(due_str)
                except (ValueError, TypeError):
                    due_time = None
            action_items.append(
                ActionItem(
                    title=item.get("task") or item.get("title") or "未命名任务",
                    description=item.get("description", ""),
                    owner_name=assignee_name,
                    owner_open_id=name_to_openid.get(assignee_name),
                    due_time=due_time,
                    source_meeting_id=meeting_id,
                )
            )

        return MeetingSummary(
            meeting_id=meeting_id,
            minute_token=minute_token,
            title=meeting_info.get("topic") or minute_data.get("title") or f"会议 {meeting_id}",
            start_time=_parse_ts(meeting_info.get("start_time")),
            end_time=_parse_ts(meeting_info.get("end_time")),
            attendees=attendees,
            summary=summary_data.get("summary", ""),
            key_points=summary_data.get("key_points", []),
            decisions=summary_data.get("decisions", []),
            action_items=action_items,
            transcript_url=minute_data.get("url"),
            minutes_url=minute_data.get("url"),
        )

    # ---------- Step 2a: 云文档 ----------
    async def _create_doc(self, summary: MeetingSummary) -> str:
        file_meta = await self.docs.copy_from_template(
            template_token=self.settings.feishu_doc_template_token,
            title=f"【会议纪要】{summary.title}",
        )
        doc_id = file_meta.get("token") or file_meta.get("file_token") or ""
        if not doc_id:
            raise RuntimeError(f"copy_from_template 未返回 doc token: {file_meta}")

        # 用模板渲染出 Markdown 正文, 逐段追加到文档
        template = self.jinja_env.get_template("meeting_doc.md.j2")
        rendered = template.render(summary=summary)

        # 找到根 block, 一次性追加所有文本 (简化: 每段一个 text block)
        blocks = await self.docs.list_root_blocks(doc_id)
        root_block_id = blocks[0]["block_id"] if blocks else doc_id

        for paragraph in rendered.split("\n\n"):
            if paragraph.strip():
                await self.docs.append_text_block(doc_id, root_block_id, paragraph.strip())

        return self.docs.build_view_url(doc_id)

    # ---------- Step 2b: Bitable 索引 ----------
    async def _write_bitable(self, summary: MeetingSummary) -> str:
        fields = {
            "会议ID": summary.meeting_id,
            "标题": summary.title,
            "开始时间": int(summary.start_time.timestamp() * 1000),
            "结束时间": int(summary.end_time.timestamp() * 1000),
            "参会人数": len(summary.attendees),
            "决议数": len(summary.decisions),
            "行动项数": len(summary.action_items),
            "摘要": summary.summary[:500],
            "妙记链接": summary.minutes_url or "",
        }
        return await self.bitable.create_record(
            app_token=self.settings.feishu_bitable_app_token,
            table_id=self.settings.feishu_bitable_table_id,
            fields=fields,
        )

    # ---------- Step 2c: 任务 ----------
    async def _create_tasks(self, summary: MeetingSummary) -> list[str]:
        task_ids: list[str] = []
        for item in summary.action_items:
            assignees = [item.owner_open_id] if item.owner_open_id else []
            task_id = await self.tasks.create_task(
                summary=f"[{summary.title}] {item.title}",
                description=(
                    f"{item.description}\n\n"
                    f"来源: 会议 {summary.meeting_id}\n"
                    f"负责人: {item.owner_name or '未指定'}"
                ),
                assignee_open_ids=[a for a in assignees if a],
                due_time=item.due_time,
            )
            if task_id:
                task_ids.append(task_id)
        return task_ids

    # ---------- Step 2d: 群卡片 ----------
    async def _send_group_card(self, summary: MeetingSummary) -> str:
        template = self.jinja_env.get_template("group_card.json.j2")
        rendered = template.render(summary=summary)
        import json as _json

        card = _json.loads(rendered)
        return await self.messages.send_card_to_chat(
            chat_id=self.settings.feishu_summary_chat_id,
            card=card,
        )

    # ---------- Step 2e: 邮件 ----------
    async def _send_email(self, summary: MeetingSummary) -> list[str]:
        recipients = [str(a.email) for a in summary.attendees if a.email]
        if not recipients:
            return []

        template = self.jinja_env.get_template("email.html.j2")
        html_body = template.render(summary=summary)
        await self.email_sender.send_html(
            to_addresses=recipients,
            subject=f"【会议纪要】{summary.title}",
            html_body=html_body,
            text_fallback=summary.summary,
        )
        return recipients


def _parse_ts(value: Any) -> datetime:
    """容错解析时间戳 (秒/毫秒/ISO 字符串)。"""
    if value is None:
        return datetime.now(tz=UTC)
    if isinstance(value, int | float):
        ts = float(value)
        if ts > 1e12:
            ts /= 1000.0
        return datetime.fromtimestamp(ts, tz=UTC)
    if isinstance(value, str):
        if value.isdigit():
            return _parse_ts(int(value))
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(tz=UTC)
    return datetime.now(tz=UTC)
