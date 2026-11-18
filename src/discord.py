"""Discord Webhook integration for rich contest alerts."""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import urllib.request
import urllib.error

try:
    import requests
except ImportError:
    requests = None

from src.deadline import get_current_kst_date, get_current_kst_datetime
from src.models import Contest

logger = logging.getLogger(__name__)

# Discord Embed Colors (Decimal RGB)
COLOR_NEW = 0x3498DB       # Bright Blue
COLOR_D7 = 0xF1C40F        # Sunflower Yellow
COLOR_D3 = 0xE67E22        # Warning Orange
COLOR_D1 = 0xED4245        # Urgent Red
COLOR_TEST = 0x9B59B6      # Purple
COLOR_CLOSED = 0x95A5A6    # Gray


class DiscordWebhookClient:
    """Client for dispatching rich embeds to a Discord Webhook channel."""

    def __init__(self, webhook_url: str, request_timeout: int = 15):
        self.webhook_url = webhook_url.strip()
        self.request_timeout = request_timeout

    def _post_payload(self, payload: Dict[str, Any], dry_run: bool = False) -> Tuple[bool, str]:
        """Send payload to Discord Webhook."""
        if dry_run:
            logger.info("[DRY-RUN] Discord payload generated: %s", payload.get("embeds", [{}])[0].get("title"))
            return True, "DRY_RUN_OK"

        if not self.webhook_url:
            return False, "DISCORD_WEBHOOK_URL is not configured."

        try:
            if requests:
                headers = {"Content-Type": "application/json"}
                resp = requests.post(
                    self.webhook_url,
                    json=payload,
                    headers=headers,
                    timeout=self.request_timeout,
                )

                if resp.status_code in (200, 204):
                    return True, "SUCCESS"
                elif resp.status_code == 429:
                    retry_after = resp.json().get("retry_after", 2.0)
                    logger.warning("Discord rate limited. Waiting %s seconds.", retry_after)
                    time.sleep(float(retry_after))
                    retry_resp = requests.post(
                        self.webhook_url,
                        json=payload,
                        headers=headers,
                        timeout=self.request_timeout,
                    )
                    if retry_resp.status_code in (200, 204):
                        return True, "SUCCESS_AFTER_RETRY"
                    return False, f"HTTP {retry_resp.status_code}: {retry_resp.text}"
                else:
                    return False, f"HTTP {resp.status_code}: {resp.text}"
            else:
                # Standard library urllib fallback
                data_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                req = urllib.request.Request(
                    self.webhook_url,
                    data=data_bytes,
                    headers={"Content-Type": "application/json", "User-Agent": "ICTContestBot/1.0"},
                    method="POST",
                )
                try:
                    with urllib.request.urlopen(req, timeout=self.request_timeout) as resp:
                        if resp.status in (200, 204):
                            return True, "SUCCESS"
                        return True, f"HTTP {resp.status}"
                except urllib.error.HTTPError as he:
                    return False, f"HTTP {he.code}: {he.reason}"
        except Exception as e:
            logger.error("Exception sending Discord webhook: %s", e)
            return False, str(e)

    def build_contest_embed(
        self,
        contest: Contest,
        alert_type: str = "NEW",
        stage: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Construct Discord Embed dictionary for a contest."""
        today = get_current_kst_date()
        d_day_str = contest.get_d_day_label(today)

        # Title and color according to alert stage
        if alert_type == "NEW":
            title = f"📢 [신규 공고] {contest.title}"
            color = COLOR_NEW
        elif stage == "D-7":
            title = f"⏰ [마감 D-7] {contest.title}"
            color = COLOR_D7
        elif stage == "D-3":
            title = f"🔥 [마감 D-3] {contest.title}"
            color = COLOR_D3
        elif stage == "D-1":
            title = f"🚨 [마감 D-1 (내일 마감!)] {contest.title}"
            color = COLOR_D1
        else:
            title = f"📋 [공모전 알림] {contest.title}"
            color = COLOR_NEW

        period_display = (
            f"{contest.apply_start or '미확인'} ~ {contest.apply_end or '미확인 (상세 공고 참조)'}"
        )

        fields = [
            {"name": "🏢 주최/주관", "value": contest.organizer or "미확인", "inline": True},
            {"name": "🎯 참가자격", "value": contest.target or "국내 대학생", "inline": True},
            {"name": "🏷️ 공모분야", "value": contest.category or "ICT / SW / AI", "inline": True},
            {"name": "📅 접수기간", "value": period_display, "inline": False},
            {"name": "⏳ 마감 현황", "value": d_day_str, "inline": True},
            {"name": "🚩 행사/대회일", "value": contest.event_date or "상세 공고 참조", "inline": True},
            {"name": "🔗 공식 공고 링크", "value": f"[공식 공고 확인 및 접수 바로가기]({contest.url})", "inline": False},
        ]

        embed = {
            "title": title[:256],
            "url": contest.url,
            "description": (contest.description or "공식 링크에서 상세 요강을 확인하세요.")[:1000],
            "color": color,
            "fields": fields,
            "footer": {
                "text": f"ICT Contest Bot • 정보통신/컴퓨터공학 • 출처: {contest.source}",
            },
            "timestamp": get_current_kst_datetime().isoformat(),
        }
        return embed

    def send_new_contest(self, contest: Contest, dry_run: bool = False) -> Tuple[bool, str]:
        """Dispatch a new contest announcement embed."""
        embed = self.build_contest_embed(contest, alert_type="NEW")
        payload = {
            "username": "ICT 공모전 알리미",
            "embeds": [embed],
        }
        success, msg = self._post_payload(payload, dry_run=dry_run)
        if not dry_run and success:
            time.sleep(0.5)  # safe interval to prevent rate limit
        return success, msg

    def send_deadline_alert(
        self, contest: Contest, stage: str, dry_run: bool = False
    ) -> Tuple[bool, str]:
        """Dispatch a deadline alert (D-7, D-3, D-1) embed."""
        embed = self.build_contest_embed(contest, alert_type="DEADLINE", stage=stage)
        payload = {
            "username": "ICT 마감 임박 알리미",
            "embeds": [embed],
        }
        success, msg = self._post_payload(payload, dry_run=dry_run)
        if not dry_run and success:
            time.sleep(0.5)
        return success, msg

    def send_test_message(self) -> Tuple[bool, str]:
        """Dispatch a test message to verify Discord Webhook configuration."""
        if not self.webhook_url:
            return False, "DISCORD_WEBHOOK_URL 환경변수가 설정되지 않았습니다."

        now_kst = get_current_kst_datetime().strftime("%Y-%m-%d %H:%M:%S KST")
        embed = {
            "title": "✅ [테스트] ICT Contest Bot 웹후크 연결 성공!",
            "description": (
                "정보통신공학과 / 컴퓨터공학과 공모전 알리미 봇이 Discord 채널과 정상적으로 연결되었습니다.\n"
                "매일 오전 9시 17분에 신규 공고 및 D-7, D-3, D-1 마감 임박 공고가 자동 발송됩니다."
            ),
            "color": COLOR_TEST,
            "fields": [
                {"name": "⏰ 발송 테스트 시각", "value": now_kst, "inline": True},
                {"name": "🎯 수집 대상", "value": "해커톤 / AI / SW / 데이터 / IoT / 로봇", "inline": True},
                {"name": "📌 상태", "value": "정상 가동 준비 완료", "inline": True},
            ],
            "footer": {
                "text": "ICT Contest Bot • Connection Test",
            },
            "timestamp": get_current_kst_datetime().isoformat(),
        }

        payload = {
            "username": "ICT 공모전 알리미 [TEST]",
            "embeds": [embed],
        }

        return self._post_payload(payload, dry_run=False)
