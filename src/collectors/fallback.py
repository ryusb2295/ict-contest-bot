"""Fallback coordinator managing primary Gemini Search Grounding and public portal scrapers."""
from __future__ import annotations

import logging
from typing import List

from src.collectors.base import BaseCollector
from src.collectors.gemini_search import GeminiSearchCollector
from src.collectors.wevity_collector import WevityCollector
from src.config import config
from src.models import Contest

logger = logging.getLogger(__name__)


class FallbackCollectorManager(BaseCollector):
    """
    Coordinates multi-tier contest collection:
    1. Primary: Gemini API with Google Search Grounding (if API key available).
    2. Fallback: Wevity IT/SW public portal scraper (zero-cost, always accessible).
    """

    def __init__(self):
        self.gemini_collector = GeminiSearchCollector()
        self.wevity_collector = WevityCollector()

    def collect(self) -> List[Contest]:
        """Collect contests with automatic graceful fallback."""
        candidates: List[Contest] = []
        gemini_success = False

        # Attempt 1: Gemini with Google Search Grounding
        if config.has_gemini:
            logger.info("Attempting primary collection via Gemini Google Search Grounding...")
            try:
                gemini_items = self.gemini_collector.collect()
                if gemini_items:
                    logger.info("Gemini Search Grounding returned %d contests.", len(gemini_items))
                    candidates.extend(gemini_items)
                    gemini_success = True
                else:
                    logger.info("Gemini Search Grounding returned 0 items. Triggering Wevity fallback.")
            except Exception as e:
                logger.warning("Gemini collection encountered error: %s. Triggering fallback.", e)
        else:
            logger.info("No GEMINI_API_KEY detected. Using Wevity public collector directly.")

        # Attempt 2: Fallback / Secondary Web Scraper
        # Always run or fallback if Gemini didn't find enough items
        try:
            wevity_items = self.wevity_collector.collect()
            if wevity_items:
                logger.info("WevityCollector gathered %d contests.", len(wevity_items))
                # Merge without URL collisions
                existing_urls = {c.url for c in candidates}
                for item in wevity_items:
                    if item.url not in existing_urls:
                        candidates.append(item)
                        existing_urls.add(item.url)
        except Exception as e:
            logger.error("WevityCollector encountered error: %s", e)

        logger.info("Total raw candidates gathered across collectors: %d", len(candidates))
        return candidates
