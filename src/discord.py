"""Discord Webhook 발송 모듈 — 신규/마감 공고를 메시지 하나로 묶어서 전송."""
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

COLOR_NEW      = 0x5865F2   # Discord 보라
COLOR_DEADLINE = 0xED4245   # 마감 빨강
COLOR_D7       = 0xF1C40F   # D-7 노랑
COLOR_D3       = 0xE67E22   # D-3 주황
COLOR_D1       = 0xED4245   # D-1 빨강
COLOR_TEST     = 0x57F287   # 테스트 초록


class DiscordWebhookClient:
    def __init__(self, webhook_url: str, request_timeout: int = 15):
        self.webhook_url = webhook_url.strip() if webhook_url else ""
        self.request_timeout = request_timeout

    # ------------------------------------------------------------------ #
    # 내부 HTTP 전송
    # ------------------------------------------------------------------ #
    def _post_payload(self, payload: Dict[str, Any], dry_run: bool = False) -> Tuple[bool, str]:
        if dry_run:
            title = payload.get("embeds", [{}])[0].get("title", "")
            logger.info("[DRY-RUN] 발송 생략: %s", title)
            return True, "DRY_RUN_OK"

        if not self.webhook_url:
            return False, "DISCORD_WEBHOOK_URL 미설정"

        try:
            if requests:
                resp = requests.post(
                    self.webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=self.request_timeout,
                )
                if resp.status_code == 429:
                    wait = float(resp.json().get("retry_after", 2.0))
                    logger.warning("Discord rate limit — %s초 대기", wait)
                    time.sleep(wait)
                    resp = requests.post(
                        self.webhook_url,
                        json=payload,
                        headers={"Content-Type": "application/json"},
                        timeout=self.request_timeout,
                    )
                return (resp.status_code in (200, 204)), f"HTTP {resp.status_code}"
            else:
                data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                req = urllib.request.Request(
                    self.webhook_url, data=data,
                    headers={"Content-Type": "application/json", "User-Agent": "ICTContestBot/1.0"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=self.request_timeout) as r:
                    return r.status in (200, 204), f"HTTP {r.status}"
        except urllib.error.HTTPError as e:
            return False, f"HTTP {e.code}: {e.reason}"
        except Exception as e:
            logger.error("Discord 전송 오류: %s", e)
            return False, str(e)

    # ------------------------------------------------------------------ #
    # 신규 공고 — 한 메시지로 묶기
    # ------------------------------------------------------------------ #
    def send_new_contests_batch(self, contests: List[Contest], dry_run: bool = False) -> Tuple[bool, str]:
        """신규 공고 여러 개를 임베드 하나에 묶어서 발송."""
        if not contests:
            return True, "NO_NEW"

        today = get_current_kst_date()
        lines = []
        for c in contests:
            if c.apply_end:
                deadline = f"~{c.apply_end[5:7]}/{c.apply_end[8:10]}"
            else:
                deadline = "마감일 미확인"
            name = f"[{c.title}]({c.url})" if c.url else c.title
            org  = c.organizer or "주최 미확인"
            lines.append(f"• {name}\n  {org} | {deadline}")

        desc = "\n\n".join(lines)
        # Discord embed description 최대 4096자
        if len(desc) > 3800:
            desc = desc[:3800] + "\n\n… (더 보기: Wevity/씽굿/공모전코리아)"

        embed = {
            "title": f"📢 신규 공모전 {len(contests)}개",
            "description": desc,
            "color": COLOR_NEW,
            "footer": {
                "text": f"ICT Contest Bot  |  {get_current_kst_datetime().strftime('%Y-%m-%d %H:%M KST')}"
            },
        }
        payload = {"username": "ICT 공모전 봇", "embeds": [embed]}
        return self._post_payload(payload, dry_run=dry_run)

    # ------------------------------------------------------------------ #
    # 마감 임박 — 한 메시지로 묶기
    # ------------------------------------------------------------------ #
    def send_deadline_alerts_batch(
        self,
        alerts: List[Tuple[Contest, str]],   # [(contest, stage), ...]
        dry_run: bool = False,
    ) -> Tuple[bool, str]:
        """D-7/D-3/D-1 마감 임박 공고 여러 개를 임베드 하나에 묶어서 발송."""
        if not alerts:
            return True, "NO_ALERTS"

        ICON = {"D-7": "🟡", "D-3": "🟠", "D-1": "🔴"}
        lines = []
        for contest, stage in alerts:
            icon = ICON.get(stage, "⚠️")
            deadline = f"{contest.apply_end[5:7]}/{contest.apply_end[8:10]}" if contest.apply_end else "?"
            name = f"[{contest.title}]({contest.url})" if contest.url else contest.title
            org  = contest.organizer or "주최 미확인"
            lines.append(f"{icon} **{stage}** | {name}\n  {org} | ~{deadline}")

        desc = "\n\n".join(lines)
        if len(desc) > 3800:
            desc = desc[:3800] + "\n…"

        # 가장 급한 단계로 색상 결정
        stages = [s for _, s in alerts]
        if "D-1" in stages:
            color = COLOR_D1
        elif "D-3" in stages:
            color = COLOR_D3
        else:
            color = COLOR_D7

        embed = {
            "title": f"⏰ 마감 임박 {len(alerts)}개",
            "description": desc,
            "color": color,
            "footer": {
                "text": f"ICT Contest Bot  |  {get_current_kst_datetime().strftime('%Y-%m-%d %H:%M KST')}"
            },
        }
        payload = {"username": "ICT 공모전 봇", "embeds": [embed]}
        return self._post_payload(payload, dry_run=dry_run)

    def send_digest(
        self,
        announcements: List[Tuple[Contest, str]],
        dry_run: bool = False,
    ) -> Tuple[bool, str, List[Tuple[Contest, str]]]:
        """Send one deadline-ordered message and return only the alerts it contains."""
        if not announcements:
            return True, "NO_ALERTS", []

        today = get_current_kst_date()

        def sort_key(item: Tuple[Contest, str]) -> Tuple[str, str]:
            contest, _ = item
            try:
                deadline = datetime.strptime(contest.apply_end or "", "%Y-%m-%d").date()
                return deadline.isoformat(), contest.title
            except ValueError:
                return "9999-12-31", contest.title

        ordered = sorted(announcements, key=sort_key)
        chunks: List[str] = [""]
        included: List[Tuple[Contest, str]] = []
        # Discord permits up to 4096 characters per embed and 6000 total.
        max_chunk = 3400
        max_total = 5400
        for contest, stage in ordered:
            days_left = contest.days_until_deadline(today)
            deadline = contest.apply_end.replace("-", ".") if contest.apply_end else "마감일 미확인"
            d_day = (f"D-{days_left}" if days_left is not None and days_left > 0
                     else "오늘 마감" if days_left == 0 else "")
            label = "🆕" if stage == "NEW" else "⏰" if stage != "ONGOING" else "•"
            name = contest.title.replace("\n", " ").replace("\r", " ")[:120]
            if contest.url:
                name = f"[{name}]({contest.url})"
            line = f"{label} **{len(included) + 1}. {name}**\n마감 **{deadline}"
            if d_day:
                line += f" · {d_day}"
            line += "**"
            organizer = (contest.organizer or "주최 미확인").replace("\n", " ")[:65]
            target = (contest.target or "대상 미확인").replace("\n", " ")[:55]
            line += f" · 주최 {organizer}\n대상 {target}"
            category = (contest.category or "").replace("\n", " ")[:65]
            if category and category not in ("웹/모바일/IT", "ICT / SW / AI"):
                line += f" · 분야 {category}"
            entry = line + "\n\n"
            if sum(map(len, chunks)) + len(entry) + 80 > max_total:
                break
            if len(chunks[-1]) + len(entry) > max_chunk:
                if len(chunks) == 2:
                    break
                chunks.append("")
            chunks[-1] += entry
            included.append((contest, stage))

        if not included:
            return False, "첫 공고가 Discord 메시지 길이 제한을 초과했습니다.", []

        omitted = len(ordered) - len(included)
        if omitted:
            chunks[-1] += f"… 외 {omitted}건 (Discord 길이 제한)"
        embeds = []
        for index, description in enumerate(chunks):
            embeds.append({
                "title": (f"📋 진행 중인 ICT 공모전 · {len(included)}건" if index == 0 else "📋 계속"),
                "description": description.rstrip(),
                "color": COLOR_D1 if any(stage == "D-1" for _, stage in included) else COLOR_NEW,
                "footer": {"text": f"마감일순 · {get_current_kst_datetime().strftime('%Y-%m-%d %H:%M KST')}"},
            })
        payload = {"username": "ICT 공모전 봇", "embeds": embeds, "allowed_mentions": {"parse": []}}
        success, message = self._post_payload(payload, dry_run=dry_run)
        return success, message, included if success else []

    # ------------------------------------------------------------------ #
    # 테스트 메시지
    # ------------------------------------------------------------------ #
    def send_test_message(self) -> Tuple[bool, str]:
        if not self.webhook_url:
            return False, "DISCORD_WEBHOOK_URL 환경변수가 설정되지 않았습니다."

        now = get_current_kst_datetime().strftime("%Y-%m-%d %H:%M:%S KST")
        embed = {
            "title": "✅ ICT Contest Bot — 연결 테스트 성공",
            "description": (
                "Discord Webhook 연결이 정상적으로 확인됐음.\n"
                "매일 오전 9:17 KST에 신규 공고와 마감 임박 알림을 자동으로 발송함."
            ),
            "color": COLOR_TEST,
            "fields": [
                {"name": "⏱ 테스트 시각", "value": now, "inline": True},
                {"name": "🎯 대상 공모전", "value": "해커톤 / AI / SW / 데이터 / IoT / 로봇", "inline": True},
                {"name": "📡 수집 경로", "value": "Wevity · DAKER · Gemini 검색(API 키 설정 시)", "inline": False},
            ],
            "footer": {"text": "ICT Contest Bot — Connection Test"},
        }
        payload = {"username": "ICT 공모전 봇 [TEST]", "embeds": [embed]}
        return self._post_payload(payload, dry_run=False)
