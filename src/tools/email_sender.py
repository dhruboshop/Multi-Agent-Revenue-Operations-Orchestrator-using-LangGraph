"""
SMTP Email Sender Tool (SendGrid compatible).

Used by Router Agent to deliver the full structured markdown briefing
as both HTML and plain-text email.
"""

from __future__ import annotations

import logging
import smtplib
import uuid
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from langchain_core.tools import tool
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config.settings import get_settings
from src.database.connection import db_session
from src.database.models import RunLog

logger = logging.getLogger(__name__)
settings = get_settings()


class EmailSender:
    """Robust SMTP sender with HTML + text multipart and audit logging."""

    def __init__(self):
        self.host = settings.smtp_host
        self.port = settings.smtp_port
        self.username = settings.smtp_username
        self.password = settings.smtp_password
        self.from_email = settings.smtp_from_email
        self.from_name = settings.smtp_from_name
        self.to_emails = settings.smtp_to_email_list
        self.use_tls = settings.smtp_use_tls
        self.enabled = settings.email_enabled and bool(self.password)

    def _log(self, run_id: uuid.UUID, status: str, details: str, duration_ms: int | None = None) -> None:
        if not settings.enable_state_logging:
            return
        try:
            with db_session() as db:
                db.add(
                    RunLog(
                        run_id=run_id,
                        node_name="email_sender",
                        status=status,
                        output_summary=details[:2500],
                        execution_time_ms=duration_ms,
                        metadata_json={"recipients": self.to_emails},
                    )
                )
        except Exception as e:
            logger.error(f"Failed to log email delivery: {e}")

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=2, min=3, max=15),
        reraise=True,
    )
    def send_briefing(
        self,
        subject: str,
        markdown_body: str,
        html_body: str | None = None,
        run_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """
        Send the weekly revenue intelligence briefing via email.

        Args:
            subject: Email subject line
            markdown_body: Full markdown content (used as text/plain fallback)
            html_body: Optional pre-rendered HTML version
            run_id: For audit trail

        Returns delivery status.
        """
        run_id = run_id or uuid.uuid4()
        start = datetime.utcnow()

        if not self.enabled:
            logger.warning("Email delivery disabled or SMTP password missing")
            self._log(run_id, "skipped", "Email not configured")
            return {"status": "skipped", "reason": "not_configured"}

        if not self.to_emails:
            raise ValueError("No recipients configured in SMTP_TO_EMAILS")

        # Build multipart message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{self.from_name} <{self.from_email}>"
        msg["To"] = ", ".join(self.to_emails)

        # Plain text version (markdown as-is is acceptable)
        msg.attach(MIMEText(markdown_body, "plain", "utf-8"))

        # HTML version (basic conversion if none provided)
        if html_body is None:
            html_body = self._markdown_to_html(markdown_body)
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        try:
            with smtplib.SMTP(self.host, self.port, timeout=20) as server:
                if self.use_tls:
                    server.starttls()
                if self.username and self.password:
                    server.login(self.username, self.password)
                server.sendmail(self.from_email, self.to_emails, msg.as_string())

            duration_ms = int((datetime.utcnow() - start).total_seconds() * 1000)
            self._log(run_id, "success", f"Email sent to {len(self.to_emails)} recipients", duration_ms)
            logger.info(f"Briefing email delivered to {self.to_emails}")
            return {"status": "success", "recipients": self.to_emails, "subject": subject}

        except Exception as e:
            duration_ms = int((datetime.utcnow() - start).total_seconds() * 1000)
            self._log(run_id, "failed", str(e), duration_ms)
            logger.exception("Email delivery failed")
            raise

    @staticmethod
    def _markdown_to_html(md: str) -> str:
        """Very lightweight markdown → HTML for email (no external deps)."""
        import re

        html = md
        # Headers
        html = re.sub(r"^### (.*)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
        html = re.sub(r"^## (.*)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
        html = re.sub(r"^# (.*)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)
        # Bold / italic
        html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
        html = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html)
        # Lists
        html = re.sub(r"^- (.*)$", r"<li>\1</li>", html, flags=re.MULTILINE)
        html = re.sub(r"(<li>.*</li>)", r"<ul>\1</ul>", html, flags=re.DOTALL)
        # Paragraphs
        html = html.replace("\n\n", "</p><p>")
        html = f"<html><body><div style='font-family:Arial,Helvetica,sans-serif;max-width:720px'>{html}</div></body></html>"
        return html


_email_sender = EmailSender()


@tool("email_send")
def email_send_tool(
    subject: str,
    markdown_body: str,
    run_id: str | None = None,
) -> dict[str, Any]:
    """
    Send the complete weekly revenue intelligence briefing via email.

    The Router Agent calls this with the full markdown produced by the Writer Agent.
    """
    rid = uuid.UUID(run_id) if run_id else uuid.uuid4()
    return _email_sender.send_briefing(subject, markdown_body, run_id=rid)
