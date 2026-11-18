"""Deadline calculation and KST timezone utilities."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Tuple

try:
    from zoneinfo import ZoneInfo
    KST = ZoneInfo("Asia/Seoul")
    # Quick probe to verify Windows IANA tzdata is available
    datetime.now(KST)
except Exception:
    # Standard library fallback for systems without IANA tzdata
    KST = timezone(timedelta(hours=9))


def get_current_kst_datetime() -> datetime:
    """Return the current datetime in Asia/Seoul (KST)."""
    return datetime.now(KST)


def get_current_kst_date() -> date:
    """Return the current date in Asia/Seoul (KST)."""
    return datetime.now(KST).date()


def parse_date(date_str: Optional[str]) -> Optional[str]:
    """
    Parse a date string into standard YYYY-MM-DD format.
    Strictly follows requirement: If date cannot be verified with confidence, return None.
    Do NOT guess missing months or days.
    """
    if not date_str or not isinstance(date_str, str):
        return None

    cleaned = date_str.strip()
    if not cleaned or any(kw in cleaned for kw in ("미정", "미확인", "추후", "상시", "별도", "참조")):
        return None

    # Try matching YYYY-MM-DD or YYYY.MM.DD or YYYY/MM/DD
    match = re.search(r"(\d{4})[\.\-/](\d{1,2})[\.\-/](\d{1,2})", cleaned)
    if match:
        year, month, day = match.groups()
        try:
            parsed = date(int(year), int(month), int(day))
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            return None

    # Try matching YY.MM.DD (e.g. 26.11.30 -> 2026-11-30)
    match_short = re.search(r"\b(\d{2})[\.\-/](\d{1,2})[\.\-/](\d{1,2})\b", cleaned)
    if match_short:
        year_short, month, day = match_short.groups()
        year = int(year_short) + 2000
        try:
            parsed = date(year, int(month), int(day))
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            return None

    return None


def parse_date_range(period_str: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract (start_date, end_date) from period strings like:
    '2026-10-20 ~ 2026-12-20' or '2026.11.01(금) - 2026.11.25(화)'
    """
    if not period_str:
        return None, None

    # Split on range separators (~, ～, —, –, or space-padded hyphen)
    # Avoid splitting on hyphens inside YYYY-MM-DD
    parts = re.split(r"\s*[~～—–]\s*|\s+-\s+", period_str.strip())
    if len(parts) >= 2:
        start = parse_date(parts[0])
        end = parse_date(parts[1])
        return start, end
    elif len(parts) == 1:
        # If only one date is mentioned, check if it's explicitly marked as deadline
        end = parse_date(parts[0])
        return None, end

    return None, None


def get_due_alert_stage(
    apply_end_str: Optional[str],
    alert_history: List[str],
    alert_days: Optional[List[int]] = None,
    today_kst: Optional[date] = None,
) -> Optional[str]:
    """
    Check if a deadline alert (e.g. D-7, D-3, D-1) is due today.
    Returns the stage string (e.g. 'D-7') if due and not yet sent, else None.
    Prevents duplicate alerts for the same stage.
    """
    if not apply_end_str:
        return None

    if alert_days is None:
        alert_days = [7, 3, 1]

    today = today_kst or get_current_kst_date()
    end_date_str = parse_date(apply_end_str)
    if not end_date_str:
        return None

    try:
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    except ValueError:
        return None

    days_left = (end_date - today).days

    if days_left < 0:
        # Already expired
        return None

    for target_day in alert_days:
        stage = f"D-{target_day}"
        if days_left == target_day:
            if stage not in alert_history:
                return stage
            return None

    return None
