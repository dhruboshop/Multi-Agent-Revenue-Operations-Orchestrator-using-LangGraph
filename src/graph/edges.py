"""
Conditional Edges for the RevOps LangGraph.

Core logic:
- After Analyst node, decide whether we have "sufficient" data.
- If insufficient AND retry_count < MAX_RETRIES → loop back to signal_scraper
- Otherwise proceed to writer → router → END
"""

from __future__ import annotations

import logging
from typing import Literal

from src.graph.state import RevOpsState

logger = logging.getLogger(__name__)

MAX_RETRIES = 2


def should_continue_to_writer(state: RevOpsState) -> Literal["writer", "signal_scraper", "__end__"]:
    """
    Decision function after Analyst node.

    Returns:
        "writer"        → proceed normally
        "signal_scraper" → loop back for more data (retry)
        "__end__"       → abort early (max retries exceeded with still-insufficient data)
    """
    retry_count = state.get("retry_count", 0)
    analysed = state.get("analysed_data", {})
    raw_signals = state.get("raw_signals", [])

    # Heuristic for "sufficient data"
    has_external = len(raw_signals) >= 3
    has_anomalies_or_summary = bool(analysed.get("anomalies")) or bool(analysed.get("strategic_summary"))
    has_internal_data = bool(analysed.get("raw_internal_results"))

    sufficient = has_external and (has_anomalies_or_summary or has_internal_data)

    if sufficient:
        logger.info("Analyst produced sufficient data → proceeding to Writer")
        return "writer"

    if retry_count < MAX_RETRIES:
        new_count = retry_count + 1
        logger.warning(f"Insufficient data after Analyst (signals={len(raw_signals)}). Retrying scraper (attempt {new_count}/{MAX_RETRIES})")
        # We mutate state here for the next pass (LangGraph will merge)
        state["retry_count"] = new_count  # type: ignore[index]
        return "signal_scraper"

    # Exhausted retries — still go forward with whatever we have (graceful degradation)
    logger.error("Max retries exhausted with insufficient data. Proceeding to Writer with degraded quality.")
    return "writer"
