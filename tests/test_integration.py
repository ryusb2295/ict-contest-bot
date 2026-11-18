"""Integration tests for end-to-end bot execution with mocked APIs."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.bot import ContestBot
from src.config import Config
from src.models import Contest


class TestBotIntegration(unittest.TestCase):
    def test_full_bot_pipeline_with_mocked_collectors(self):
        """Simulate end-to-end bot execution with mock collectors and webhook."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_db = Path(tmp_dir) / "contests.json"

            # Create mock candidates
            cand1 = Contest.create(
                title="2026 전국 대학생 AI 해커톤",
                url="https://ai-hackathon.kr",
                organizer="과학기술정보통신부",
                category="인공지능, SW",
                target="전국 대학생",
                apply_start="2026-11-01",
                apply_end="2026-11-25",  # D-7 for today 2026-11-18
                description="대학생 생성형 AI 개발 대회",
            )
            cand2 = Contest.create(
                title="제1회 초등학생 글짓기 대회",  # should be filtered out
                url="https://kids-writing.kr",
                category="문학",
                target="초등학생 전용",
                apply_end="2026-12-01",
            )

            # Initialize bot with custom test file
            bot = ContestBot()
            bot.config.data_file = test_db
            bot.storage = bot.storage.__class__(test_db)

            # Mock collector to return our test candidates
            with patch.object(bot.collector, "collect", return_value=[cand1, cand2]):
                # Mock Discord client to simulate successful send
                with patch.object(bot.discord, "_post_payload", return_value=(True, "SUCCESS")):
                    # Execute bot run
                    results = bot.run(dry_run=False)

                    # Verify results
                    self.assertEqual(results["collected_raw"], 2)
                    self.assertEqual(results["filtered_valid"], 1)  # cand2 filtered out
                    self.assertEqual(results["new_contests"], 1)
                    self.assertEqual(results["total_stored"], 1)
                    self.assertEqual(len(results["errors"]), 0)

                    # Verify that state was written to disk
                    self.assertTrue(test_db.exists())
                    with open(test_db, "r", encoding="utf-8") as f:
                        saved_data = json.load(f)
                        self.assertEqual(len(saved_data["contests"]), 1)
                        self.assertEqual(saved_data["contests"][0]["title"], "2026 전국 대학생 AI 해커톤")
                        self.assertIn("NEW", saved_data["contests"][0]["alert_history"])

    def test_bot_dry_run_does_not_mutate_storage(self):
        """Verify that dry-run mode does not touch storage file."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_db = Path(tmp_dir) / "contests.json"

            cand = Contest.create(
                title="2026 로봇 경진대회",
                url="https://robot.kr",
                target="대학생",
                apply_end="2026-12-01",
            )

            bot = ContestBot()
            bot.config.data_file = test_db
            bot.storage = bot.storage.__class__(test_db)

            with patch.object(bot.collector, "collect", return_value=[cand]):
                results = bot.run(dry_run=True)
                self.assertEqual(results["new_contests"], 1)
                # Storage file must NOT exist because save was skipped
                self.assertFalse(test_db.exists())


if __name__ == "__main__":
    unittest.main()
