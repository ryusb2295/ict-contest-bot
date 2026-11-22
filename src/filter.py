"""Filtering logic for contest relevance and university student eligibility."""
from __future__ import annotations

import re
from datetime import date
from typing import Optional, Tuple

from src.deadline import get_current_kst_date, parse_date

TECHNICAL_TERMS = (
    "소프트웨어", "정보통신", "통신", "임베디드", "사물인터넷", "정보보호",
    "사이버보안", "보안", "블록체인", "암호화", "알고리즘", "프로그래밍",
    "코딩", "클라우드", "네트워크", "로봇", "자율주행", "반도체",
    "회로", "전자공학", "머신러닝", "딥러닝", "대규모 언어모델",
    "데이터분석", "데이터 분석", "빅데이터", "데이터사이언스",
    "에이전트", "웹서비스 개발", "웹앱 개발", "앱 개발", "서비스 개발",
    "모델 개발", "모델링", "시스템 개발", "기술 개발", "가전",
)
TECHNICAL_ENGLISH = re.compile(
    r"(?<![a-z])(?:sw|ict|iot|llm|ctf|api|agent|blockchain|security|hackathon|embedded|robotics)(?![a-z])"
)
AI_PATTERN = re.compile(r"(?<![a-z])ai(?![a-z])|인공지능")
DATA_PATTERN = re.compile(r"데이터|(?<![a-z])data(?![a-z])")
TECHNICAL_TASK = re.compile(r"경진대회|해커톤|챌린지|개발|분석|활용|모델|벤치마크|시각화|아이디어|프롬프톤")
CREATIVE_TERMS = (
    "광고", "마케팅", "홍보", "포스터", "영화", "영상", "숏폼", "ucc",
    "브이로그", "사진", "그림", "미술", "웹툰", "만화", "캐릭터",
    "로고", "슬로건", "네이밍", "표어", "글짓기", "백일장", "수필",
    "시 공모전", "콘텐츠", "음악", "댄스", "e스포츠", "e-스포츠",
    "이스포츠", "꿀팁", "제작법",
)
NON_CONTEST_TITLE = re.compile(
    r"교육생\s*모집|수강생\s*모집|양성과정|국비지원|취업\s*컨설팅|"
    r"무료\s*강의|세미나\s*참가|교육과정\s*모집|아카데미\s*모집|"
    r"(?<![a-z])(?:bootcamp|training course)(?![a-z])",
    re.IGNORECASE,
)
TECHNICAL_OVERRIDE = re.compile(
    r"모델 개발|알고리즘 개발|소프트웨어 개발|서비스 개발|시스템 개발|"
    r"앱 개발|웹앱 개발|데이터 분석|데이터분석|임베디드|정보보호|보안 기술"
)

# Positive eligibility keywords for domestic university students
ELIGIBLE_TARGET_KEYWORDS = [
    "대학생", "대학원생", "대학(원)생", "학부생", "대학교 재학생", "대학 재학생",
    "대학교 휴학생", "대학 휴학생", "대학교 재·휴학생", "대학 재·휴학생",
    "누구나", "제한없음", "제한 없음", "전국민", "전 국민", "대한민국 국민",
    "청년", "일반인",
]

# Ineligible keywords (strictly restricted away from university students)
INELIGIBLE_TARGET_KEYWORDS = [
    "초등학생 전용", "중학생 전용", "고등학생만", "초등학생만", "중학생만",
    "어린이 전용", "만 65세", "시니어 전용", "재직자 한정", "군인 한정",
]


def is_relevant_major(title: str, category: str = "", description: str = "") -> bool:
    """Require a technical subject or deliverable, not merely use of an AI tool."""
    title_text = title.lower()
    detail_text = f"{title} {description}".lower()

    if NON_CONTEST_TITLE.search(title):
        return False
    if any(term in title_text for term in CREATIVE_TERMS) and not TECHNICAL_OVERRIDE.search(detail_text):
        return False
    if any(term in detail_text for term in TECHNICAL_TERMS):
        return True
    if TECHNICAL_ENGLISH.search(detail_text):
        return True
    if (AI_PATTERN.search(detail_text) or DATA_PATTERN.search(detail_text)) and TECHNICAL_TASK.search(detail_text):
        return True
    return False


def is_eligible_student(target: str) -> bool:
    """Require explicit student, youth, general public, or open-to-all eligibility."""
    if not target:
        return False

    target_lower = target.lower()

    # If it contains any strictly ineligible terms, reject
    if any(ineligible in target_lower for ineligible in INELIGIBLE_TARGET_KEYWORDS):
        return False

    # Check for positive eligibility words
    if any(eligible in target_lower for eligible in ELIGIBLE_TARGET_KEYWORDS):
        return True

    return False


def is_not_expired(apply_end_str: Optional[str], today: Optional[date] = None) -> bool:
    """Require a verified deadline that has not passed yet."""
    if not apply_end_str:
        return False

    today_kst = today or get_current_kst_date()
    parsed_end = parse_date(apply_end_str)
    if not parsed_end:
        return False

    from datetime import datetime
    try:
        end_date = datetime.strptime(parsed_end, "%Y-%m-%d").date()
        return end_date >= today_kst
    except ValueError:
        return False


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
    if not parse_date(apply_end):
        return False, "마감일 미확인"

    if not is_not_expired(apply_end, today):
        return False, "마감일 경과 (이미 종료된 공고)"

    if not is_relevant_major(title, category, description):
        return False, "ICT/SW/AI/컴퓨터공학 관련 분야 아님"

    if not is_eligible_student(target):
        return False, "대학생 참가 대상 아님 (초/중/고 전용 또는 특정 연령 제한)"

    return True, "유효한 대학생 참가 가능 공고"
