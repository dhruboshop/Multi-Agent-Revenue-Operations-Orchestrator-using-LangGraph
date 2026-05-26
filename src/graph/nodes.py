"""
LangGraph Node Functions for RevOps Orchestrator.

Each node is a thin, observable wrapper around one of the four agents.
Every node:
- Records start time
- Calls the corresponding agent
- Logs to PostgreSQL run_logs via the agent
- Merges results into state
- Records node execution in run_metadata
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

from src.agents.analyst import run_analyst
from src.agents.router import run_router
from src.agents.signal_scraper import run_signal_scraper
from src.agents.writer import run_writer
from src.graph.state import RevOpsState, get_run_id

logger = logging.getLogger(__name__)


async def signal_scraper_node(state: RevOpsState) -> dict[str, Any]:
    """Node wrapper for Agent 1."""
    run_id = get_run_id(state)
    logger.info(f"[signal_scraper_node] Starting run_id={run_id}")

    start = time.time()
    result = await run_signal_scraper(run_id=run_id)  # type: ignore[arg-type]

    duration_ms = int((time.time() - start) * 1000)

    metadata = state.get("run_metadata", {})
    nodes = metadata.get("nodes_executed", [])
    nodes.append({"node": "signal_scraper", "ts": datetime.utcnow().isoformat(), "duration_ms": duration_ms})

    return {
        "raw_signals": result.get("raw_signals", []),
        "run_metadata": {**metadata, "nodes_executed": nodes},
    }


async def analyst_node(state: RevOpsState) -> dict[str, Any]:
    """Node wrapper for Agent 2."""
    run_id = get_run_id(state)
    raw_signals = state.get("raw_signals", [])
    logger.info(f"[analyst_node] Starting with {len(raw_signals)} signals, run_id={run_id}")

    start = time.time()
    result = await run_analyst(raw_signals=raw_signals, run_id=run_id)  # type: ignore[arg-type]

    duration_ms = int((time.time() - start) * 1000)

    metadata = state.get("run_metadata", {})
    nodes = metadata.get("nodes_executed", [])
    nodes.append({"node": "analyst", "ts": datetime.utcnow().isoformat(), "duration_ms": duration_ms})

    return {
        "analysed_data": result.get("analysed_data", {}),
        "run_metadata": {**metadata, "nodes_executed": nodes},
    }


async def writer_node(state: RevOpsState) -> dict[str, Any]:
    """Node wrapper for Agent 3."""
    run_id = get_run_id(state)
    analysed = state.get("analysed_data", {})
    raw_signals = state.get("raw_signals", [])
    logger.info(f"[writer_node] Generating briefing, run_id={run_id}")

    start = time.time()
    result = await run_writer(analysed_data=analysed, raw_signals=raw_signals, run_id=run_id)

    duration_ms = int((time.time() - start) * 1000)

    metadata = state.get("run_metadata", {})
    nodes = metadata.get("nodes_executed", [])
    nodes.append({"node": "writer", "ts": datetime.utcnow().isoformat(), "duration_ms": duration_ms})

    return {
        "briefing_draft": result.get("briefing_draft", ""),
        "run_metadata": {**metadata, "nodes_executed": nodes},
    }


async def router_node(state: RevOpsState) -> dict[str, Any]:
    """Node wrapper for Agent 4 (final delivery)."""
    run_id = get_run_id(state)
    briefing = state.get("briefing_draft", "")
    logger.info(f"[router_node] Delivering briefing, run_id={run_id}")

    start = time.time()
    result = await run_router(briefing_draft=briefing, run_id=run_id)

    duration_ms = int((time.time() - start) * 1000)

    metadata = state.get("run_metadata", {})
    nodes = metadata.get("nodes_executed", [])
    nodes.append({"node": "router", "ts": datetime.utcnow().isoformat(), "duration_ms": duration_ms})

    completed_at = datetime.utcnow().isoformat()
    total_duration = sum(n.get("duration_ms", 0) for n in nodes)

    return {
        "delivery_status": result.get("delivery_status", {}),
        "run_metadata": {
            **metadata,
            "nodes_executed": nodes,
            "completed_at": completed_at,
            "total_duration_ms": total_duration,
        },
    }
