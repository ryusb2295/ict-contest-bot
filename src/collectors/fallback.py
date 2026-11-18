"""Merge results from Gemini search, Wevity, and DAKER."""
from __future__ import annotations

import logging
from typing import List

from src.collectors.base import BaseCollector
from src.collectors.daker_collector import DakerCollector
from src.collectors.gemini_search import GeminiSearchCollector
from src.collectors.wevity_collector import WevityCollector
from src.config import config
from src.models import Contest

logger = logging.getLogger(__name__)


class FallbackCollectorManager(BaseCollector):
    """
    Run optional Gemini search and both public site collectors on every run.
    """

    def __init__(self):
        self.gemini_collector = GeminiSearchCollector()
        self.wevity_collector = WevityCollector()
        self.daker_collector = DakerCollector()

    def collect(self) -> List[Contest]:
        """Collect from available sources while isolating individual failures."""
        candidates: List[Contest] = []

        # Attempt 1: Gemini with Google Search Grounding
        if config.has_gemini:
            logger.info("Attempting primary collection via Gemini Google Search Grounding...")
            try:
                gemini_items = self.gemini_collector.collect()
                if gemini_items:
                    logger.info("Gemini Search Grounding returned %d contests.", len(gemini_items))
                    candidates.extend(gemini_items)
                else:
                    logger.info("Gemini Search Grounding returned 0 items.")
            except Exception as e:
                logger.warning("Gemini collection encountered error: %s", e)
        else:
            logger.info("No GEMINI_API_KEY detected. Collecting from public sites only.")

        # Wevity runs even when Gemini succeeds.
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

        # DAKER is an independent source for AI and data hackathons.
        try:
            daker_items = self.daker_collector.collect()
            existing_urls = {c.url for c in candidates}
            for item in daker_items:
                if item.url not in existing_urls:
                    candidates.append(item)
                    existing_urls.add(item.url)
        except Exception as e:
            logger.error("DakerCollector encountered error: %s", e)

        logger.info("Total raw candidates gathered across collectors: %d", len(candidates))
        return candidates
