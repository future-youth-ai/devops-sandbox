"""异步 SMTP 邮件发送 - 用于把会议纪要推送给参会人。"""

from __future__ import annotations

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib
import structlog

from meeting_bot.config import Settings

log = structlog.get_logger(__name__)


class EmailSender:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def send_html(
        self,
        to_addresses: list[str],
        subject: str,
        html_body: str,
        text_fallback: str = "",
    ) -> None:
        """发送 HTML 邮件, text_fallback 为无法渲染 HTML 时的纯文本。"""
        if not to_addresses:
            log.warning("email_skipped_no_recipients")
            return

        msg = MIMEMultipart("alternative")
        msg["From"] = self.settings.smtp_from_address
        msg["To"] = ", ".join(to_addresses)
        msg["Subject"] = subject
        if text_fallback:
            msg.attach(MIMEText(text_fallback, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        try:
            await aiosmtplib.send(
                msg,
                hostname=self.settings.smtp_host,
                port=self.settings.smtp_port,
                username=self.settings.smtp_username or None,
                password=(
                    self.settings.smtp_password.get_secret_value()
                    if self.settings.smtp_password.get_secret_value()
                    else None
                ),
                start_tls=self.settings.smtp_use_tls,
            )
            log.info("email_sent", recipients=len(to_addresses), subject=subject)
        except Exception as e:
            log.error("email_failed", error=str(e), recipients=to_addresses)
            raise
