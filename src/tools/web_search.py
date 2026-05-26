"""
Web Search Tool (DuckDuckGo) for Signal Scraper Agent.

Provides fresh market signals when Playwright scraping needs supplementation.
Returns structured results suitable for Claude extraction.
"""

from __future__ import annotations

import logging
from typing import Any

from duckduckgo_search import DDGS
from langchain_core.tools import tool
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


@tool("web_search")
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)
def web_search_tool(query: str, max_results: int = 8) -> list[dict[str, Any]]:
    """
    Search the web using DuckDuckGo.

    Args:
        query: Natural language search query (e.g. "Tata Hitachi excavator price hike 2025")
        max_results: Number of results to return (default 8)

    Returns:
        List of dicts with keys: title, href, body
    """
    logger.info(f"Web search initiated: query='{query}' max_results={max_results}")

    results: list[dict[str, Any]] = []

    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            results.append(
                {
                    "title": r.get("title", ""),
                    "href": r.get("href", ""),
                    "body": r.get("body", ""),
                }
            )

    logger.info(f"Web search returned {len(results)} results")
    return results


def search_competitor_signals(competitor: str, days_back: int = 14) -> list[dict[str, Any]]:
    """
    Convenience wrapper used by Signal Scraper Agent.
    Builds a targeted query for recent pricing / dealer news.
    """
    query = f"{competitor} price OR dealer OR expansion OR news after:{days_back} days"
    return web_search_tool.invoke({"query": query, "max_results": 6})
