"""Persistence and deduplication for contests state in data/contests.json."""
from __future__ import annotations

import difflib
import json
import logging
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.models import Contest, normalize_title, normalize_url

logger = logging.getLogger(__name__)


def _same_edition(left: Contest, right: Contest) -> bool:
    """Avoid merging different years or numbered editions of a recurring contest."""
    left_years = set(re.findall(r"20\d{2}", left.title))
    right_years = set(re.findall(r"20\d{2}", right.title))
    if left_years and right_years and left_years.isdisjoint(right_years):
        return False
    left_rounds = set(re.findall(r"제\s*(\d+)\s*회|시즌\s*(\d+)", left.title))
    right_rounds = set(re.findall(r"제\s*(\d+)\s*회|시즌\s*(\d+)", right.title))
    if left_rounds and right_rounds and left_rounds.isdisjoint(right_rounds):
        return False
    return True


def _same_title(left: Contest, right: Contest) -> bool:
    if not _same_edition(left, right):
        return False
    left_title = normalize_title(left.title)
    right_title = normalize_title(right.title)
    if not left_title or not right_title:
        return False
    ratio = difflib.SequenceMatcher(None, left_title, right_title).ratio()
    if ratio >= 0.85:
        return True
    # Portals often add different event prefixes around the same long title.
    if not left.apply_end or left.apply_end != right.apply_end:
        return False
    compact_left = left_title.replace(" ", "")
    compact_right = right_title.replace(" ", "")
    match = difflib.SequenceMatcher(None, compact_left, compact_right).find_longest_match()
    return match.size >= 15 and match.size / min(len(compact_left), len(compact_right)) >= 0.55


class ContestStorage:
    """Manages loading, deduplicating, updating, and saving contests."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self._contests: Dict[str, Contest] = {}
        self.last_digest_date: Optional[str] = None
        self.last_test_digest_date: Optional[str] = None
        self.source_counts: Dict[str, int] = {}
        self.partial_digest_date: Optional[str] = None
        self.partial_digest_ids: List[str] = []
        self.load()

    @property
    def contests(self) -> List[Contest]:
        """Return list of all stored contests."""
        return list(self._contests.values())

    def get_contest(self, contest_id: str) -> Optional[Contest]:
        """Get contest by ID."""
        return self._contests.get(contest_id)

    def load(self) -> None:
        """Load contests from JSON file."""
        self.last_digest_date = None
        self.last_test_digest_date = None
        self.source_counts = {}
        self.partial_digest_date = None
        self.partial_digest_ids = []
        if not self.file_path.exists():
            logger.info("Storage file %s does not exist. Initializing empty storage.", self.file_path)
            self._contests = {}
            self.last_digest_date = None
            return

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    self._contests = {}
                    self.last_digest_date = None
                    return
                data = json.loads(content)

            items = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = data.get("contests", [])
                self.last_digest_date = data.get("last_digest_date")
                self.last_test_digest_date = data.get("last_test_digest_date")
                self.source_counts = data.get("source_counts", {})
                self.partial_digest_date = data.get("partial_digest_date")
                self.partial_digest_ids = data.get("partial_digest_ids", [])

            self._contests = {}
            for item in items:
                try:
                    contest = Contest(**item)
                    self._contests[contest.id] = contest
                except Exception as ex:
                    logger.warning("Failed to parse contest item %s: %s", item.get("title"), ex)

            loaded = list(self._contests.values())
            self._contests = {}
            for contest in loaded:
                existing = self.find_duplicate(contest)
                if existing is None:
                    self._contests[contest.id] = contest
                    continue
                if not existing.apply_end and contest.apply_end:
                    existing.apply_end = contest.apply_end
                if not existing.apply_start and contest.apply_start:
                    existing.apply_start = contest.apply_start
                if existing.organizer == "미확인 / 상세 공고 참조" and contest.organizer:
                    existing.organizer = contest.organizer
                if existing.target == "미확인 / 상세 공고 참조" and contest.target:
                    existing.target = contest.target
                if not existing.description and contest.description:
                    existing.description = contest.description
                for stage in contest.alert_history:
                    if stage not in existing.alert_history:
                        existing.alert_history.append(stage)
                if contest.last_alert_at and (not existing.last_alert_at or contest.last_alert_at > existing.last_alert_at):
                    existing.last_alert_at = contest.last_alert_at
                if contest.id in self.partial_digest_ids:
                    self.partial_digest_ids = [existing.id if item_id == contest.id else item_id for item_id in self.partial_digest_ids]
            if len(loaded) != len(self._contests):
                logger.info("Merged %d duplicate stored contests.", len(loaded) - len(self._contests))

            logger.info("Loaded %d contests from %s", len(self._contests), self.file_path)
        except Exception as e:
            logger.error("Error reading storage file %s: %s", self.file_path, e)
            self._contests = {}
            self.last_digest_date = None
            self.source_counts = {}
            self.partial_digest_date = None
            self.partial_digest_ids = []

    def find_duplicate(self, candidate: Contest) -> Optional[Contest]:
        """
        Check if a candidate contest matches any existing contest by:
        1. Exact ID
        2. Normalized URL
        3. Title similarity >= 0.85
        """
        # 1. Exact ID
        if candidate.id in self._contests:
            return self._contests[candidate.id]

        cand_norm_url = normalize_url(candidate.url)
        for existing in self._contests.values():
            # 2. Normalized URL match
            if cand_norm_url and cand_norm_url == normalize_url(existing.url) and _same_edition(candidate, existing):
                return existing

            # 3. Same edition and sufficiently similar title
            if _same_title(candidate, existing):
                return existing

        return None

    def add_or_update(
        self, candidates: List[Contest]
    ) -> Tuple[List[Contest], List[Contest]]:
        """
        Merge candidate contests into storage.
        Returns (newly_added_contests, updated_existing_contests).
        """
        new_contests: List[Contest] = []
        updated_contests: List[Contest] = []

        for cand in candidates:
            existing = self.find_duplicate(cand)
            if existing:
                # Merge any missing or updated information into existing without losing alert_history
                modified = False
                if cand.apply_end and cand.apply_end != existing.apply_end:
                    existing.apply_end = cand.apply_end
                    modified = True
                if cand.apply_start and cand.apply_start != existing.apply_start:
                    existing.apply_start = cand.apply_start
                    modified = True
                if cand.event_date and cand.event_date != existing.event_date:
                    existing.event_date = cand.event_date
                    modified = True
                if cand.organizer and (existing.organizer == "미확인 / 상세 공고 참조" or not existing.organizer):
                    existing.organizer = cand.organizer
                    modified = True
                if modified:
                    updated_contests.append(existing)
            else:
                self._contests[cand.id] = cand
                new_contests.append(cand)

        return new_contests, updated_contests

    def mark_alert_sent(self, contest_id: str, stage: str) -> None:
        """Mark an alert stage as sent for a contest."""
        contest = self._contests.get(contest_id)
        if contest:
            contest.record_alert(stage)

    def mark_closed(self, contest_id: str) -> None:
        """Mark a contest as closed."""
        contest = self._contests.get(contest_id)
        if contest:
            contest.status = "CLOSED"

    def save(self) -> None:
        """Save contests atomically to JSON file."""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "updated_at": datetime.now().isoformat(),
            "last_digest_date": self.last_digest_date,
            "last_test_digest_date": self.last_test_digest_date,
            "source_counts": self.source_counts,
            "partial_digest_date": self.partial_digest_date,
            "partial_digest_ids": self.partial_digest_ids,
            "contests": [c.model_dump() for c in self._contests.values()],
        }

        # Atomic file write using temporary file
        temp_dir = self.file_path.parent
        with tempfile.NamedTemporaryFile("w", dir=temp_dir, delete=False, encoding="utf-8") as tf:
            json.dump(payload, tf, ensure_ascii=False, indent=2)
            temp_name = tf.name

        try:
            # os.replace handles atomic overwrite on both Windows & POSIX
            os.replace(temp_name, self.file_path)
            logger.info("Successfully saved %d contests to %s", len(self._contests), self.file_path)
        except Exception as e:
            logger.error("Failed to atomic replace file: %s", e)
            if os.path.exists(temp_name):
                os.remove(temp_name)
            raise
