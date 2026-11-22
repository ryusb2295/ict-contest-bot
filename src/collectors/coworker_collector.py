"""Collect active ICT contests from Co-worker's public contest listings."""
from __future__ import annotations

import logging
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from src.collectors.base import BaseCollector
from src.config import config
from src.deadline import get_current_kst_date, parse_date_range
from src.filter import is_eligible_student, is_relevant_major
from src.models import Contest

logger = logging.getLogger(__name__)
LIST_URL = "https://co-worker.co.kr/Contest/state_contest_list?contest_state=3"
CREATIVE_OR_EDUCATION = ("영상", "광고", "포스터", "디자인", "교육생", "교육과정", "양성과정", "아카데미", "캠프", "세미나", "컨설팅", "취업", "강의", "camp")


class CoworkerCollector(BaseCollector):
    def __init__(self, max_items: int = 30):
        self.max_items = max_items

    def _fetch(self, url: str):
        try:
            response = requests.get(url, headers={"User-Agent": config.user_agent}, timeout=config.request_timeout)
            response.raise_for_status()
            return BeautifulSoup(response.content, "html.parser")
        except requests.RequestException as exc:
            logger.warning("Co-worker request failed for %s: %s", url, exc)
            return None

    @staticmethod
    def _detail(soup, detail_url: str):
        title_tag = soup.select_one("p.bigtxt")
        if not title_tag:
            return None
        title = title_tag.get_text(" ", strip=True)
        if any(word in title.lower() for word in CREATIVE_OR_EDUCATION):
            return None

        fields = {}
        official_url = detail_url
        for label in soup.select("strong.tit"):
            key = label.get_text(" ", strip=True)
            parent = label.parent
            if not parent:
                continue
            value = parent.get_text(" ", strip=True).removeprefix(key).strip()
            fields[key] = value
            if key == "홈페이지":
                link = parent.find("a", href=True)
                if link and link["href"].startswith("http"):
                    official_url = link["href"]

        target = fields.get("응모대상", "")
        start, end = parse_date_range(fields.get("접수기간", ""))
        if not is_eligible_student(target) or not end or end < get_current_kst_date().isoformat():
            return None
        description = ""
        for label in soup.select("span.listtit"):
            if "응모주제" in label.get_text(" ", strip=True):
                description = label.parent.get_text(" ", strip=True)[:400]
                break
        if not is_relevant_major(title, description=description):
            return None
        return Contest.create(
            title=title, url=official_url, organizer=fields.get("주최사"),
            category=fields.get("분야"), target=target,
            apply_start=start, apply_end=end, description=description,
            source="coworker",
        )

    def collect(self):
        listing = self._fetch(LIST_URL)
        if listing is None:
            return []
        links = {}
        for anchor in listing.find_all("a", href=True):
            url = urljoin(LIST_URL, anchor["href"])
            parsed = urlparse(url)
            if parsed.hostname not in ("co-worker.co.kr", "www.co-worker.co.kr"):
                continue
            if parsed.path.lower() != "/contest/contest_view" or not parse_qs(parsed.query).get("idx"):
                continue
            title = anchor.get_text(" ", strip=True)
            if title and is_relevant_major(title) and not any(word in title.lower() for word in CREATIVE_OR_EDUCATION):
                links[url] = None
        contests = []
        for url in list(links)[:self.max_items]:
            soup = self._fetch(url)
            if soup is None:
                continue
            contest = self._detail(soup, url)
            if contest:
                contests.append(contest)
        logger.info("Co-worker collected %d eligible open contests from %d candidates.", len(contests), len(links))
        return contests
