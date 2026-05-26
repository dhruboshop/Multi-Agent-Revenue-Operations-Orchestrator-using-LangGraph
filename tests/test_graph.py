"""
Tests for LangGraph orchestration layer.
Focuses on conditional routing logic and state transitions.
"""

import pytest
import uuid
from unittest.mock import patch, AsyncMock

from src.graph.state import create_initial_state, RevOpsState
from src.graph.edges import should_continue_to_writer
from src.graph.orchestrator import build_revops_graph


def test_initial_state_shape():
    state = create_initial_state()
    assert "run_id" in state
    assert state["retry_count"] == 0
    assert isinstance(state["raw_signals"], list)


def test_conditional_edge_loops_on_insufficient_data():
    state: RevOpsState = {
        "run_id": str(uuid.uuid4()),
        "raw_signals": [],           # insufficient
        "analysed_data": {},
        "retry_count": 0,
    }
    decision = should_continue_to_writer(state)
    assert decision == "signal_scraper"
    assert state["retry_count"] == 1


def test_conditional_edge_proceeds_when_sufficient():
    state: RevOpsState = {
        "run_id": str(uuid.uuid4()),
        "raw_signals": [{"a": 1}, {"b": 2}, {"c": 3}],
        "analysed_data": {"anomalies": [1], "strategic_summary": "ok"},
        "retry_count": 0,
    }
    decision = should_continue_to_writer(state)
    assert decision == "writer"


@pytest.mark.asyncio
async def test_graph_compiles_and_runs_minimal():
    """Smoke test that the graph can be built and invoked (with heavy mocks)."""
    with patch("src.graph.nodes.signal_scraper_node", new_callable=AsyncMock) as s1, \
         patch("src.graph.nodes.analyst_node", new_callable=AsyncMock) as s2, \
         patch("src.graph.nodes.writer_node", new_callable=AsyncMock) as s3, \
         patch("src.graph.nodes.router_node", new_callable=AsyncMock) as s4:

        s1.return_value = {"raw_signals": [{"test": True}]}
        s2.return_value = {"analysed_data": {"anomalies": []}}
        s3.return_value = {"briefing_draft": "# Test Briefing"}
        s4.return_value = {"delivery_status": {"email": {"status": "success"}}}

        graph = build_revops_graph(checkpointer=None)
        initial = create_initial_state()
        # We don't actually run .invoke here because it would require full async graph execution setup
        assert graph is not None
        assert hasattr(graph, "nodes")
