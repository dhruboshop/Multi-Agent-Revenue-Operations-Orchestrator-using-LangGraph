"""
Database Query Tool with Natural Language Interface.

This is the core tool used by the Analyst Agent.

Features:
- Takes natural language question about revenue performance
- Uses Claude (via direct Anthropic SDK) to generate safe, read-only SQL
- Executes the SQL with strict guardrails (only SELECT allowed)
- Returns structured results + Claude's interpretation
- Full audit logging to run_logs
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime
from typing import Any

import anthropic
from langchain_core.tools import tool
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.config.settings import get_settings
from src.database.connection import db_session
from src.database.models import RunLog

logger = logging.getLogger(__name__)
settings = get_settings()

# Schema context injected into Claude prompt (critical for correctness)
DATABASE_SCHEMA_CONTEXT = """
You are an expert PostgreSQL analyst for a B2B industrial equipment company.

DATABASE SCHEMA:

Table: dealers
  - id (uuid, PK)
  - dealer_code (varchar, unique)
  - name (varchar)
  - region (varchar: North, West, South, East)
  - city (varchar)
  - state (varchar)
  - tier (varchar: A, B, C)
  - is_active (boolean)

Table: revenue_records
  - id (uuid, PK)
  - dealer_id (uuid, FK → dealers.id)
  - period (date)          -- first day of the month, e.g. 2025-03-01
  - revenue_inr (float)
  - units_sold (integer)
  - target_inr (float)
  - growth_pct (float, nullable)  -- MoM growth %

Relationships:
  revenue_records.dealer_id = dealers.id

STRICT RULES FOR SQL GENERATION:
1. ONLY generate SELECT statements. Never INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE.
2. Always use explicit column lists. Never use SELECT * in production queries.
3. Always qualify columns with table aliases when joining.
4. Use parameterized queries style but return raw SQL with literals (we will execute safely).
5. For date filtering, use period >= '2024-10-01' style (YYYY-MM-DD).
6. For aggregates, use meaningful aliases: total_revenue, avg_revenue, dealer_count.
7. Limit results to 50 rows maximum unless explicitly asked for trends.
8. If the question cannot be answered with the schema, return: -- CANNOT_ANSWER: <reason>

Return ONLY the SQL query. No explanation, no markdown fences, no comments except the CANNOT_ANSWER case.
"""


class DatabaseQueryTool:
    """Encapsulates NL→SQL→execution pipeline."""

    def __init__(self, anthropic_client: anthropic.Anthropic | None = None):
        self.client = anthropic_client or anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = settings.claude_model

    def _log_execution(
        self,
        run_id: uuid.UUID,
        node_name: str,
        status: str,
        input_summary: str | None = None,
        output_summary: str | None = None,
        error: str | None = None,
        duration_ms: int | None = None,
    ) -> None:
        """Write structured execution log to PostgreSQL."""
        if not settings.enable_state_logging:
            return
        try:
            with db_session() as db:
                log = RunLog(
                    run_id=run_id,
                    node_name=node_name,
                    status=status,
                    input_summary=input_summary[:2000] if input_summary else None,
                    output_summary=output_summary[:4000] if output_summary else None,
                    error_message=error,
                    execution_time_ms=duration_ms,
                    metadata_json={},
                )
                db.add(log)
        except Exception as e:
            logger.error(f"Failed to write run_log: {e}")

    def generate_sql(self, question: str) -> str:
        """Ask Claude to translate natural language question into safe SQL."""
        prompt = f"""{DATABASE_SCHEMA_CONTEXT}

QUESTION FROM ANALYST AGENT:
{question}

SQL:"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=800,
                temperature=0.0,  # Deterministic for SQL generation
                messages=[{"role": "user", "content": prompt}],
            )
            sql = response.content[0].text.strip() if response.content else ""
            return sql
        except Exception as e:
            logger.error(f"Claude SQL generation failed: {e}")
            raise

    def _is_safe_select(self, sql: str) -> bool:
        """Guardrail: only allow single SELECT statements."""
        sql_clean = sql.strip().upper()
        if not sql_clean.startswith("SELECT"):
            return False
        forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE", "GRANT", ";--"]
        return not any(word in sql_clean for word in forbidden)

    def execute_query(self, sql: str) -> list[dict[str, Any]]:
        """Execute read-only query with row limiting."""
        if not self._is_safe_select(sql):
            raise ValueError(f"Unsafe SQL rejected by guardrail: {sql[:120]}...")

        # Force safety limit
        if "LIMIT" not in sql.upper():
            sql = sql.rstrip(";") + " LIMIT 50;"

        with db_session() as db:
            result = db.execute(text(sql))
            columns = list(result.keys())
            rows = [dict(zip(columns, row)) for row in result.fetchall()]
            return rows

    def analyze(self, question: str, run_id: uuid.UUID | None = None) -> dict[str, Any]:
        """
        Full pipeline: NL question → safe SQL → execution → Claude interpretation.
        Returns structured payload for Analyst Agent.
        """
        start = datetime.utcnow()
        run_id = run_id or uuid.uuid4()

        self._log_execution(run_id, "database_query_tool", "started", input_summary=question)

        try:
            sql = self.generate_sql(question)
            logger.info(f"Generated SQL for question: {question[:80]}...")

            if sql.startswith("-- CANNOT_ANSWER"):
                return {
                    "question": question,
                    "sql": None,
                    "results": [],
                    "interpretation": sql,
                    "success": False,
                }

            rows = self.execute_query(sql)

            # Ask Claude to interpret the results (second call)
            interpretation_prompt = f"""You are a senior revenue analyst.

QUESTION: {question}

SQL EXECUTED:
{sql}

QUERY RESULTS (JSON):
{rows}

Write a concise 2-4 sentence business interpretation. Flag any anomalies (e.g. >15% variance vs target, unusual regional concentration, sudden drops). Be specific with numbers.
"""
            interp_response = self.client.messages.create(
                model=self.model,
                max_tokens=600,
                temperature=0.3,
                messages=[{"role": "user", "content": interpretation_prompt}],
            )
            interpretation = interp_response.content[0].text.strip() if interp_response.content else ""

            duration_ms = int((datetime.utcnow() - start).total_seconds() * 1000)

            self._log_execution(
                run_id,
                "database_query_tool",
                "success",
                output_summary=f"rows={len(rows)}",
                duration_ms=duration_ms,
            )

            return {
                "question": question,
                "sql": sql,
                "results": rows,
                "interpretation": interpretation,
                "success": True,
                "row_count": len(rows),
            }

        except Exception as e:
            duration_ms = int((datetime.utcnow() - start).total_seconds() * 1000)
            self._log_execution(
                run_id,
                "database_query_tool",
                "failed",
                error=str(e),
                duration_ms=duration_ms,
            )
            logger.exception("Database query tool failed")
            raise


# Singleton instance + LangChain tool wrapper
_db_tool_instance = DatabaseQueryTool()


@tool("database_query")
def database_query_tool(question: str) -> dict[str, Any]:
    """
    Natural language interface to the internal revenue PostgreSQL database.

    Use this to answer questions such as:
    - "What was total revenue in South region last quarter?"
    - "Which dealer has the largest gap between actual and target in March 2025?"
    - "Show month-over-month growth trend for tier-A dealers"

    The tool will generate safe SQL, execute it, and return both raw results and
    a business interpretation generated by Claude.
    """
    return _db_tool_instance.analyze(question)
