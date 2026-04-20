#!/usr/bin/env python3
"""CodeRabbit 报告 -> 飞书 Webhook 同步.

监听 GitHub 事件, 过滤出 CodeRabbit 的"有信息量"输出推送到飞书群.
按照策略 B, 只推以下两类, 忽略 walkthrough / ack / 进度提示, 避免刷屏:

  1. Summary 评论         (issue_comment, body 含 "Summary by CodeRabbit")
  2. Review 结论          (pull_request_review, state ∈ {changes_requested, approved})

环境变量:
  FEISHU_WEBHOOK_URL        (必需, 飞书群机器人 webhook)
  EVENT_NAME                (issue_comment | pull_request_review)
  REPO_NAME                 (owner/repo)
  PR_NUMBER, PR_TITLE, PR_URL
  SENDER_LOGIN              (事件触发者, 用于双保险过滤)
  COMMENT_BODY              (issue_comment.comment.body 或 pull_request_review.review.body)
  REVIEW_STATE              (pull_request_review 事件专用)
"""

from __future__ import annotations

import os
import re
import sys

import requests

TIMEOUT = 15
CODERABBIT_BOT = "coderabbitai[bot]"
MAX_BODY_LEN = 1500  # 飞书卡片单元素建议不超过 2KB, 留余量

SUMMARY_PATTERN = re.compile(r"Summary by CodeRabbit", re.IGNORECASE)


def should_skip(event: str, sender: str, body: str, state: str) -> tuple[bool, str]:
    """返回 (是否跳过, 原因)."""
    if sender != CODERABBIT_BOT:
        return True, f"非 CodeRabbit 事件 (sender={sender})"

    if event == "issue_comment":
        # 只推 Summary 评论
        if not SUMMARY_PATTERN.search(body or ""):
            return True, "非 Summary 评论 (可能是 walkthrough/ack/进度)"
        return False, "summary"

    if event == "pull_request_review":
        # 只推有结论的 review
        if state not in {"changes_requested", "approved"}:
            return True, f"review state={state} 不推送"
        return False, f"review-{state}"

    return True, f"未支持的事件类型: {event}"


def truncate(body: str, limit: int = MAX_BODY_LEN) -> str:
    if not body:
        return "(无内容)"
    if len(body) <= limit:
        return body
    return body[:limit] + "\n\n...(已截断, 完整内容见 PR)"


def build_card(kind: str, repo: str, pr_number: str, pr_title: str, pr_url: str, body: str) -> dict:
    """构造飞书交互式卡片."""
    title_map = {
        "summary": ("📝", "CodeRabbit 审查摘要", "blue"),
        "review-approved": ("✅", "CodeRabbit 审查通过", "green"),
        "review-changes_requested": ("❌", "CodeRabbit 要求修改", "red"),
    }
    emoji, title, color = title_map.get(kind, ("🐰", f"CodeRabbit [{kind}]", "grey"))

    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": color,
                "title": {
                    "tag": "plain_text",
                    "content": f"{emoji} {title} · {repo}#{pr_number}",
                },
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": f"**PR**: [{pr_title}]({pr_url})"},
                },
                {"tag": "hr"},
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": truncate(body)},
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "查看 PR"},
                            "url": pr_url,
                            "type": "primary",
                        }
                    ],
                },
            ],
        },
    }


def main() -> int:
    event = os.environ.get("EVENT_NAME", "")
    sender = os.environ.get("SENDER_LOGIN", "")
    body = os.environ.get("COMMENT_BODY", "") or ""
    state = os.environ.get("REVIEW_STATE", "")

    skip, reason = should_skip(event, sender, body, state)
    if skip:
        print(f"⏭️  跳过: {reason}")
        return 0

    webhook = os.environ.get("FEISHU_WEBHOOK_URL")
    if not webhook:
        print("::warning::缺少 FEISHU_WEBHOOK_URL, 跳过推送")
        return 0

    repo = os.environ.get("REPO_NAME", "")
    pr_number = os.environ.get("PR_NUMBER", "")
    pr_title = os.environ.get("PR_TITLE", "")
    pr_url = os.environ.get("PR_URL", "")

    card = build_card(reason, repo, pr_number, pr_title, pr_url, body)

    resp = requests.post(webhook, json=card, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    # 飞书群 webhook: 成功返回 code=0 或 StatusCode=0
    if data.get("code", 0) != 0 and data.get("StatusCode", 0) != 0:
        raise RuntimeError(f"飞书群消息发送失败: {data}")
    print(f"✅ 已推送到飞书: kind={reason}, PR #{pr_number}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except requests.HTTPError as e:
        body = ""
        try:
            body = e.response.text  # type: ignore[union-attr]
        except Exception:
            pass
        print(f"::error::HTTP 错误: {e}\n{body}", file=sys.stderr)
        raise SystemExit(1)
    except Exception as e:
        print(f"::error::CodeRabbit 同步脚本异常: {e}", file=sys.stderr)
        raise SystemExit(1)
