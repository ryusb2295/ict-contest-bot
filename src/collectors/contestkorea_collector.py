"""Collect open science and IT competitions from Contest Korea."""
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
LIST_URL = "https://www.contestkorea.com/sub/list.php?Txt_bcode=030310001&int_gbn=1&page={}"
CREATIVE_OR_EDUCATION = ("영상", "광고", "포스터", "디자인", "교육생", "교육과정", "양성과정", "아카데미", "캠프", "세미나", "컨설팅", "취업", "강의", "camp")


class ContestKoreaCollector(BaseCollector):
    def __init__(self, pages: int = 4, max_items: int = 50):
        self.pages = pages
        self.max_items = max_items

    def _fetch(self, url: str):
        try:
            response = requests.get(url, headers={"User-Agent": config.user_agent}, timeout=config.request_timeout)
            response.raise_for_status()
            return BeautifulSoup(response.content, "html.parser")
        except requests.RequestException as exc:
            logger.warning("Contest Korea request failed for %s: %s", url, exc)
            return None

    @staticmethod
    def _detail(soup, detail_url: str):
        title_tag = soup.find("h1")
        if not title_tag:
            return None
        title = title_tag.get_text(" ", strip=True)
        if any(word in title.lower() for word in CREATIVE_OR_EDUCATION):
            return None
        fields = {}
        official_url = detail_url
        for tr in soup.find_all("tr"):
            th, td = tr.find("th"), tr.find("td")
            if not th or not td:
                continue
            key = th.get_text(" ", strip=True)
            fields[key] = td.get_text(" ", strip=True)
            if key == "홈페이지":
                link = td.find("a", href=True)
                if link and link["href"].startswith("http"):
                    official_url = link["href"]
        target = fields.get("참가대상", "")
        start, end = parse_date_range(fields.get("접수기간", ""))
        if not is_eligible_student(target) or not end or end < get_current_kst_date().isoformat():
            return None
        if not is_relevant_major(title):
            return None
        return Contest.create(
            title=title, url=official_url,
            organizer=fields.get("주최 . 주관"), category=fields.get("대표분야"),
            target=target, apply_start=start, apply_end=end, source="contestkorea",
        )

    def collect(self):
        links = {}
        for page in range(1, self.pages + 1):
            listing = self._fetch(LIST_URL.format(page))
            if listing is None:
                continue
            for anchor in listing.find_all("a", href=True):
                url = urljoin(LIST_URL.format(page), anchor["href"])
                parsed = urlparse(url)
                if parsed.hostname not in ("contestkorea.com", "www.contestkorea.com"):
                    continue
                if parsed.path != "/sub/view.php" or not parse_qs(parsed.query).get("str_no"):
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
        logger.info("Contest Korea collected %d eligible open contests from %d candidates.", len(contests), len(links))
        return contests
