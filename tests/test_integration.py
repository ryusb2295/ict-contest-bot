"""Integration tests for end-to-end bot execution with mocked APIs."""
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.bot import ContestBot
from src.config import Config
from src.models import Contest


class TestBotIntegration(unittest.TestCase):
    def setUp(self):
        self.config_patch = patch("src.bot.config", Config(gemini_refine_enabled=False, gemini_search_enabled=False))
        self.config_patch.start()

    def tearDown(self):
        self.config_patch.stop()

    def test_optional_gemini_review_runs_after_rule_filter(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            bot = ContestBot()
            bot.storage = bot.storage.__class__(Path(tmp_dir) / "contests.json")
            bot.config.gemini_refine_enabled = True
            bot.config.gemini_api_key = "test-key"
            candidate = Contest.create(title="대학생 AI 서비스 개발 경진대회",
                                       url="https://example.com/ai", target="대학생",
                                       apply_end="2026-12-10")
            with patch("src.bot.get_current_kst_date", return_value=date(2026, 11, 22)):
                with patch.object(bot.collector, "collect", return_value=[candidate]):
                    with patch.object(bot.refiner, "refine", return_value=[]) as refine:
                        result = bot.run(dry_run=True)
            refine.assert_called_once()
            self.assertEqual(result["gemini_excluded"], 1)
            self.assertEqual(result["filtered_valid"], 0)

    def test_partial_digest_resumes_without_repeating_sent_contests(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            bot = ContestBot()
            bot.storage = bot.storage.__class__(Path(tmp_dir) / "contests.json")
            titles = ["AI 모델 개발 경진대회", "로봇 자율주행 해커톤", "데이터 분석 챌린지"]
            contests = [Contest.create(title=title, url=f"https://example.com/{i}",
                                       target="대학생", apply_end="2026-11-30") for i, title in enumerate(titles)]
            bot.storage.add_or_update(contests)
            sent_batches = []

            def send_digest(items, dry_run=False, on_page_sent=None):
                sent_batches.append([contest.id for contest, _ in items])
                if len(sent_batches) == 1:
                    on_page_sent(items[:1])
                    return False, "HTTP 500", items[:1]
                on_page_sent(items)
                return True, "SUCCESS", items

            with patch("src.bot.get_current_kst_date", return_value=date(2026, 11, 22)):
                with patch.object(bot.collector, "collect", return_value=[]):
                    with patch.object(bot.discord, "send_digest", side_effect=send_digest):
                        first_result = bot.run()
                        self.assertIsNone(bot.storage.last_digest_date)
                        self.assertIn("Discord digest delivery failed: HTTP 500", first_result["errors"])
                        saved = json.loads((Path(tmp_dir) / "contests.json").read_text(encoding="utf-8"))
                        self.assertEqual(saved["partial_digest_ids"], [sent_batches[0][0]])
                        bot.storage = bot.storage.__class__(Path(tmp_dir) / "contests.json")
                        bot.run()
            self.assertEqual(len(sent_batches[0]), 3)
            self.assertEqual(len(sent_batches[1]), 2)
            self.assertNotIn(sent_batches[0][0], sent_batches[1])
            self.assertEqual(bot.storage.last_digest_date, "2026-11-22")

    def test_source_drop_sends_warning(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            bot = ContestBot()
            bot.storage = bot.storage.__class__(Path(tmp_dir) / "contests.json")
            bot.storage.source_counts = {"wevity": 4, "daker": 0}
            bot.collector.source_counts = {"wevity": 0, "daker": 0}
            bot.collector.source_errors = {}
            with patch("src.bot.get_current_kst_date", return_value=date(2026, 11, 22)):
                with patch.object(bot.collector, "collect", return_value=[]):
                    with patch.object(bot.discord, "send_source_warning", return_value=(True, "HTTP 204")) as warn:
                        result = bot.run()
            self.assertTrue(result["source_warnings"])
            warn.assert_called_once()
            self.assertEqual(bot.storage.source_counts["wevity"], 0)

    def test_manual_digest_can_send_once_after_daily_digest(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            bot = ContestBot()
            bot.storage = bot.storage.__class__(Path(tmp_dir) / "contests.json")
            contest = Contest.create(
                title="AI Agent 개발 경진대회",
                url="https://example.com/agent",
                target="대학생",
                apply_end="2026-11-30",
            )
            bot.storage.add_or_update([contest])
            bot.storage.last_digest_date = "2026-11-19"
            with patch("src.bot.get_current_kst_date", return_value=date(2026, 11, 19)):
                with patch.object(bot.collector, "collect", return_value=[]):
                    with patch.object(bot.discord, "_post_payload", return_value=(True, "SUCCESS")) as post:
                        bot.run(send_test_digest=True)
                        bot.run(send_test_digest=True)
            self.assertEqual(post.call_count, 1)
            self.assertEqual(bot.storage.last_test_digest_date, "2026-11-19")

    def test_new_and_deadline_alerts_share_one_message(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            bot = ContestBot()
            bot.storage = bot.storage.__class__(Path(tmp_dir) / "contests.json")
            existing = Contest.create(
                title="대학생 AI 모델 개발 마감 임박 공모전",
                url="https://example.com/due",
                target="대학생",
                apply_end="2026-11-20",
            )
            new = Contest.create(
                title="대학생 SW 신규 공모전",
                url="https://example.com/new",
                target="대학생",
                apply_end="2026-11-30",
            )
            ongoing = Contest.create(
                title="대학생 데이터 분석 진행 중 공모전",
                url="https://example.com/ongoing",
                target="대학생",
                apply_end="2026-12-15",
            )
            creative = Contest.create(
                title="AI 광고 제작 공모전",
                url="https://example.com/creative",
                target="누구나",
                apply_end="2026-12-20",
            )
            bot.storage.add_or_update([existing, ongoing, creative])
            bot.storage.mark_alert_sent(existing.id, "NEW")
            bot.storage.mark_alert_sent(ongoing.id, "NEW")

            with patch("src.bot.get_current_kst_date", return_value=date(2026, 11, 19)):
                with patch("src.discord.get_current_kst_date", return_value=date(2026, 11, 19)):
                    with patch.object(bot.collector, "collect", return_value=[new]):
                        with patch.object(bot.discord, "_post_payload", return_value=(True, "SUCCESS")) as post:
                            result = bot.run()
                            bot.run()

            self.assertEqual(post.call_count, 1)
            description = post.call_args.args[0]["embeds"][0]["description"]
            self.assertLess(description.index(existing.title), description.index(new.title))
            self.assertIn(ongoing.title, description)
            self.assertNotIn(creative.title, description)
            self.assertEqual(result["deadline_alerts"], 1)
            self.assertEqual(bot.storage.last_digest_date, "2026-11-19")
            self.assertIn("D-1", bot.storage.get_contest(existing.id).alert_history)
            self.assertIn("NEW", bot.storage.get_contest(new.id).alert_history)

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
            with patch("src.bot.get_current_kst_date", return_value=date(2026, 11, 18)):
                with patch("src.discord.get_current_kst_date", return_value=date(2026, 11, 18)):
                    self._run_full_pipeline_assertions(bot, cand1, cand2, test_db)

    def _run_full_pipeline_assertions(self, bot, cand1, cand2, test_db):
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
