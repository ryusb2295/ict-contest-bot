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
BACKUP_LIST_URL = "https://deck.dacon.io/"


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
        links = {}
        for page_url, page in ((LIST_URL, listing), (BACKUP_LIST_URL, None)):
            if page is None:
                page = self._fetch(page_url)
            if page is None:
                continue
            for anchor in page.select('a[href*="/hackathons/"]'):
                url = urljoin(page_url, anchor.get("href", ""))
                parsed = urlparse(url)
                if parsed.hostname not in ("daker.ai", "www.daker.ai"):
                    continue
                if not re.fullmatch(r"/(?:public/)?hackathons/[^/]+", parsed.path):
                    continue
                links[url] = anchor.get_text(" ", strip=True)
            if links:
                break
        logger.info("DAKER listing found %d candidate links.", len(links))

        contests: List[Contest] = []
        today = get_current_kst_date()
        missing_deadline = 0
        for url, list_title in list(links.items())[:self.max_items]:
            detail = self._fetch(url)
            if detail is None:
                continue
            title = detail.h1.get_text(" ", strip=True) if detail.h1 else list_title
            title = title.split(" | DAKER")[0].strip()
            text = detail.get_text("\n", strip=True)
            eligible_terms = ("대학생", "대학원생", "대학(원)생", "학부생", "누구나", "제한없음", "제한 없음", "전국민", "전 국민", "대한민국 국민", "청년", "일반인")
            eligibility = next((word for word in eligible_terms if word in text), None)
            if not title or not eligibility:
                continue
            deadline = _submission_deadline(text)
            if not deadline:
                missing_deadline += 1
                continue
            if deadline < today.isoformat():
                continue
            contests.append(Contest.create(
                title=title,
                url=url,
                category="AI / 데이터 / 해커톤",
                target=eligibility,
                apply_end=deadline,
                source="daker",
                discovered_at=get_current_kst_datetime().isoformat(),
            ))

        logger.info("DAKER collected %d open hackathons (%d without a verified deadline).", len(contests), missing_deadline)
        return contests
