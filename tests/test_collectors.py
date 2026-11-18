"""Unit tests for collector JSON extraction and Wevity HTML parsing."""
import unittest
from datetime import date
from unittest.mock import patch

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

from src.collectors.gemini_search import extract_json_array
from src.collectors.daker_collector import DakerCollector
from src.collectors.fallback import FallbackCollectorManager
from src.collectors.wevity_collector import WevityCollector
from src.models import Contest


class TestCollectors(unittest.TestCase):
    def test_manager_merges_independent_sites(self):
        manager = FallbackCollectorManager()
        wevity = Contest.create(title="사회보장 데이터 AI 경진대회", url="https://example.com/social")
        daker = Contest.create(title="제주 AI Agent 챌린지", url="https://example.com/jeju")
        with patch.object(manager.gemini_collector, "collect", return_value=[]):
            with patch.object(manager.wevity_collector, "collect", return_value=[wevity]):
                with patch.object(manager.daker_collector, "collect", return_value=[daker]):
                    contests = manager.collect()
        self.assertEqual({item.title for item in contests}, {wevity.title, daker.title})

    def test_daker_collects_jeju_from_listing(self):
        listing = BeautifulSoup(
            '<a href="/hackathons/jeju-ai-agent">제주 AI·빅데이터 활용 AI Agent 개발 챌린지</a>',
            "html.parser",
        )
        detail = BeautifulSoup(
            '<h1>제주 AI·빅데이터 활용 AI Agent 개발 챌린지</h1>'
            '<p>일반인, 학생 등 누구나 참가 가능</p>'
            '<p>기획안 및 최종 산출물 제출: 2026년 10월 26일 10:00 ~ 11월 20일 10:00</p>',
            "html.parser",
        )
        collector = DakerCollector()
        with patch("src.collectors.daker_collector.get_current_kst_date", return_value=date(2026, 11, 19)):
            with patch.object(collector, "_fetch", side_effect=[listing, detail]):
                contests = collector.collect()
        self.assertEqual(len(contests), 1)
        self.assertEqual(contests[0].apply_end, "2026-11-20")
        self.assertEqual(contests[0].source, "daker")

    def test_wevity_scans_idea_and_later_pages(self):
        def listing(title, ix):
            return BeautifulSoup(
                f'<ul class="list"><li><div class="tit"><a href="/?c=find&ix={ix}">{title}</a></div>'
                '<div class="day">D-1</div></li></ul>', "html.parser"
            )

        detail = BeautifulSoup(
            '<ul class="cd-info-list"><li>대상 : 누구나</li>'
            '<li>접수기간 : 2026-10-21 ~ 2026-11-20</li></ul>', "html.parser"
        )
        urls = ["https://www.wevity.com/?c=find&cidx=1&gp=1", "https://www.wevity.com/?c=find&cidx=1&gp=2"]
        responses = [listing("대구 기후 공공데이터 AI 활용대회", 1), detail,
                     listing("사회보장 데이터 AI 혁신 아이디어 경진대회", 2), detail]
        collector = WevityCollector()
        with patch("src.collectors.wevity_collector.WEVITY_URLS", urls):
            with patch.object(collector, "_fetch_html_or_soup", side_effect=responses):
                contests = collector.collect()
        self.assertEqual(len(contests), 2)
        self.assertTrue(all(c.apply_end == "2026-11-20" for c in contests))

    def test_extract_json_array_plain(self):
        text = '[{"title": "2026 AI 해커톤", "url": "https://example.com"}]'
        items = extract_json_array(text)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "2026 AI 해커톤")

    def test_extract_json_array_markdown_fence(self):
        text = """
        다음은 최신 공모전 목록입니다:
        ```json
        [
          {
            "title": "SW 개발 경진대회",
            "url": "https://sw-contest.org",
            "organizer": "정보통신산업진흥원",
            "apply_end": "2026-12-15"
          }
        ]
        ```
        """
        items = extract_json_array(text)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "SW 개발 경진대회")
        self.assertEqual(items[0]["apply_end"], "2026-12-15")

    def test_extract_json_array_dict_envelope(self):
        text = '{"contests": [{"title": "데이터 분석 챌린지", "url": "https://data.kr"}]}'
        items = extract_json_array(text)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "데이터 분석 챌린지")

    def test_extract_json_array_invalid(self):
        self.assertEqual(extract_json_array("검색 결과가 존재하지 않습니다."), [])
        self.assertEqual(extract_json_array(""), [])

    def test_wevity_detail_parser_mock(self):
        mock_detail_html = """
        <div class="tit-area">
          <h6 class="tit">2026 대학생 생성형 AI SW 공모전</h6>
        </div>
        <ul class="cd-info-list">
          <li><span class="tit">분야</span> : 웹/모바일/IT</li>
          <li><span class="tit">대상</span> : 일반인, 대학생, 청소년</li>
          <li><span class="tit">주최/주관</span> : 과학기술정보통신부 / NIPA</li>
          <li><span class="tit">접수기간</span> : 2026-11-01 ~ 2026-12-20 D-32</li>
          <li><span class="tit">홈페이지</span> : <a href="https://official-contest-site.kr/register">바로가기</a></li>
        </ul>
        <div class="view-cont">
          <p>본 공모전은 전국 대학생을 대상으로 생성형 AI 및 SW 역량을 겨루는 대회입니다.</p>
        </div>
        """

        collector = WevityCollector()
        mock_content = BeautifulSoup(mock_detail_html, "html.parser") if BeautifulSoup else mock_detail_html

        with patch.object(collector, "_fetch_html_or_soup", return_value=mock_content):
            parsed = collector._parse_detail_page("https://wevity.com/view/123")

            self.assertEqual(parsed["category"], "웹/모바일/IT")
            self.assertIn("대학생", parsed["target"])
            self.assertIn("과학기술정보통신부", parsed["organizer"])
            self.assertEqual(parsed["apply_start"], "2026-11-01")
            self.assertEqual(parsed["apply_end"], "2026-12-20")
            self.assertEqual(parsed["homepage_url"], "https://official-contest-site.kr/register")
            self.assertIn("생성형 AI", parsed["description"])


if __name__ == "__main__":
    unittest.main()
