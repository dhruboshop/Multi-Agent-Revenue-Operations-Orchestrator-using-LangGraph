"""
Tests for the four specialized agents.
Heavy mocking of Claude + external services.
"""

import pytest
import uuid
from unittest.mock import AsyncMock, patch

from src.agents.signal_scraper import SignalScraperAgent
from src.agents.analyst import AnalystAgent
from src.agents.writer import WriterAgent
from src.agents.router import RouterAgent


@pytest.mark.asyncio
async def test_signal_scraper_demo_mode():
    with patch("src.agents.signal_scraper.settings") as mock_settings:
        mock_settings.demo_mode = True
        agent = SignalScraperAgent()
        result = await agent.scrape(run_id=uuid.uuid4())
        assert isinstance(result, list)


@pytest.mark.asyncio
async def test_analyst_produces_anomalies():
    agent = AnalystAgent()
    with patch.object(agent, "_run_three_queries") as mock_queries:
        mock_queries.return_value = [
            {"question": "q1", "success": True, "interpretation": "South region underperformed"}
        ]
        with patch("src.agents.analyst.anthropic.Anthropic") as mock_claude:
            mock_resp = MagicMock()
            mock_resp.content = [MagicMock(text='{"anomalies": [{"type": "variance", "severity": "high"}]}')]
            mock_claude.return_value.messages.create.return_value = mock_resp

            result = agent.analyze(raw_signals=[{"title": "test"}], run_id=uuid.uuid4())
            assert "analysed_data" in result


def test_writer_generates_markdown():
    agent = WriterAgent()
    with patch("src.agents.writer.anthropic.Anthropic") as mock_claude:
        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text="# Weekly Revenue Intelligence Briefing\n\n## 1. Executive Summary\nTest")]
        mock_claude.return_value.messages.create.return_value = mock_resp

        result = agent.write_briefing(
            analysed_data={"anomalies": [], "strategic_summary": "ok"},
            raw_signals=[],
            run_id=uuid.uuid4()
        )
        assert "briefing_draft" in result
        assert "Executive Summary" in result["briefing_draft"]


def test_router_returns_delivery_status():
    agent = RouterAgent()
    with patch("src.agents.router.whatsapp_send_tool") as wa, patch("src.agents.router.email_send_tool") as em:
        wa.invoke.return_value = {"status": "success"}
        em.invoke.return_value = {"status": "success"}
        result = agent.deliver(briefing_draft="# Test", run_id=uuid.uuid4())
        assert "delivery_status" in result
        assert result["delivery_status"]["whatsapp"]["status"] == "success"
