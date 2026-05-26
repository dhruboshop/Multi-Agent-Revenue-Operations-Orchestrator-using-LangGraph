"""
LangGraph State Definition for Multi-Agent RevOps Orchestrator.

This TypedDict is the single source of truth passed between every node.
It is checkpointed to Redis after each node (when Redis is available).
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages  # not strictly needed, but kept for future agent messages


class RevOpsState(TypedDict, total=False):
    """
    Core state object for the RevOps multi-agent graph.

    Fields and ownership:
    - run_id: Unique identifier for the entire weekly run (used for audit + resumption)
    - raw_signals: Output of Signal Scraper Agent (list of dicts)
    - analysed_data: Output of Analyst Agent (structured JSON with anomalies + recommendations)
    - briefing_draft: Markdown string produced by Writer Agent
    - delivery_status: Result of Router Agent (WhatsApp + Email status)
    - run_metadata: Timestamps, retry counts, execution summary
    - retry_count: Number of times we looped back to Signal Scraper (max 2)
    - error: Last error encountered (for graceful degradation)
    """

    run_id: str
    raw_signals: list[dict[str, Any]]
    analysed_data: dict[str, Any]
    briefing_draft: str
    delivery_status: dict[str, Any]
    run_metadata: dict[str, Any]
    retry_count: int
    error: str | None


def create_initial_state(run_id: str | None = None) -> RevOpsState:
    """Factory for a fresh state object at START of graph."""
    rid = run_id or str(uuid.uuid4())
    return RevOpsState(
        run_id=rid,
        raw_signals=[],
        analysed_data={},
        briefing_draft="",
        delivery_status={},
        run_metadata={
            "started_at": None,
            "completed_at": None,
            "nodes_executed": [],
            "total_duration_ms": 0,
        },
        retry_count=0,
        error=None,
    )


def get_run_id(state: RevOpsState) -> str:
    return state.get("run_id", str(uuid.uuid4()))
