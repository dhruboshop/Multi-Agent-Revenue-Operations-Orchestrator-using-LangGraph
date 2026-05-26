"""
AGENT 2 — Analyst Agent

Role:
Cross-reference external market signals against internal PostgreSQL revenue data.
Runs exactly three targeted analytical queries and uses Claude to surface anomalies
and strategic implications.

Queries executed (hard-coded for determinism and auditability):
1. Revenue vs target variance by dealer + region (latest 3 months)
2. Month-over-month growth trend for Tier-A dealers
3. Concentration risk: Top 3 dealers % of total revenue (latest period)
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime
from typing import Any

import anthropic

from src.config.settings import get_settings
from src.database.connection import db_session
from src.database.models import RunLog
from src.tools.database_query import database_query_tool

logger = logging.getLogger(__name__)
settings = get_settings()


ANALYST_SYSTEM_PROMPT = """You are a senior revenue operations analyst for a B2B industrial equipment manufacturer in India.

You have just received results from three SQL queries against the company's internal revenue warehouse plus fresh external market signals.

Your job:
- Identify real business anomalies (variance >12% vs target, sudden growth drops, regional concentration risk, competitive threats)
- Quantify impact in INR and percentage where possible
- Suggest 2-3 concrete recommended actions with owner and timeframe
- Output STRICTLY valid JSON with the keys shown below. No markdown, no extra text.

OUTPUT SCHEMA:
{
  "anomalies": [
    {
      "type": "variance|growth|concentration|competitive",
      "severity": "high|medium|low",
      "description": "one sentence",
      "affected_dealers": ["DLR-XXX"],
      "estimated_impact_inr": number or null,
      "evidence": "short quote from data"
    }
  ],
  "strategic_summary": "2-3 sentence synthesis of what the data + signals mean for the next 30-45 days",
  "recommended_actions": [
    {
      "action": "specific action",
      "owner": "Sales Head / RevOps / Regional Manager",
      "timeframe": "this week / next 30 days",
      "priority": "P0|P1|P2"
    }
  ]
}
"""


class AnalystAgent:
    """Cross-references internal data with external signals and flags anomalies."""

    def __init__(self, anthropic_client: anthropic.Anthropic | None = None):
        self.client = anthropic_client or anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = settings.claude_model

    def _log(self, run_id: uuid.UUID, status: str, details: str, duration_ms: int | None = None) -> None:
        if not settings.enable_state_logging:
            return
        try:
            with db_session() as db:
                db.add(RunLog(run_id=run_id, node_name="analyst", status=status, output_summary=details[:3000], execution_time_ms=duration_ms))
        except Exception as e:
            logger.error(f"RunLog failed: {e}")

    def _run_three_queries(self, run_id: uuid.UUID) -> list[dict[str, Any]]:
        """Execute the three canonical analytical questions."""
        questions = [
            "For the most recent 3 months available, show each dealer with revenue vs target variance (actual - target) and percentage variance. Include region and tier. Sort by largest negative variance first.",
            "Calculate month-over-month revenue growth percentage for all Tier-A dealers over the last 4 periods. Return dealer name, period, revenue, and MoM growth %.",
            "For the single most recent period in the database, calculate total revenue across all dealers and the percentage contributed by the top 3 dealers (by revenue). Also list those 3 dealers with their individual revenue and % share.",
        ]

        results = []
        for q in questions:
            try:
                res = database_query_tool.invoke({"question": q})
                results.append(res)
            except Exception as e:
                logger.error(f"Query failed: {q[:60]}... → {e}")
                results.append({"question": q, "success": False, "error": str(e)})
        return results

    def analyze(
        self,
        raw_signals: list[dict[str, Any]],
        run_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """
        Main entry point for the Analyst Agent node.
        Returns analysed_data payload consumed by Writer Agent.
        """
        run_id = run_id or uuid.uuid4()
        start = time.time()
        self._log(run_id, "started", f"Analysing {len(raw_signals)} external signals")

        internal_results = self._run_three_queries(run_id)

        # Prepare context for Claude
        signals_text = "\n".join(
            f"- [{s.get('signal_type')}] {s.get('competitor')}: {s.get('summary')}" for s in raw_signals[:8]
        ) or "No fresh external signals captured in this run."

        internal_text = ""
        for i, r in enumerate(internal_results, 1):
            internal_text += f"\n--- Query {i} ---\n"
            internal_text += f"Question: {r.get('question', '')}\n"
            if r.get("success"):
                internal_text += f"Interpretation: {r.get('interpretation', '')}\n"
                internal_text += f"Rows (first 5): {str(r.get('results', []))[:800]}\n"
            else:
                internal_text += f"Error: {r.get('error')}\n"

        prompt = f"""{ANALYST_SYSTEM_PROMPT}

EXTERNAL MARKET SIGNALS (last 14 days):
{signals_text}

INTERNAL REVENUE ANALYSIS (3 canonical queries):
{internal_text}

Return ONLY the JSON object. No other text.
"""

        try:
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=2200,
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}],
            )
            content = resp.content[0].text.strip() if resp.content else "{}"
            import json, re

            content = re.sub(r"^```json\s*", "", content)
            content = re.sub(r"```$", "", content).strip()
            analysed = json.loads(content)

            duration = int((time.time() - start) * 1000)
            anomaly_count = len(analysed.get("anomalies", []))
            self._log(run_id, "success", f"{anomaly_count} anomalies flagged", duration)

            return {
                "analysed_data": analysed,
                "raw_internal_results": internal_results,
                "external_signals_used": len(raw_signals),
                "analysis_completed_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            duration = int((time.time() - start) * 1000)
            self._log(run_id, "failed", str(e), duration)
            logger.exception("Analyst agent failed")

            # Graceful degradation — still return something usable
            return {
                "analysed_data": {
                    "anomalies": [],
                    "strategic_summary": "Analyst agent encountered an error during Claude interpretation. Manual review of internal data recommended.",
                    "recommended_actions": [],
                },
                "error": str(e),
                "raw_internal_results": internal_results,
            }


async def run_analyst(raw_signals: list[dict], run_id: uuid.UUID | None = None) -> dict[str, Any]:
    agent = AnalystAgent()
    return agent.analyze(raw_signals, run_id)
