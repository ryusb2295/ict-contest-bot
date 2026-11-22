"""Free Gemini review accepts only evidence-backed exclusions."""
import json
import unittest
from unittest.mock import Mock, patch

import requests

from src.gemini_refiner import GeminiRefiner
from src.models import Contest


class TestGeminiRefiner(unittest.TestCase):
    def setUp(self):
        self.contest = Contest.create(
            title="AI 영상 제작 공모전", url="https://example.com/video",
            target="대학생", apply_end="2026-12-10",
        )
        self.refiner = GeminiRefiner(api_key="test-key", model="gemini-3.5-flash-lite")

    def test_excludes_only_with_source_evidence(self):
        decision = [{"id": self.contest.id, "decision": "exclude",
                     "reason": "creative", "evidence": "영상 제작"}]
        response = Mock(status_code=200)
        response.json.return_value = {"candidates": [{"content": {"parts": [{"text": json.dumps(decision)}]}}]}
        with patch("src.gemini_refiner.requests.post", return_value=response) as post:
            self.assertEqual(self.refiner.refine([self.contest]), [])
        self.assertIn("gemini-3.5-flash-lite", post.call_args.args[0])
        self.assertNotIn("google_search", str(post.call_args.kwargs["json"]))

        decision[0]["evidence"] = "원문에 없는 근거"
        response.json.return_value["candidates"][0]["content"]["parts"][0]["text"] = json.dumps(decision)
        with patch("src.gemini_refiner.requests.post", return_value=response):
            self.assertEqual(self.refiner.refine([self.contest]), [self.contest])

    def test_api_failure_keeps_candidates(self):
        with patch("src.gemini_refiner.requests.post", side_effect=requests.Timeout):
            self.assertEqual(self.refiner.refine([self.contest]), [self.contest])
