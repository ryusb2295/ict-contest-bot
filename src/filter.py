"""Filtering logic for contest relevance and university student eligibility."""
from __future__ import annotations

import re
from datetime import date
from typing import Optional, Tuple

from src.deadline import get_current_kst_date, parse_date

# Target fields for Information & Communication / Computer Science students
# Korean keywords (substring match)
ICT_KOREAN_KEYWORDS = [
    "해커톤", "인공지능", "머신러닝", "딥러닝", "생성형",
    "빅데이터", "데이터분석", "데이터 분석", "데이터사이언스",
    "소프트웨어", "정보통신", "사물인터넷", "임베디드",
    "로봇", "드론", "자율주행", "정보보호", "해킹",
    "알고리즘", "코딩", "프로그래밍", "메타버스",
    "클라우드", "웹", "앱", "서비스 개발", "sw",
]

# Short English keywords / acronyms (strict word boundary match)
ICT_ENGLISH_PATTERNS = [
    r"\bhackathon\b", r"\bai\b", r"\bsw\b", r"\bict\b", r"\biot\b",
    r"\bdata\b", r"\bml\b", r"\bllm\b", r"\bweb\b", r"\bapp\b",
    r"\bcloud\b", r"\bdevops\b", r"\bsecurity\b", r"\bctf\b",
    r"\bvr\b", r"\bar\b", r"\bxr\b", r"\brobot\b", r"\brobotics\b",
    r"\bsoftware\b", r"\bdeep learning\b", r"\bmachine learning\b",
]

# Irrelevant non-technical fields to exclude
EXCLUDE_KEYWORDS = [
    "포스터 공모전", "로고 공모전", "캐릭터 디자인", "캐릭터 공모전",
    "슬로건 공모전", "네이밍 공모전", "표어 공모전",
    "수필", "시 공모전", "시 짓기", "백일장", "글짓기", "독후감",
    "UCC 영상", "숏폼 영상", "브이로그", "사진전", "사진 공모전",
    "가요제", "댄스", "음악 경연", "노래자랑",
    "영화제", "영화 공모전", "단편영화", "시나리오", "웹툰 공모전", "만화 공모전",
]

# Positive eligibility keywords for domestic university students
ELIGIBLE_TARGET_KEYWORDS = [
    "대학생", "대학(원)생", "학부생", "청년", "일반인", "누구나", "제한없음",
    "전국민", "국내 거주", "예비창업자", "스타트업", "학생",
]

# Ineligible keywords (strictly restricted away from university students)
INELIGIBLE_TARGET_KEYWORDS = [
    "초등학생 전용", "중학생 전용", "고등학생만", "초등학생만", "중학생만",
    "어린이 전용", "만 65세", "시니어 전용", "재직자 한정", "군인 한정",
]


def is_relevant_major(title: str, category: str = "", description: str = "") -> bool:
    """Check if the contest is relevant to ICT, CS, AI, SW, IoT, or Robotics."""
    combined_text = f"{title} {category} {description}".lower()

    # Reject if it matches purely excluded non-technical themes
    for exclude_word in EXCLUDE_KEYWORDS:
        if exclude_word.lower() in combined_text:
            # Check if there is an explicit technical override (e.g. 'AI 영상 공모전' or 'SW 알고리즘')
            has_tech_override = any(k in title.lower() for k in ["인공지능", "소프트웨어", "알고리즘", "해커톤"]) or \
                                any(re.search(p, title.lower()) for p in [r"\bai\b", r"\bsw\b"])
            if not has_tech_override:
                return False

    # Check Korean keywords
    if any(k in combined_text for k in ICT_KOREAN_KEYWORDS):
        return True

    # Check English word boundary patterns
    if any(re.search(pattern, combined_text) for pattern in ICT_ENGLISH_PATTERNS):
        return True

    return False


def is_eligible_student(target: str) -> bool:
    """Check if domestic university students are eligible to participate."""
    if not target or target.strip() in ("", "미확인 / 상세 공고 참조"):
        # If unspecified in summary, allow passage so official URL can be checked
        return True

    target_lower = target.lower()

    # If it contains any strictly ineligible terms, reject
    if any(ineligible in target_lower for ineligible in INELIGIBLE_TARGET_KEYWORDS):
        return False

    # Check for positive eligibility words
    if any(eligible in target_lower for eligible in ELIGIBLE_TARGET_KEYWORDS):
        return True

    # If target mentions '학생' but not '초등/중등/고등 전용', default to True
    if "학생" in target_lower:
        return True

    return False


def is_not_expired(apply_end_str: Optional[str], today: Optional[date] = None) -> bool:
    """Check if the contest deadline has not passed yet."""
    if not apply_end_str:
        return True  # If unknown, keep for verification

    today_kst = today or get_current_kst_date()
    parsed_end = parse_date(apply_end_str)
    if not parsed_end:
        return True

    from datetime import datetime
    try:
        end_date = datetime.strptime(parsed_end, "%Y-%m-%d").date()
        return end_date >= today_kst
    except ValueError:
        return True


def filter_contest(
    title: str,
    target: str = "",
    category: str = "",
    description: str = "",
    apply_end: Optional[str] = None,
    today: Optional[date] = None,
) -> Tuple[bool, str]:
    """
    Run full validation on a contest candidate.
    Returns (is_valid, reason).
    """
    if not is_not_expired(apply_end, today):
        return False, "마감일 경과 (이미 종료된 공고)"

    if not is_relevant_major(title, category, description):
        return False, "ICT/SW/AI/컴퓨터공학 관련 분야 아님"

    if not is_eligible_student(target):
        return False, "대학생 참가 대상 아님 (초/중/고 전용 또는 특정 연령 제한)"

    return True, "유효한 대학생 참가 가능 공고"
