"""
Main LangGraph StateGraph Builder & Executor.

This is the heart of the Multi-Agent RevOps Orchestrator.

Features:
- Builds a directed graph with conditional routing
- Supports Redis checkpointing (resumable weekly jobs)
- Full observability via run_logs + state metadata
- Graceful degradation when external services are down
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from langgraph.checkpoint.redis import RedisSaver
from langgraph.graph import END, StateGraph

from src.config.settings import get_settings
from src.database.connection import db_session
from src.database.models import RunLog
from src.graph.edges import should_continue_to_writer
from src.graph.nodes import analyst_node, router_node, signal_scraper_node, writer_node
from src.graph.state import RevOpsState, create_initial_state

logger = logging.getLogger(__name__)
settings = get_settings()


def _log_graph_run(run_id: str, event: str, details: dict | None = None) -> None:
    """Lightweight graph-level audit log."""
    if not settings.enable_state_logging:
        return
    try:
        with db_session() as db:
            db.add(
                RunLog(
                    run_id=uuid.UUID(run_id),
                    node_name="orchestrator",
                    status=event,
                    output_summary=str(details)[:2000] if details else None,
                    metadata_json=details or {},
                )
            )
    except Exception as e:
        logger.error(f"Failed to write orchestrator log: {e}")


def build_revops_graph(checkpointer: Any | None = None) -> StateGraph:
    """
    Construct the complete RevOps StateGraph.

    Graph topology:
        START → signal_scraper → analyst → [conditional]
                                          ├─ (sufficient) → writer → router → END
                                          └─ (insufficient + retries < 2) → signal_scraper (loop)
    """
    graph = StateGraph(RevOpsState)

    # Register nodes
    graph.add_node("signal_scraper", signal_scraper_node)
    graph.add_node("analyst", analyst_node)
    graph.add_node("writer", writer_node)
    graph.add_node("router", router_node)

    # Define the flow
    graph.set_entry_point("signal_scraper")
    graph.add_edge("signal_scraper", "analyst")

    # Conditional routing after Analyst (the key architectural feature)
    graph.add_conditional_edges(
        "analyst",
        should_continue_to_writer,
        {
            "writer": "writer",
            "signal_scraper": "signal_scraper",
            "__end__": END,
        },
    )

    graph.add_edge("writer", "router")
    graph.add_edge("router", END)

    # Compile with optional Redis checkpointer
    compiled = graph.compile(checkpointer=checkpointer)
    logger.info("RevOps StateGraph compiled successfully")
    return compiled


def get_redis_checkpointer() -> RedisSaver | None:
    """Return a Redis-backed checkpointer if Redis is reachable, else None."""
    try:
        saver = RedisSaver(redis_url=settings.redis_url)
        # Quick smoke test
        saver.get({"configurable": {"thread_id": "health-check"}})
        logger.info("Redis checkpointer initialized")
        return saver
    except Exception as e:
        logger.warning(f"Redis unavailable for checkpointing: {e}. Running without persistence.")
        return None


def invoke_graph(
    initial_state: RevOpsState | None = None,
    thread_id: str | None = None,
    resume: bool = False,
) -> RevOpsState:
    """
    Synchronous convenience wrapper to run the full graph.

    Args:
        initial_state: Optional pre-populated state (rarely needed)
        thread_id: Used for Redis checkpointing / resumption
        resume: If True, will attempt to resume from last checkpoint

    Returns the final state after router node completes.
    """
    checkpointer = get_redis_checkpointer()
    app = build_revops_graph(checkpointer=checkpointer)

    state = initial_state or create_initial_state()
    run_id = state["run_id"]
    thread_id = thread_id or f"revops-weekly-{run_id}"

    _log_graph_run(run_id, "graph_invoked", {"thread_id": thread_id, "resume": resume})

    config = {"configurable": {"thread_id": thread_id}}

    if resume and checkpointer:
        # LangGraph will automatically load previous state
        logger.info(f"Attempting to resume graph from Redis (thread_id={thread_id})")

    # Run the graph to completion
    final_state = app.invoke(state, config=config)

    _log_graph_run(run_id, "graph_completed", {
        "nodes": final_state.get("run_metadata", {}).get("nodes_executed", []),
        "duration_ms": final_state.get("run_metadata", {}).get("total_duration_ms"),
    })

    return final_state
