"""
AGENT 1 — Signal Scraper Agent

Role:
Scrape public web sources (competitor pricing pages, news, dealer announcements)
using Playwright + fallback to DuckDuckGo search. Uses Claude to extract
structured JSON signals from raw HTML.

Key behaviors:
- Scrapes 3 configured demo URLs (stable public pages)
- Falls back gracefully to web_search_tool when Playwright fails or in DEMO_MODE
- Always returns list[dict] with keys: source, competitor, signal_type, title, summary, relevance
- Logs every scrape to run_logs
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from datetime import datetime
from typing import Any

import anthropic
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

from src.config.settings import get_settings
from src.database.connection import db_session
from src.database.models import RunLog
from src.tools.web_search import web_search_tool

logger = logging.getLogger(__name__)
settings = get_settings()


class SignalScraperAgent:
    """
    Production-grade web signal collector.
    Designed to be called as a LangGraph node.
    """

    DEMO_URLS = [
        "https://news.google.com/rss/search?q=Tata+Hitachi+excavator+price&hl=en-IN&gl=IN&ceid=IN:en",
        "https://economictimes.indiatimes.com/topic/construction-equipment",
        "https://www.livemint.com/search?q=JCB+India+dealer+expansion",
    ]

    def __init__(self, anthropic_client: anthropic.Anthropic | None = None):
        self.client = anthropic_client or anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = settings.claude_model
        self.max_retries = settings.max_scraper_retries

    def _log(self, run_id: uuid.UUID, status: str, details: str, duration_ms: int | None = None) -> None:
        if not settings.enable_state_logging:
            return
        try:
            with db_session() as db:
                db.add(
                    RunLog(
                        run_id=run_id,
                        node_name="signal_scraper",
                        status=status,
                        input_summary=f"urls={len(self.DEMO_URLS)}",
                        output_summary=details[:3000],
                        execution_time_ms=duration_ms,
                    )
                )
        except Exception as e:
            logger.error(f"RunLog write failed: {e}")

    async def _scrape_one(self, url: str) -> str:
        """Fetch raw text content from a single URL using Playwright."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=25000)
                # Give RSS/news pages a moment
                await asyncio.sleep(1.2)
                content = await page.content()
                # Strip scripts/styles
                content = re.sub(r"<script[^>]*>.*?</script>", "", content, flags=re.DOTALL | re.I)
                content = re.sub(r"<style[^>]*>.*?</style>", "", content, flags=re.DOTALL | re.I)
                text = re.sub(r"<[^>]+>", " ", content)
                text = re.sub(r"\s+", " ", text).strip()
                return text[:12000]  # safety cap
            except PlaywrightTimeout:
                logger.warning(f"Playwright timeout on {url}")
                return ""
            finally:
                await browser.close()

    def _extract_structured_signals(self, raw_text: str, source_url: str) -> list[dict[str, Any]]:
        """Use Claude to turn raw scraped text into structured signals."""
        if not raw_text or len(raw_text) < 200:
            return []

        prompt = f"""You are an expert market intelligence analyst for construction equipment in India.

SOURCE URL: {source_url}

RAW CONTENT (truncated):
{raw_text[:8000]}

TASK:
Extract 1-4 high-signal items about competitor pricing, new dealer appointments, major orders, or strategic moves.
Return ONLY a JSON array. Each object must have exactly these keys:
- competitor (string)
- signal_type (one of: "pricing", "news", "dealer_activity", "hiring", "contract")
- title (string, <120 chars)
- summary (string, 1-2 sentences, business-relevant)
- relevance_score (float 0.0-1.0)

If nothing relevant is found, return exactly: []

JSON:"""

        try:
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=1200,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text.strip() if resp.content else "[]"
            # Very light cleanup in case Claude adds markdown
            text = re.sub(r"^```json\s*", "", text)
            text = re.sub(r"```$", "", text).strip()
            import json

            signals = json.loads(text)
            for s in signals:
                s["source"] = source_url
            return signals
        except Exception as e:
            logger.warning(f"Claude extraction failed on {source_url}: {e}")
            return []

    async def scrape(self, run_id: uuid.UUID | None = None) -> list[dict[str, Any]]:
        """
        Main entry point. Returns list of structured signals.
        """
        run_id = run_id or uuid.uuid4()
        start = time.time()
        self._log(run_id, "started", "Beginning scrape cycle")

        all_signals: list[dict[str, Any]] = []

        if settings.demo_mode:
            logger.info("DEMO_MODE active — using web_search fallback only")
            search_results = web_search_tool.invoke(
                {"query": "Tata Hitachi OR BEML OR JCB India excavator dealer price OR expansion India 2025", "max_results": 10}
            )
            for r in search_results[:6]:
                all_signals.append(
                    {
                        "source": r.get("href", "web_search"),
                        "competitor": "Market Signal",
                        "signal_type": "news",
                        "title": r.get("title", "")[:140],
                        "summary": r.get("body", "")[:280],
                        "relevance_score": 0.65,
                    }
                )
            duration = int((time.time() - start) * 1000)
            self._log(run_id, "success", f"DEMO_MODE: {len(all_signals)} signals via search", duration)
            return all_signals

        # Real Playwright scraping
        for url in self.DEMO_URLS:
            try:
                raw = await self._scrape_one(url)
                if raw:
                    extracted = self._extract_structured_signals(raw, url)
                    all_signals.extend(extracted)
                    logger.info(f"Scraped {len(extracted)} signals from {url}")
            except Exception as e:
                logger.warning(f"Scrape failed for {url}: {e}")
                # Fallback to search for this source
                try:
                    fallback = web_search_tool.invoke({"query": "construction equipment India dealer news pricing", "max_results": 4})
                    for f in fallback:
                        all_signals.append(
                            {
                                "source": f.get("href", url),
                                "competitor": "Unknown Competitor",
                                "signal_type": "news",
                                "title": f.get("title", "")[:120],
                                "summary": f.get("body", "")[:260],
                                "relevance_score": 0.5,
                            }
                        )
                except Exception:
                    pass

        # Always enrich with targeted web search
        try:
            extra = web_search_tool.invoke(
                {"query": "Tata Hitachi price hike OR JCB new dealer appointment OR BEML order India", "max_results": 6}
            )
            for e in extra:
                all_signals.append(
                    {
                        "source": e.get("href", "search"),
                        "competitor": "Market",
                        "signal_type": "news",
                        "title": e.get("title", "")[:120],
                        "summary": e.get("body", "")[:260],
                        "relevance_score": 0.6,
                    }
                )
        except Exception:
            pass

        duration = int((time.time() - start) * 1000)
        status = "success" if all_signals else "partial"
        self._log(run_id, status, f"Collected {len(all_signals)} raw signals", duration)

        # Deduplicate by title
        seen = set()
        unique = []
        for s in all_signals:
            key = s.get("title", "")[:60]
            if key and key not in seen:
                seen.add(key)
                unique.append(s)

        return unique[:15]  # reasonable cap for downstream agents


# Convenience function for graph nodes
async def run_signal_scraper(run_id: uuid.UUID | None = None) -> dict[str, Any]:
    agent = SignalScraperAgent()
    signals = await agent.scrape(run_id)
    return {
        "raw_signals": signals,
        "scraper_completed_at": datetime.utcnow().isoformat(),
        "signal_count": len(signals),
    }
