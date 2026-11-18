"""Persistence and deduplication for contests state in data/contests.json."""
from __future__ import annotations

import difflib
import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.models import Contest, normalize_title, normalize_url

logger = logging.getLogger(__name__)


class ContestStorage:
    """Manages loading, deduplicating, updating, and saving contests."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self._contests: Dict[str, Contest] = {}
        self.last_digest_date: Optional[str] = None
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

            self._contests = {}
            for item in items:
                try:
                    contest = Contest(**item)
                    self._contests[contest.id] = contest
                except Exception as ex:
                    logger.warning("Failed to parse contest item %s: %s", item.get("title"), ex)

            logger.info("Loaded %d contests from %s", len(self._contests), self.file_path)
        except Exception as e:
            logger.error("Error reading storage file %s: %s", self.file_path, e)
            self._contests = {}
            self.last_digest_date = None

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
        cand_norm_title = normalize_title(candidate.title)

        for existing in self._contests.values():
            # 2. Normalized URL match
            if cand_norm_url and cand_norm_url == normalize_url(existing.url):
                return existing

            # 3. High Title similarity match
            exist_norm_title = normalize_title(existing.title)
            if cand_norm_title and exist_norm_title:
                ratio = difflib.SequenceMatcher(None, cand_norm_title, exist_norm_title).ratio()
                if ratio >= 0.85:
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
