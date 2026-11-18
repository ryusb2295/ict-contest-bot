"""Tests for the single Discord digest message."""
import unittest
from datetime import date
from unittest.mock import patch

from src.discord import DiscordWebhookClient
from src.models import Contest


class TestDiscord(unittest.TestCase):
    def test_digest_sorts_deadlines_and_posts_once(self):
        client = DiscordWebhookClient(webhook_url="https://discord.com/api/webhooks/mock")
        later = Contest.create(title="늦은 공모전", url="https://example.com/later", apply_end="2026-12-10")
        sooner = Contest.create(title="빠른 공모전", url="https://example.com/sooner", apply_end="2026-11-20")
        unknown = Contest.create(title="날짜 미확인", url="https://example.com/unknown")

        with patch("src.discord.get_current_kst_date", return_value=date(2026, 11, 19)):
            with patch.object(client, "_post_payload", return_value=(True, "SUCCESS")) as post:
                success, _, included = client.send_digest(
                    [(unknown, "NEW"), (later, "NEW"), (sooner, "D-1")]
                )

        self.assertTrue(success)
        self.assertEqual(post.call_count, 1)
        self.assertEqual([c.title for c, _ in included], ["빠른 공모전", "늦은 공모전", "날짜 미확인"])
        description = post.call_args.args[0]["embeds"][0]["description"]
        self.assertLess(description.index("빠른 공모전"), description.index("늦은 공모전"))
        self.assertIn("마감 **2026.11.20 · D-1**", description)
        self.assertIn("[빠른 공모전](https://example.com/sooner)", description)
        self.assertIn("주최", description)
        self.assertIn("대상", description)

    def test_long_digest_uses_multiple_embeds_in_one_message(self):
        client = DiscordWebhookClient(webhook_url="https://discord.com/api/webhooks/mock")
        contests = [
            Contest.create(
                title=f"AI Agent 개발 경진대회 {i} " + "기술" * 60,
                url=f"https://example.com/contest/{i}",
                apply_end="2026-12-10",
            )
            for i in range(22)
        ]
        with patch.object(client, "_post_payload", return_value=(True, "SUCCESS")) as post:
            success, _, included = client.send_digest([(item, "NEW") for item in contests])
        self.assertTrue(success)
        self.assertEqual(post.call_count, 1)
        self.assertEqual(len(post.call_args.args[0]["embeds"]), 2)
        self.assertEqual(len(included), len(contests))

    def test_dry_run_and_failed_send_do_not_claim_alerts(self):
        client = DiscordWebhookClient(webhook_url="")
        contest = Contest.create(title="테스트 공모전", url="https://example.com/dry")
        success, msg, included = client.send_digest([(contest, "NEW")], dry_run=True)
        self.assertTrue(success)
        self.assertEqual(msg, "DRY_RUN_OK")
        self.assertEqual(len(included), 1)

        success, _, included = client.send_digest([(contest, "NEW")])
        self.assertFalse(success)
        self.assertEqual(included, [])

    def test_empty_webhook_send_fails_cleanly(self):
        client = DiscordWebhookClient(webhook_url="")
        success, msg = client.send_test_message()
        self.assertFalse(success)
        self.assertTrue("환경변수" in msg or "DISCORD_WEBHOOK_URL" in msg)


if __name__ == "__main__":
    unittest.main()
