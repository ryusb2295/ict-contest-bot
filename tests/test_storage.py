"""Unit tests for storage, atomic persistence, and deduplication."""
import json
import tempfile
import unittest
from pathlib import Path

from src.models import Contest
from src.storage import ContestStorage


class TestStorage(unittest.TestCase):
    def test_cross_site_title_prefixes_deduplicate_but_new_year_does_not(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            storage = ContestStorage(Path(tmp_dir) / "contests.json")
            first = Contest.create(
                title="2026 대구 로컬AI그라운드 - 지역문제 해결형 AI활용 경진대회",
                url="https://official.example/contest", apply_end="2026-11-30",
            )
            same = Contest.create(
                title="2026 창업도시 프로젝트 <지역문제 해결형 AI활용 경진대회>",
                url="https://portal.example/view/123", apply_end="2026-11-30",
            )
            next_year = Contest.create(
                title="2027 대구 로컬AI그라운드 - 지역문제 해결형 AI활용 경진대회",
                url="https://official.example/next", apply_end="2027-11-30",
            )
            new, _ = storage.add_or_update([first, same, next_year])
            self.assertEqual(len(new), 2)

    def test_load_merges_existing_cross_site_duplicates_and_alert_history(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "contests.json"
            first = Contest.create(
                title="2026 대구 로컬AI그라운드 - 지역문제 해결형 AI활용 경진대회",
                url="https://official.example/contest", apply_end="2026-11-30",
            )
            same = Contest.create(
                title="2026 창업도시 프로젝트 <지역문제 해결형 AI활용 경진대회>",
                url="https://portal.example/view/123", apply_end="2026-11-30",
            )
            first.alert_history = ["NEW"]
            same.alert_history = ["D-7"]
            path.write_text(json.dumps({"contests": [first.model_dump(), same.model_dump()],
                                        "partial_digest_ids": [same.id]}), encoding="utf-8")
            storage = ContestStorage(path)
            self.assertEqual(len(storage.contests), 1)
            self.assertEqual(set(storage.contests[0].alert_history), {"NEW", "D-7"})
            self.assertEqual(storage.partial_digest_ids, [first.id])

    def test_same_homepage_keeps_different_years_separate(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            storage = ContestStorage(Path(tmp_dir) / "contests.json")
            contests = [Contest.create(title=f"{year} AI 개발 경진대회",
                                       url="https://example.com/contest", apply_end=f"{year}-11-30")
                        for year in (2026, 2027)]
            new, _ = storage.add_or_update(contests)
            self.assertEqual(len(new), 2)

    def test_different_rounds_in_same_year_are_separate(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            storage = ContestStorage(Path(tmp_dir) / "contests.json")
            contests = [Contest.create(title=f"2026 제{round_no}회 대학생 AI 개발 경진대회",
                                       url=f"https://example.com/{round_no}", apply_end="2026-11-30")
                        for round_no in (1, 2)]
            new, _ = storage.add_or_update(contests)
            self.assertEqual(len(new), 2)

    def test_storage_empty_initialization(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_file = Path(tmp_dir) / "contests.json"
            storage = ContestStorage(db_file)
            self.assertEqual(len(storage.contests), 0)

    def test_storage_add_and_deduplication(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_file = Path(tmp_dir) / "contests.json"
            storage = ContestStorage(db_file)

            c1 = Contest.create(
                title="2026 대학생 AI 해커톤",
                url="https://hackathon.or.kr/2026?utm_source=news",
                organizer="인공지능협회",
                apply_end="2026-12-01",
            )

            new_items, updated = storage.add_or_update([c1])
            self.assertEqual(len(new_items), 1)
            self.assertEqual(len(updated), 0)
            self.assertEqual(len(storage.contests), 1)

            # Add duplicate by URL with different query parameters
            c1_dup_url = Contest.create(
                title="2026 대학생 AI 해커톤 (추가 접수)",
                url="https://hackathon.or.kr/2026?utm_campaign=ad",
                organizer="인공지능협회",
                apply_end="2026-12-01",
            )
            new_items, updated = storage.add_or_update([c1_dup_url])
            self.assertEqual(len(new_items), 0)
            self.assertEqual(len(storage.contests), 1)

            # Add duplicate by high title similarity
            c1_dup_title = Contest.create(
                title="[접수중] 2026 대학생 AI 해커톤!",
                url="https://another-domain.com/hackathon",
                organizer="인공지능협회",
                apply_end="2026-12-05",  # new end date
            )
            new_items, updated = storage.add_or_update([c1_dup_title])
            self.assertEqual(len(new_items), 0)
            self.assertEqual(len(storage.contests), 1)
            # Check that field was updated without breaking existing state
            self.assertEqual(storage.get_contest(c1.id).apply_end, "2026-12-05")

            # Add completely new contest
            c2 = Contest.create(
                title="2026 임베디드 IoT 로봇 경진대회",
                url="https://robot-contest.kr",
                organizer="로봇산업진흥원",
            )
            new_items, updated = storage.add_or_update([c2])
            self.assertEqual(len(new_items), 1)
            self.assertEqual(len(storage.contests), 2)

    def test_storage_save_and_reload(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_file = Path(tmp_dir) / "contests.json"
            storage = ContestStorage(db_file)

            c = Contest.create(
                title="한글 공모전 테스트 (로봇/AI)",
                url="https://example.com/korean",
                organizer="과학기술정보통신부",
            )
            storage.add_or_update([c])
            storage.mark_alert_sent(c.id, "NEW")
            storage.last_digest_date = "2026-11-19"
            storage.last_test_digest_date = "2026-11-19"
            storage.save()

            # Verify JSON content on disk
            with open(db_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.assertIn("contests", data)
                self.assertEqual(len(data["contests"]), 1)
                self.assertEqual(data["contests"][0]["title"], "한글 공모전 테스트 (로봇/AI)")
                self.assertIn("NEW", data["contests"][0]["alert_history"])
                self.assertEqual(data["last_digest_date"], "2026-11-19")
                self.assertEqual(data["last_test_digest_date"], "2026-11-19")

            # Reload into new storage instance
            storage_reloaded = ContestStorage(db_file)
            self.assertEqual(len(storage_reloaded.contests), 1)
            self.assertEqual(storage_reloaded.last_digest_date, "2026-11-19")
            self.assertEqual(storage_reloaded.last_test_digest_date, "2026-11-19")
            reloaded_item = storage_reloaded.get_contest(c.id)
            self.assertIsNotNone(reloaded_item)
            self.assertEqual(reloaded_item.title, "한글 공모전 테스트 (로봇/AI)")
            self.assertTrue(reloaded_item.has_alert_sent("NEW"))


if __name__ == "__main__":
    unittest.main()
