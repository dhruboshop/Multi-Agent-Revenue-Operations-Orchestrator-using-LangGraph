"""
WhatsApp Cloud API Sender Tool (Meta Graph API v21+).

Used exclusively by the Router Agent to deliver briefing summaries.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

import httpx
from langchain_core.tools import tool
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.config.settings import get_settings
from src.database.connection import db_session
from src.database.models import RunLog

logger = logging.getLogger(__name__)
settings = get_settings()

WHATSAPP_API_URL = "https://graph.facebook.com"


class WhatsAppSendError(Exception):
    """Raised when WhatsApp Cloud API returns a non-2xx response."""


class WhatsAppSender:
    """Production-grade WhatsApp Cloud API client with logging."""

    def __init__(self):
        self.access_token = settings.whatsapp_access_token
        self.phone_number_id = settings.whatsapp_phone_number_id
        self.api_version = settings.whatsapp_api_version
        self.recipient = settings.whatsapp_recipient_phone
        self.enabled = settings.whatsapp_enabled and settings.is_whatsapp_configured

    def _log(self, run_id: uuid.UUID, status: str, details: str, duration_ms: int | None = None) -> None:
        if not settings.enable_state_logging:
            return
        try:
            with db_session() as db:
                db.add(
                    RunLog(
                        run_id=run_id,
                        node_name="whatsapp_sender",
                        status=status,
                        output_summary=details[:2000],
                        execution_time_ms=duration_ms,
                        metadata_json={"recipient": self.recipient},
                    )
                )
        except Exception as e:
            logger.error(f"Failed to log WhatsApp delivery: {e}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1.5, min=2, max=12),
        retry=retry_if_exception_type((httpx.HTTPError, WhatsAppSendError)),
        reraise=True,
    )
    def send_text_message(self, message: str, run_id: uuid.UUID | None = None) -> dict[str, Any]:
        """
        Send a plain text WhatsApp message via Meta Cloud API.

        Returns the API response dict on success.
        """
        run_id = run_id or uuid.uuid4()
        start = datetime.utcnow()

        if not self.enabled:
            msg = "WhatsApp delivery skipped (not configured or disabled)"
            logger.warning(msg)
            self._log(run_id, "skipped", msg)
            return {"status": "skipped", "reason": "not_configured"}

        if len(message) > 4096:
            message = message[:4090] + "…"

        url = f"{WHATSAPP_API_URL}/{self.api_version}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": self.recipient,
            "type": "text",
            "text": {"body": message},
        }

        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(url, json=payload, headers=headers)
                duration_ms = int((datetime.utcnow() - start).total_seconds() * 1000)

                if resp.status_code >= 300:
                    error_detail = resp.text[:500]
                    self._log(run_id, "failed", f"HTTP {resp.status_code}: {error_detail}", duration_ms)
                    raise WhatsAppSendError(f"WhatsApp API error {resp.status_code}: {error_detail}")

                data = resp.json()
                self._log(run_id, "success", f"Message sent to {self.recipient}", duration_ms)
                logger.info(f"WhatsApp message delivered to {self.recipient}")
                return {"status": "success", "message_id": data.get("messages", [{}])[0].get("id"), "raw": data}

        except Exception as e:
            duration_ms = int((datetime.utcnow() - start).total_seconds() * 1000)
            self._log(run_id, "failed", str(e), duration_ms)
            logger.exception("WhatsApp send failed")
            raise


_whatsapp_sender = WhatsAppSender()


@tool("whatsapp_send")
def whatsapp_send_tool(message: str, run_id: str | None = None) -> dict[str, Any]:
    """
    Send a concise briefing summary via WhatsApp.

    The Router Agent uses this after the Writer produces the full markdown briefing.
    Message should be under 4000 characters and contain the most critical insights.
    """
    rid = uuid.UUID(run_id) if run_id else uuid.uuid4()
    return _whatsapp_sender.send_text_message(message, rid)
