"""Unit tests for collector JSON extraction and Wevity HTML parsing."""
import unittest
from unittest.mock import patch

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

from src.collectors.gemini_search import extract_json_array
from src.collectors.wevity_collector import WevityCollector


class TestCollectors(unittest.TestCase):
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
