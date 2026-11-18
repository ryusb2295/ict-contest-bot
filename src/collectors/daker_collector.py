"""Collect open AI hackathons from DAKER's public listing."""
from __future__ import annotations

import logging
import re
from datetime import date
from typing import List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from src.collectors.base import BaseCollector
from src.config import config
from src.deadline import get_current_kst_datetime, get_current_kst_date, parse_date
from src.models import Contest

logger = logging.getLogger(__name__)
LIST_URL = "https://daker.ai/public/hackathons"


def _submission_deadline(text: str) -> Optional[str]:
    """Use an explicit year in the submission period; never infer one from today."""
    for line in text.splitlines():
        if not any(word in line for word in ("제출", "접수", "마감")):
            continue
        dates = re.findall(r"\d{4}[./-]\d{1,2}[./-]\d{1,2}", line)
        if dates:
            parsed = parse_date(dates[-1])
            if parsed:
                return parsed
        korean = re.search(
            r"(\d{4})년\s*\d{1,2}월\s*\d{1,2}일[^\n]*?~\s*(\d{1,2})월\s*(\d{1,2})일",
            line,
        )
        if korean:
            year, month, day = map(int, korean.groups())
            try:
                return date(year, month, day).isoformat()
            except ValueError:
                continue
    return None


class DakerCollector(BaseCollector):
    def __init__(self, max_items: int = 30):
        self.max_items = max_items

    def _fetch(self, url: str) -> Optional[BeautifulSoup]:
        try:
            response = requests.get(
                url, headers={"User-Agent": config.user_agent}, timeout=config.request_timeout
            )
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except requests.RequestException as exc:
            logger.warning("DAKER request failed for %s: %s", url, exc)
            return None

    def collect(self) -> List[Contest]:
        listing = self._fetch(LIST_URL)
        if listing is None:
            return []

        links = {}
        for anchor in listing.select('a[href*="/hackathons/"]'):
            url = urljoin(LIST_URL, anchor.get("href", ""))
            parsed = urlparse(url)
            if parsed.hostname not in ("daker.ai", "www.daker.ai"):
                continue
            if not re.fullmatch(r"/(?:public/)?hackathons/[^/]+", parsed.path):
                continue
            links[url] = anchor.get_text(" ", strip=True)

        contests: List[Contest] = []
        today = get_current_kst_date()
        for url, list_title in list(links.items())[:self.max_items]:
            detail = self._fetch(url)
            if detail is None:
                continue
            title = detail.h1.get_text(" ", strip=True) if detail.h1 else list_title
            title = title.split(" | DAKER")[0].strip()
            text = detail.get_text("\n", strip=True)
            if not title or not any(word in text for word in ("누구나", "대학생", "학생", "일반인")):
                continue
            deadline = _submission_deadline(text)
            if not deadline or deadline < today.isoformat():
                continue
            contests.append(Contest.create(
                title=title,
                url=url,
                category="AI / 데이터 / 해커톤",
                target="학생 및 일반인",
                apply_end=deadline,
                source="daker",
                discovered_at=get_current_kst_datetime().isoformat(),
            ))

        logger.info("DAKER collected %d open hackathons.", len(contests))
        return contests
