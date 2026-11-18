"""ContestBot orchestrator coordinating collection, filtering, deduplication, and alerting."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from src.collectors.fallback import FallbackCollectorManager
from src.config import config
from src.deadline import get_current_kst_date, get_due_alert_stage
from src.discord import DiscordWebhookClient
from src.filter import filter_contest
from src.models import Contest
from src.storage import ContestStorage

logger = logging.getLogger(__name__)


class ContestBot:
    """Core controller for the ICT Contest Bot system."""

    def __init__(self):
        self.config = config
        self.storage = ContestStorage(self.config.data_file)
        self.collector = FallbackCollectorManager()
        self.discord = DiscordWebhookClient(
            webhook_url=self.config.discord_webhook_url,
            request_timeout=self.config.request_timeout,
        )

    def run(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Execute full contest alert pipeline:
        1. Collect candidates via Gemini / Wevity fallback
        2. Filter domestic university student eligibility & ICT/CS relevance
        3. Deduplicate against existing data/contests.json
        4. Summarize all open contests in one deadline-ordered Discord message per day
        5. Record the digest date and included alert stages
        6. Persist state to data/contests.json (skipped in dry-run)
        """
        logger.info("Starting ICT Contest Bot run (dry_run=%s)...", dry_run)
        today = get_current_kst_date()
        logger.info("Current KST Date: %s", today.isoformat())

        results = {
            "collected_raw": 0,
            "filtered_valid": 0,
            "new_contests": 0,
            "updated_contests": 0,
            "deadline_alerts": 0,
            "total_stored": len(self.storage.contests),
            "errors": [],
        }

        # Step 1: Collection
        try:
            raw_candidates = self.collector.collect()
            results["collected_raw"] = len(raw_candidates)
        except Exception as e:
            logger.error("Error during contest collection: %s", e)
            results["errors"].append(str(e))
            raw_candidates = []

        # Step 2: Filtering
        valid_candidates: List[Contest] = []
        for cand in raw_candidates:
            is_valid, reason = filter_contest(
                title=cand.title,
                target=cand.target,
                category=cand.category,
                description=cand.description or "",
                apply_end=cand.apply_end,
                today=today,
            )
            if is_valid:
                valid_candidates.append(cand)
            else:
                logger.debug("Filtered out '%s': %s", cand.title, reason)

        results["filtered_valid"] = len(valid_candidates)
        logger.info("Filtered %d valid ICT contests open to university students.", len(valid_candidates))

        # Step 3: Deduplication & Storage Update
        new_contests, updated_contests = self.storage.add_or_update(valid_candidates)
        results["new_contests"] = len(new_contests)
        results["updated_contests"] = len(updated_contests)
        logger.info(
            "Deduplication complete: %d new contests, %d updated contests.",
            len(new_contests),
            len(updated_contests),
        )

        # Step 4: Prepare the full daily digest, including previously announced contests.
        announcements = {}
        for contest in self.storage.contests:
            # Skip if already closed
            if contest.status == "CLOSED":
                continue

            # Check if contest deadline has passed
            days_left = contest.days_until_deadline(today)
            if days_left is not None and days_left < 0:
                logger.debug("Contest '%s' deadline passed (D%d). Marking CLOSED.", contest.title, days_left)
                if not dry_run:
                    self.storage.mark_closed(contest.id)
                continue

            announcements[contest.id] = (
                contest, "NEW" if not contest.has_alert_sent("NEW") else "ONGOING"
            )

            # Check if an alert stage is due today
            stage = get_due_alert_stage(
                apply_end_str=contest.apply_end,
                alert_history=contest.alert_history,
                alert_days=self.config.alert_days,
                today_kst=today,
            )

            if stage:
                logger.info("Contest '%s' reached alert stage %s (D-%d)", contest.title, stage, days_left)
                announcements[contest.id] = (contest, stage)

        new_alerts_sent = 0
        deadline_alerts_sent = 0
        if announcements and (dry_run or self.storage.last_digest_date != today.isoformat()):
            success, msg, included = self.discord.send_digest(
                list(announcements.values()), dry_run=dry_run
            )
            if success:
                if not dry_run:
                    self.storage.last_digest_date = today.isoformat()
                for contest, stage in included:
                    if not contest.has_alert_sent("NEW"):
                        new_alerts_sent += 1
                        if not dry_run:
                            self.storage.mark_alert_sent(contest.id, "NEW")
                    if stage not in ("NEW", "ONGOING"):
                        deadline_alerts_sent += 1
                        if not dry_run:
                            self.storage.mark_alert_sent(contest.id, stage)
                if len(included) < len(announcements):
                    logger.warning("Discord digest omitted %d contests due to length limits.", len(announcements) - len(included))
            else:
                logger.warning("Failed to send Discord digest: %s", msg)
        elif announcements:
            logger.info("Today's Discord digest was already sent; skipping duplicate notification.")

        results["deadline_alerts"] = deadline_alerts_sent

        # Step 6: Persist Updated State to data/contests.json
        if not dry_run:
            try:
                self.storage.save()
                logger.info("Successfully persisted contest database.")
            except Exception as e:
                logger.error("Failed to save contests state: %s", e)
                results["errors"].append(str(e))
        else:
            logger.info("[DRY-RUN] State persistence to %s was skipped.", self.config.data_file)

        results["total_stored"] = len(self.storage.contests)
        logger.info(
            "Pipeline completed successfully. Summary: %d new alerts, %d deadline alerts, %d total stored.",
            new_alerts_sent,
            deadline_alerts_sent,
            results["total_stored"],
        )
        return results
