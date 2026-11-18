"""Web scraper collector for public domestic contest portal (Wevity IT/SW section)."""
from __future__ import annotations

import html
import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin
import urllib.request
import urllib.error

try:
    import requests
except ImportError:
    requests = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

from src.collectors.base import BaseCollector
from src.config import config
from src.deadline import get_current_kst_date, get_current_kst_datetime, parse_date, parse_date_range
from src.models import Contest

logger = logging.getLogger(__name__)

WEVITY_BASE_URL = "https://www.wevity.com/"
# Category 21: Web/Mobile/IT, Category 20: Science/Engineering/Tech
WEVITY_URLS = [
    "https://www.wevity.com/?c=find&s=1&gub=1&cidx=21",
    "https://www.wevity.com/?c=find&s=1&gub=1&cidx=20",
]


class WevityCollector(BaseCollector):
    """
    Scrapes active domestic competitions from Wevity's Web/Mobile/IT & Tech boards.
    Serves as an automatic zero-cost fallback when Gemini Search Grounding is restricted.
    """

    def __init__(self, max_items_per_category: int = 10):
        self.max_items_per_category = max_items_per_category
        self.headers = {
            "User-Agent": config.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        }

    def _fetch_html_or_soup(self, url: str) -> Optional[Any]:
        """Fetch URL and return BeautifulSoup object or raw HTML string on fallback."""
        try:
            if requests:
                resp = requests.get(
                    url,
                    headers=self.headers,
                    timeout=config.request_timeout,
                )
                if resp.status_code != 200:
                    logger.warning("Wevity request to %s returned HTTP %s", url, resp.status_code)
                    return None
                html_text = resp.content.decode("utf-8", errors="ignore")
            else:
                req = urllib.request.Request(url, headers=self.headers)
                with urllib.request.urlopen(req, timeout=config.request_timeout) as resp:
                    if resp.status != 200:
                        return None
                    html_text = resp.read().decode("utf-8", errors="ignore")

            if BeautifulSoup:
                return BeautifulSoup(html_text, "html.parser")
            return html_text
        except Exception as e:
            logger.warning("Failed to fetch Wevity URL %s: %s", url, e)
            return None

    def _parse_detail_page(self, detail_url: str) -> dict:
        """Parse contest detail page on Wevity to extract accurate fields."""
        data = {
            "category": "웹/모바일/IT",
            "target": "대학생",
            "organizer": "미확인 / 상세 공고 참조",
            "apply_start": None,
            "apply_end": None,
            "event_date": None,
            "homepage_url": detail_url,
            "description": "",
        }

        content = self._fetch_html_or_soup(detail_url)
        if not content:
            return data

        if BeautifulSoup and isinstance(content, BeautifulSoup):
            soup = content
            for li in soup.select(".cd-info-list li"):
                text = li.get_text(" ", strip=True)
                if not text:
                    continue

                if "분야" in text:
                    parts = text.split("분야", 1)
                    if len(parts) > 1:
                        data["category"] = parts[1].strip(" :")

                elif "대상" in text:
                    parts = text.split("대상", 1)
                    if len(parts) > 1:
                        data["target"] = parts[1].strip(" :")

                elif "주최" in text or "주관" in text:
                    parts = re.split(r"주최[/\s]*주관|주최|주관", text)
                    if len(parts) > 1:
                        data["organizer"] = parts[1].strip(" :")

                elif "접수기간" in text or "기간" in text:
                    period_clean = re.sub(r"D[+\-]\d+", "", text)
                    period_clean = period_clean.replace("접수기간", "").replace("기간", "").strip(" :")
                    start, end = parse_date_range(period_clean)
                    data["apply_start"] = start
                    data["apply_end"] = end

                elif "홈페이지" in text or "관련링크" in text:
                    for a in li.find_all("a", href=True):
                        href = a["href"].strip()
                        if href.startswith("http") and "wevity.com" not in href:
                            data["homepage_url"] = href
                            break

                elif any(k in text for k in ("행사일", "대회일", "시상일", "본선")):
                    data["event_date"] = text.strip(" :")

            desc_el = soup.select_one(".view-cont, .article-copy, #viewCont")
            if desc_el:
                desc_text = desc_el.get_text(" ", strip=True)
                data["description"] = desc_text[:400]

        elif isinstance(content, str):
            # Standard library regex parser fallback
            raw_html = content
            for match in re.finditer(r"<li[^>]*>(.*?)</li>", raw_html, re.DOTALL):
                li_inner = match.group(1)
                text = re.sub(r"<[^>]+>", " ", li_inner).strip()
                if "분야" in text:
                    parts = text.split("분야", 1)
                    if len(parts) > 1:
                        data["category"] = parts[1].strip(" :")
                elif "대상" in text:
                    parts = text.split("대상", 1)
                    if len(parts) > 1:
                        data["target"] = parts[1].strip(" :")
                elif "주최" in text or "주관" in text:
                    parts = re.split(r"주최[/\s]*주관|주최|주관", text)
                    if len(parts) > 1:
                        data["organizer"] = parts[1].strip(" :")
                elif "접수기간" in text or "기간" in text:
                    period_clean = re.sub(r"D[+\-]\d+", "", text)
                    period_clean = period_clean.replace("접수기간", "").replace("기간", "").strip(" :")
                    start, end = parse_date_range(period_clean)
                    data["apply_start"] = start
                    data["apply_end"] = end
                elif "홈페이지" in text or "관련링크" in text:
                    link_match = re.search(r'href=["\'](https?://(?!www\.wevity\.com)[^"\']+)["\']', li_inner)
                    if link_match:
                        data["homepage_url"] = link_match.group(1)
                elif any(k in text for k in ("행사일", "대회일", "시상일", "본선")):
                    data["event_date"] = text.strip(" :")

            desc_match = re.search(r'class=["\'](?:view-cont|article-copy)["\'][^>]*>(.*?)</div>', raw_html, re.DOTALL)
            if desc_match:
                clean_desc = re.sub(r"<[^>]+>", " ", desc_match.group(1)).strip()
                data["description"] = clean_desc[:400]

        return data

    def collect(self) -> List[Contest]:
        """Scrape active IT/SW contests from Wevity."""
        logger.info("Collecting contests from Wevity public portal...")
        contests: List[Contest] = []
        seen_urls = set()
        now_iso = get_current_kst_datetime().isoformat()

        for category_url in WEVITY_URLS:
            content = self._fetch_html_or_soup(category_url)
            if not content:
                continue

            entries = []
            if BeautifulSoup and isinstance(content, BeautifulSoup):
                for item in content.select("ul.list > li"):
                    tit_el = item.select_one(".tit a")
                    if not tit_el:
                        continue
                    raw_title = tit_el.get_text(strip=True)
                    href = tit_el.get("href", "")
                    day_el = item.select_one(".day")
                    day_text = day_el.get_text(strip=True) if day_el else ""
                    entries.append((raw_title, href, day_text))
            elif isinstance(content, str):
                # Regex list parsing fallback
                for match in re.finditer(r'<li[^>]*>(.*?)</li>', content, re.DOTALL):
                    li_str = match.group(1)
                    tit_match = re.search(r'<div class=["\']tit["\'][^>]*>\s*<a href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', li_str, re.DOTALL)
                    if tit_match:
                        href = tit_match.group(1)
                        raw_title = re.sub(r'<[^>]+>', '', tit_match.group(2)).strip()
                        day_match = re.search(r'<div class=["\']day["\'][^>]*>(.*?)</div>', li_str, re.DOTALL)
                        day_text = re.sub(r'<[^>]+>', '', day_match.group(1)).strip() if day_match else ""
                        entries.append((raw_title, href, day_text))

            collected_in_category = 0
            for raw_title, href, day_text in entries:
                if not raw_title or not href or "ix=" not in href:
                    continue

                detail_url = urljoin(WEVITY_BASE_URL, href)
                if detail_url in seen_urls:
                    continue
                seen_urls.add(detail_url)

                if "마감" in day_text and "D-" not in day_text:
                    continue

                detail = self._parse_detail_page(detail_url)
                official_url = detail.get("homepage_url") or detail_url

                contest = Contest.create(
                    title=raw_title,
                    url=official_url,
                    organizer=detail.get("organizer"),
                    category=detail.get("category"),
                    target=detail.get("target"),
                    apply_start=detail.get("apply_start"),
                    apply_end=detail.get("apply_end"),
                    event_date=detail.get("event_date"),
                    description=detail.get("description"),
                    source="wevity",
                    discovered_at=now_iso,
                )
                contests.append(contest)
                collected_in_category += 1

                if collected_in_category >= self.max_items_per_category:
                    break

        logger.info("WevityCollector successfully gathered %d contests.", len(contests))
        return contests
