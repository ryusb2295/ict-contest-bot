"""Gemini Google Search Grounding collector using official google-genai SDK."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from src.collectors.base import BaseCollector
from src.config import config
from src.deadline import get_current_kst_date, get_current_kst_datetime, parse_date
from src.models import Contest

logger = logging.getLogger(__name__)


def extract_json_array(text: str) -> List[Dict[str, Any]]:
    """Extract a JSON array from model text response."""
    if not text:
        return []

    # 1. Try direct JSON parsing
    cleaned = text.strip()
    try:
        data = json.loads(cleaned)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            # Check for keys like 'contests' or 'items'
            for key in ("contests", "items", "competitions", "data"):
                if key in data and isinstance(data[key], list):
                    return data[key]
    except Exception:
        pass

    # 2. Extract from markdown code blocks: ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        block_text = match.group(1).strip()
        try:
            data = json.loads(block_text)
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                for key in ("contests", "items", "competitions", "data"):
                    if key in data and isinstance(data[key], list):
                        return data[key]
        except Exception:
            pass

    # 3. Search for bracket slice [ ... ]
    start_idx = text.find("[")
    end_idx = text.rfind("]")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        bracket_text = text[start_idx : end_idx + 1]
        try:
            data = json.loads(bracket_text)
            if isinstance(data, list):
                return data
        except Exception:
            pass

    return []


class GeminiSearchCollector(BaseCollector):
    """
    Collector utilizing Gemini API with Google Search Grounding to discover
    real active domestic hackathons, AI/SW competitions, and ICT contests.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self.api_key = api_key or config.gemini_api_key
        self.model_name = model_name or config.gemini_model

    def collect(self) -> List[Contest]:
        """Query Gemini with Google Search tool and parse response into Contest objects."""
        if not self.api_key:
            logger.info("GEMINI_API_KEY is not set. Skipping GeminiSearchCollector.")
            return []

        try:
            from google import genai
            from google.genai import types
        except ImportError:
            logger.error("google-genai SDK is not installed. Skipping GeminiSearchCollector.")
            return []

        today_kst = get_current_kst_date()
        today_str = today_kst.strftime("%Y년 %m월 %d일")
        now_iso = get_current_kst_datetime().isoformat()

        prompt = (
            f"오늘 기준일은 대한민국 표준시(KST) {today_str}입니다.\n"
            "대한민국 국내에서 대학생·청년·일반인이 참가할 수 있거나 국민 누구나 참여 가능한, 현재 접수 중인 최신 공모전을 Google 검색을 활용하여 조사해주세요.\n"
            "대상 분야: AI 모델·에이전트 개발, 소프트웨어·앱 개발, 데이터 분석, 임베디드·IoT·통신·보안·블록체인 경진대회.\n"
            "AI로 광고·포스터·영상·영화를 제작하는 공모전과 e스포츠 대회는 제외하세요.\n\n"
            "[필수 규칙]\n"
            "1. 국내 대학생·청년·일반인 또는 대한민국 국민 누구나 실제 참여 가능한 공고만 선별하세요.\n"
            "2. 이미 마감된 공고나 전공과 무관한(순수 디자인, 문학, 영상 등) 공고는 절대 제외하세요.\n"
            "3. 원문 근거로 확인되지 않은 날짜는 추측하지 말고 반드시 null로 처리하세요.\n"
            "4. 반드시 실제 접속 가능한 공식 웹사이트 URL(url)을 기재하세요.\n"
            "5. 반드시 아래 JSON 배열 형식으로만 응답하세요.\n\n"
            "```json\n"
            "[\n"
            "  {\n"
            '    "title": "공고명",\n'
            '    "organizer": "주최/주관 기관명",\n'
            '    "category": "AI / SW / 해커톤 등",\n'
            '    "target": "참가자격 (예: 전국 대학생, 제한없음)",\n'
            '    "apply_start": "YYYY-MM-DD 또는 null",\n'
            '    "apply_end": "YYYY-MM-DD 또는 null",\n'
            '    "event_date": "행사일(문자열) 또는 null",\n'
            '    "url": "https://공식공고URL",\n'
            '    "description": "공고 간략 요약 (1~2문장)"\n'
            "  }\n"
            "]\n"
            "```"
        )

        try:
            logger.info("Querying Gemini (%s) with Google Search Grounding...", self.model_name)
            client = genai.Client(api_key=self.api_key)

            # Attempt generate_content with Google Search tool
            response = client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=0.2,
                ),
            )

            response_text = response.text or ""
            items = extract_json_array(response_text)

            if not items:
                logger.warning("Gemini Search Grounding returned empty or unparseable JSON.")
                return []

            contests: List[Contest] = []
            for item in items:
                title = item.get("title")
                url = item.get("url")
                if not title or not url:
                    continue

                apply_start = parse_date(item.get("apply_start"))
                apply_end = parse_date(item.get("apply_end"))

                contest = Contest.create(
                    title=title,
                    url=url,
                    organizer=item.get("organizer"),
                    category=item.get("category"),
                    target=item.get("target"),
                    apply_start=apply_start,
                    apply_end=apply_end,
                    event_date=item.get("event_date"),
                    description=item.get("description"),
                    source="gemini_search",
                    discovered_at=now_iso,
                )
                contests.append(contest)

            logger.info("Gemini Search Grounding discovered %d contests.", len(contests))
            return contests

        except Exception as e:
            logger.warning(
                "Gemini Search Grounding failed or is restricted on this tier (%s). "
                "Activating fallback collector. Error details: %s",
                self.model_name,
                e,
            )
            return []
