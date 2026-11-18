"""Unit tests for deadline and alert stage calculations."""
import unittest
from datetime import date

from src.deadline import get_due_alert_stage, parse_date, parse_date_range


class TestDeadline(unittest.TestCase):
    def test_parse_date_valid_formats(self):
        self.assertEqual(parse_date("2026-11-25"), "2026-11-25")
        self.assertEqual(parse_date("2026.11.25"), "2026-11-25")
        self.assertEqual(parse_date("2026/11/25"), "2026-11-25")
        self.assertEqual(parse_date("26.11.25"), "2026-11-25")

    def test_parse_date_unconfirmed_must_be_none(self):
        """Requirement 3: Never guess unverified dates; return None."""
        self.assertIsNone(parse_date("미정"))
        self.assertIsNone(parse_date("추후 공지"))
        self.assertIsNone(parse_date("상세공고 참조"))
        self.assertIsNone(parse_date("상시 접수"))
        self.assertIsNone(parse_date(None))
        self.assertIsNone(parse_date(""))
        self.assertIsNone(parse_date("2026년"))  # missing month/day -> do not guess!

    def test_parse_date_range(self):
        start, end = parse_date_range("2026-10-20 ~ 2026-12-20")
        self.assertEqual(start, "2026-10-20")
        self.assertEqual(end, "2026-12-20")

        start2, end2 = parse_date_range("2026.11.01(금) - 2026.11.25(화)")
        self.assertEqual(start2, "2026-11-01")
        self.assertEqual(end2, "2026-11-25")

    def test_alert_stage_d7(self):
        today = date(2026, 11, 18)
        apply_end = "2026-11-25"  # exactly 7 days
        stage = get_due_alert_stage(apply_end, alert_history=[], today_kst=today)
        self.assertEqual(stage, "D-7")

        # Duplicate prevention: if D-7 already in history, must return None
        stage_dup = get_due_alert_stage(apply_end, alert_history=["D-7"], today_kst=today)
        self.assertIsNone(stage_dup)

    def test_alert_stage_d3(self):
        today = date(2026, 11, 22)
        apply_end = "2026-11-25"  # exactly 3 days
        stage = get_due_alert_stage(apply_end, alert_history=["D-7"], today_kst=today)
        self.assertEqual(stage, "D-3")

    def test_alert_stage_d1(self):
        today = date(2026, 11, 24)
        apply_end = "2026-11-25"  # exactly 1 day
        stage = get_due_alert_stage(apply_end, alert_history=["D-7", "D-3"], today_kst=today)
        self.assertEqual(stage, "D-1")

    def test_alert_stage_no_alert_when_not_matching_stage(self):
        today = date(2026, 11, 20)
        apply_end = "2026-11-25"  # 5 days left -> no alert due
        self.assertIsNone(get_due_alert_stage(apply_end, alert_history=[], today_kst=today))

    def test_alert_stage_past_deadline(self):
        today = date(2026, 11, 26)
        apply_end = "2026-11-25"  # -1 days (expired)
        self.assertIsNone(get_due_alert_stage(apply_end, alert_history=[], today_kst=today))


if __name__ == "__main__":
    unittest.main()
