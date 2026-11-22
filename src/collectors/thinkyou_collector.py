"""Collect open IT/SW competitions from Thinkyou's public listings."""
from __future__ import annotations

import logging
import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from src.collectors.base import BaseCollector
from src.config import config
from src.deadline import get_current_kst_date, parse_date, parse_date_range
from src.filter import is_eligible_student, is_relevant_major
from src.models import Contest

logger = logging.getLogger(__name__)
LIST_URL = "https://thinkyou.co.kr/contest/sector.asp?serfield=5&serstatus=1&page={}"
DETAIL_PATH = re.compile(r"^/contest/\d+/?$")
NON_CONTEST = ("교육생 모집", "교육과정", "무료교육", "국비지원", "아카데미", "양성과정", "세미나", "컨설팅", "취업", "강의")
CREATIVE_TITLE = ("music video", "ai video", "ai film", "광고", "포스터", "영상", "뮤직비디오")


class ThinkyouCollector(BaseCollector):
    def __init__(self, pages: int = 2, max_items: int = 45):
        self.pages = pages
        self.max_items = max_items

    def _fetch(self, url: str):
        try:
            response = requests.get(url, headers={"User-Agent": config.user_agent}, timeout=config.request_timeout)
            response.raise_for_status()
            return BeautifulSoup(response.content, "html.parser")
        except requests.RequestException as exc:
            logger.warning("Thinkyou request failed for %s: %s", url, exc)
            return None

    @staticmethod
    def _detail(soup, detail_url: str):
        title_tag = soup.select_one("h1")
        if not title_tag:
            return None
        title = title_tag.get_text(" ", strip=True)
        if any(word in title for word in NON_CONTEST) or any(word in title.lower() for word in CREATIVE_TITLE):
            return None

        rows = {}
        official_url = detail_url
        for tr in soup.select("tr"):
            th, td = tr.find("th"), tr.find("td")
            if not th or not td:
                continue
            key = th.get_text(" ", strip=True)
            rows[key] = td.get_text(" ", strip=True)
            if "홈페이지" in key:
                link = td.find("a", href=True)
                if link and link["href"].startswith("http"):
                    official_url = link["href"]

        eligibility = ""
        description = ""
        for dl in soup.select("dl"):
            dt, dd = dl.find("dt"), dl.find("dd")
            if not dt or not dd:
                continue
            key = dt.get_text(" ", strip=True)
            value = dd.get_text(" ", strip=True)
            if "참여자격" in key or "응모자격" in key:
                eligibility = value[:250]
            elif "공모주제" in key:
                description = value[:400]

        if not is_eligible_student(eligibility):
            return None
        if not is_relevant_major(title, description=description):
            return None
        period = next((v for k, v in rows.items() if "접수기간" in k), "")
        start, end = parse_date_range(period)
        if not end or parse_date(end) < get_current_kst_date().isoformat():
            return None
        organizer = next((v for k, v in rows.items() if "주최" in k), "")
        category = next((v for k, v in rows.items() if "응모분야" in k), "")
        return Contest.create(
            title=title, url=official_url, organizer=organizer, category=category,
            target=eligibility, apply_start=start, apply_end=end,
            description=description, source="thinkyou",
        )

    def collect(self):
        links = {}
        for page in range(1, self.pages + 1):
            url = LIST_URL.format(page)
            soup = self._fetch(url)
            if soup is None:
                continue
            for anchor in soup.find_all("a", href=True):
                detail_url = urljoin(url, anchor["href"])
                if urlparse(detail_url).hostname not in ("thinkyou.co.kr", "www.thinkyou.co.kr"):
                    continue
                if DETAIL_PATH.fullmatch(urlparse(detail_url).path):
                    links[detail_url] = None
        contests = []
        for url in list(links)[:self.max_items]:
            soup = self._fetch(url)
            if soup is None:
                continue
            contest = self._detail(soup, url)
            if contest:
                contests.append(contest)
        logger.info("Thinkyou collected %d eligible open contests from %d listings.", len(contests), len(links))
        return contests
