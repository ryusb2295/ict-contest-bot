#!/usr/bin/env python3
"""
Main CLI entrypoint for ICT Contest Discord Bot.
Supports --test-webhook and --dry-run modes.
"""
from __future__ import annotations

import argparse
import logging
import sys

from src.bot import ContestBot
from src.config import config
from src.discord import DiscordWebhookClient


def setup_logging(verbose: bool = False) -> None:
    """Configure console logging format and level."""
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def handle_test_webhook() -> int:
    """Send a test message to the configured Discord webhook."""
    print("=" * 60)
    print(" [ICT Contest Bot] Discord Webhook 연결 테스트")
    print("=" * 60)

    if not config.has_webhook:
        print("[오류] DISCORD_WEBHOOK_URL 환경변수가 설정되지 않았습니다.")
        print("설정 방법:")
        print(" 1. Discord 채널 설정 > 연동 > 웹후크 생성 > 웹후크 URL 복사")
        print(" 2. .env 파일에 DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/... 추가")
        print(" 3. GitHub Actions의 경우 Repository Secrets에 DISCORD_WEBHOOK_URL 등록")
        return 0

    client = DiscordWebhookClient(webhook_url=config.discord_webhook_url)
    print(f"웹후크 대상: {config.discord_webhook_url[:35]}...")
    print("테스트 Embed 메시지 전송 중...")

    success, message = client.send_test_message()
    if success:
        print(">> [성공] Discord 채널에 테스트 메시지가 정상적으로 발송되었습니다!")
        print(">> Discord 채널을 확인해보세요.")
    else:
        print(f">> [실패] 웹후크 전송 실패: {message}")
        print(">> 웹후크 URL이 올바른지, 채널 권한이 유효한지 확인하세요.")

    return 0


def main() -> int:
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="ICT Contest Discord Bot - Information & Communication / CS Contest Alert System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--test-webhook",
        action="store_true",
        help="Discord Webhook으로 테스트 메시지를 발송하여 연결 상태를 점검합니다.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실제 Discord 전송 및 contests.json 저장을 하지 않고 수집/필터링/알림 시뮬레이션을 수행합니다.",
    )
    parser.add_argument(
        "--send-test-digest",
        action="store_true",
        help="오늘 요약을 이미 보냈어도 수정된 공모전 요약을 하루 한 번 추가로 테스트 발송합니다.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="상세 디버그 로그를 출력합니다.",
    )

    args = parser.parse_args()
    setup_logging(verbose=args.verbose)

    if args.test_webhook:
        return handle_test_webhook()

    print("=" * 60)
    print(f" [ICT Contest Bot] 시작 (Dry-Run: {args.dry_run})")
    print(f" - Gemini API 설정 여부: {'등록됨' if config.has_gemini else '미등록 (폴백 모드 동작)'}")
    print(f" - Discord Webhook 설정 여부: {'등록됨' if config.has_webhook else '미등록'}")
    print("=" * 60)

    try:
        bot = ContestBot()
        results = bot.run(dry_run=args.dry_run, send_test_digest=args.send_test_digest)

        print("\n" + "=" * 60)
        print(" [실행 결과 요약]")
        print(f" - 원본 수집 공고 수: {results['collected_raw']}건")
        print(f" - 전공/자격 검증 통과: {results['filtered_valid']}건")
        print(f" - 신규 발견 공고: {results['new_contests']}건")
        print(f" - 기존 갱신 공고: {results['updated_contests']}건")
        print(f" - 마감 임박 알림(D-7/3/1): {results['deadline_alerts']}건")
        print(f" - 누적 보관 공고 수: {results['total_stored']}건")
        if results.get("errors"):
            print(f" - 주의 사항: {len(results['errors'])}건 발생 (상세 로그 참조)")
        print("=" * 60)
        return 0

    except Exception as e:
        # Requirement 8: graceful exit even on unexpected exceptions
        logging.error("Unhandled error during bot execution: %s", e, exc_info=True)
        print(f"\n[알림] 오류가 발생했으나 시스템을 안전하게 정상 종료합니다: {e}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
