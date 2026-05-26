"""
Unit tests for the four LangChain tools.
All external calls are heavily mocked.
"""

import pytest
from unittest.mock import patch, MagicMock

from src.tools.web_search import web_search_tool
from src.tools.database_query import database_query_tool
from src.tools.whatsapp_sender import whatsapp_send_tool
from src.tools.email_sender import email_send_tool


def test_web_search_tool_basic():
    with patch("src.tools.web_search.DDGS") as mock_ddgs:
        mock_ddgs.return_value.__enter__.return_value.text.return_value = [
            {"title": "Tata Hitachi raises prices", "href": "https://example.com", "body": "4.5% hike"}
        ]
        result = web_search_tool.invoke({"query": "Tata Hitachi price", "max_results": 3})
        assert len(result) == 1
        assert "Tata Hitachi" in result[0]["title"]


def test_database_query_tool_returns_structure():
    with patch("src.tools.database_query._db_tool_instance.analyze") as mock_analyze:
        mock_analyze.return_value = {
            "question": "test?",
            "sql": "SELECT 1",
            "results": [{"a": 1}],
            "interpretation": "All good",
            "success": True,
        }
        res = database_query_tool.invoke({"question": "What is total revenue?"})
        assert res["success"] is True
        assert "interpretation" in res


def test_whatsapp_send_tool_skips_when_unconfigured(monkeypatch):
    monkeypatch.setenv("WHATSAPP_ENABLED", "false")
    result = whatsapp_send_tool.invoke({"message": "hello", "run_id": "123"})
    assert result["status"] == "skipped"


def test_email_send_tool_skips_when_unconfigured(monkeypatch):
    monkeypatch.setenv("SMTP_PASSWORD", "")
    result = email_send_tool.invoke({"subject": "test", "markdown_body": "# hi", "run_id": "123"})
    assert result["status"] == "skipped"
