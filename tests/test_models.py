"""Unit tests for models and normalization functions."""
import unittest
from datetime import date

from src.models import Contest, normalize_title, normalize_url


class TestModels(unittest.TestCase):
    def test_normalize_url(self):
        raw_url = "https://Example.COM/contest/view/?id=123&utm_source=twitter&utm_medium=social"
        normalized = normalize_url(raw_url)
        self.assertEqual("https://example.com/contest/view?id=123", normalized)
        self.assertNotIn("utm_source", normalized)

        # Trailing slash handling
        self.assertEqual(normalize_url("https://example.com/path/"), "https://example.com/path")

    def test_normalize_title(self):
        raw = "[접수중] 2026 제1회 AI 해커톤 대회 (대학생 부문)!"
        cleaned = normalize_title(raw)
        self.assertIn("2026 제1회 ai 해커톤 대회", cleaned)
        self.assertNotIn("[", cleaned)
        self.assertNotIn("!", cleaned)
        self.assertIn("서울관광 프롬프톤", normalize_title("[2026 서울관광 프롬프톤] 참가자모집"))

    def test_contest_id_determinism(self):
        url = "https://example.com/hackathon"
        title = "대학생 AI SW 경진대회"
        id1 = Contest.generate_id(url, title)
        id2 = Contest.generate_id(url, title)
        self.assertEqual(id1, id2)
        self.assertEqual(len(id1), 16)

    def test_contest_create(self):
        contest = Contest.create(
            title="2026 대학생 ICT 융합 공모전",
            url="https://ict-contest.kr/view",
            organizer="과학기술정보통신부",
            apply_start="2026-11-01",
            apply_end="2026-11-25",
        )
        self.assertEqual(contest.organizer, "과학기술정보통신부")
        self.assertEqual(contest.status, "ACTIVE")
        self.assertEqual(contest.alert_history, [])
        self.assertEqual(len(contest.id), 16)

    def test_days_until_deadline_and_labels(self):
        contest = Contest.create(
            title="마감 테스트 공모전",
            url="https://example.com/test",
            apply_end="2026-11-25",
        )
        today = date(2026, 11, 18)
        self.assertEqual(contest.days_until_deadline(today), 7)
        self.assertEqual(contest.get_d_day_label(today), "D-7")

        d_day_date = date(2026, 11, 25)
        self.assertEqual(contest.days_until_deadline(d_day_date), 0)
        self.assertEqual(contest.get_d_day_label(d_day_date), "D-Day (오늘 마감!)")

        past_date = date(2026, 11, 26)
        self.assertEqual(contest.days_until_deadline(past_date), -1)
        self.assertIn("마감 완료", contest.get_d_day_label(past_date))

    def test_alert_recording(self):
        contest = Contest.create(
            title="알림 테스트",
            url="https://example.com/alert",
        )
        self.assertFalse(contest.has_alert_sent("NEW"))
        contest.record_alert("NEW")
        self.assertTrue(contest.has_alert_sent("NEW"))
        self.assertIn("NEW", contest.alert_history)

        # Duplicate record check
        contest.record_alert("NEW")
        self.assertEqual(contest.alert_history.count("NEW"), 1)


if __name__ == "__main__":
    unittest.main()
