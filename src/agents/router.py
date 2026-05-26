"""
AGENT 4 — Router Agent

Role:
Take the final markdown briefing and deliver it through two channels:
- WhatsApp (concise executive summary + link to full version)
- Email (full markdown converted to professional HTML + plain text)

This is the last node before END in the StateGraph.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime
from typing import Any

from src.config.settings import get_settings
from src.database.connection import db_session
from src.database.models import RunLog
from src.tools.email_sender import email_send_tool
from src.tools.whatsapp_sender import whatsapp_send_tool

logger = logging.getLogger(__name__)
settings = get_settings()


class RouterAgent:
    """Multi-channel delivery of the weekly intelligence briefing."""

    def __init__(self):
        self.whatsapp_enabled = settings.whatsapp_enabled
        self.email_enabled = settings.email_enabled

    def _log(self, run_id: uuid.UUID, status: str, details: str, duration_ms: int | None = None) -> None:
        if not settings.enable_state_logging:
            return
        try:
            with db_session() as db:
                db.add(RunLog(run_id=run_id, node_name="router", status=status, output_summary=details[:2000], execution_time_ms=duration_ms))
        except Exception:
            pass

    def _build_whatsapp_summary(self, briefing: str) -> str:
        """Extract the Executive Summary section for WhatsApp (mobile-friendly)."""
        lines = briefing.splitlines()
        summary_lines = []
        capture = False
        for line in lines:
            if "Executive Summary" in line:
                capture = True
                continue
            if capture:
                if line.strip().startswith("##"):
                    break
                if line.strip():
                    summary_lines.append(line.strip())
        summary = "\n".join(summary_lines[:6]) or "Weekly RevOps briefing generated. Full version sent via email."
        return f"📊 *Weekly Revenue Intelligence*\n\n{summary}\n\n_Full briefing delivered to your inbox._"

    def deliver(
        self,
        briefing_draft: str,
        run_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        run_id = run_id or uuid.uuid4()
        start = time.time()
        self._log(run_id, "started", "Beginning multi-channel delivery")

        subject = f"Weekly Revenue Intelligence Briefing — {datetime.utcnow().strftime('%d %b %Y')}"
        whatsapp_summary = self._build_whatsapp_summary(briefing_draft)

        delivery_status: dict[str, Any] = {
            "run_id": str(run_id),
            "whatsapp": {"status": "skipped"},
            "email": {"status": "skipped"},
            "delivered_at": datetime.utcnow().isoformat(),
        }

        # WhatsApp
        if self.whatsapp_enabled:
            try:
                wa_result = whatsapp_send_tool.invoke(
                    {"message": whatsapp_summary, "run_id": str(run_id)}
                )
                delivery_status["whatsapp"] = wa_result
            except Exception as e:
                delivery_status["whatsapp"] = {"status": "failed", "error": str(e)}
                logger.error(f"WhatsApp delivery failed: {e}")

        # Email (always send full briefing)
        if self.email_enabled:
            try:
                email_result = email_send_tool.invoke(
                    {
                        "subject": subject,
                        "markdown_body": briefing_draft,
                        "run_id": str(run_id),
                    }
                )
                delivery_status["email"] = email_result
            except Exception as e:
                delivery_status["email"] = {"status": "failed", "error": str(e)}
                logger.error(f"Email delivery failed: {e}")

        duration = int((time.time() - start) * 1000)
        success = any(
            d.get("status") == "success" for d in [delivery_status["whatsapp"], delivery_status["email"]]
        )
        self._log(run_id, "success" if success else "partial", f"WhatsApp={delivery_status['whatsapp']['status']}, Email={delivery_status['email']['status']}", duration)

        return {"delivery_status": delivery_status, "router_completed_at": datetime.utcnow().isoformat()}


async def run_router(briefing_draft: str, run_id: uuid.UUID | None = None) -> dict[str, Any]:
    agent = RouterAgent()
    return agent.deliver(briefing_draft, run_id)
