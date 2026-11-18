"""Unit tests for Discord Webhook embed construction and dry-run dispatch."""
import unittest

from src.discord import (
    COLOR_D1,
    COLOR_D3,
    COLOR_D7,
    COLOR_NEW,
    DiscordWebhookClient,
)
from src.models import Contest


class TestDiscord(unittest.TestCase):
    def test_build_contest_embed_new(self):
        client = DiscordWebhookClient(webhook_url="https://discord.com/api/webhooks/mock")
        contest = Contest.create(
            title="2026 대학생 생성형 AI 해커톤",
            url="https://hackathon.ai",
            organizer="정보통신기획평가원",
            category="인공지능, SW",
            target="전국 대학생",
            apply_start="2026-11-01",
            apply_end="2026-12-10",
        )

        embed = client.build_contest_embed(contest, alert_type="NEW")
        self.assertIn("[신규 공고]", embed["title"])
        self.assertEqual(embed["color"], COLOR_NEW)
        self.assertEqual(embed["url"], "https://hackathon.ai")

        field_names = [f["name"] for f in embed["fields"]]
        self.assertTrue(any("주최" in n for n in field_names))
        self.assertTrue(any("참가자격" in n for n in field_names))
        self.assertTrue(any("접수기간" in n for n in field_names))
        self.assertTrue(any("공식 공고" in n for n in field_names))

    def test_build_contest_embed_deadline_stages(self):
        client = DiscordWebhookClient(webhook_url="https://discord.com/api/webhooks/mock")
        contest = Contest.create(
            title="2026 빅데이터 경진대회",
            url="https://dacon.io/test",
            apply_end="2026-11-25",
        )

        embed_d7 = client.build_contest_embed(contest, alert_type="DEADLINE", stage="D-7")
        self.assertIn("[마감 D-7]", embed_d7["title"])
        self.assertEqual(embed_d7["color"], COLOR_D7)

        embed_d3 = client.build_contest_embed(contest, alert_type="DEADLINE", stage="D-3")
        self.assertIn("[마감 D-3]", embed_d3["title"])
        self.assertEqual(embed_d3["color"], COLOR_D3)

        embed_d1 = client.build_contest_embed(contest, alert_type="DEADLINE", stage="D-1")
        self.assertIn("[마감 D-1", embed_d1["title"])
        self.assertEqual(embed_d1["color"], COLOR_D1)

    def test_dry_run_dispatch(self):
        client = DiscordWebhookClient(webhook_url="")
        contest = Contest.create(
            title="테스트 공모전",
            url="https://example.com/dry",
        )
        success, msg = client.send_new_contest(contest, dry_run=True)
        self.assertTrue(success)
        self.assertEqual(msg, "DRY_RUN_OK")

        success_d, msg_d = client.send_deadline_alert(contest, stage="D-7", dry_run=True)
        self.assertTrue(success_d)
        self.assertEqual(msg_d, "DRY_RUN_OK")

    def test_empty_webhook_send_fails_cleanly(self):
        client = DiscordWebhookClient(webhook_url="")
        success, msg = client.send_test_message()
        self.assertFalse(success)
        self.assertTrue("환경변수" in msg or "DISCORD_WEBHOOK_URL" in msg)


if __name__ == "__main__":
    unittest.main()
