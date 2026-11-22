"""Optional free-tier Gemini review of already collected contest notices."""
from __future__ import annotations

import json
import logging
from typing import List

import requests

from src.collectors.gemini_search import extract_json_array
from src.config import config
from src.models import Contest

logger = logging.getLogger(__name__)
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"
EXCLUSION_REASONS = {"education", "creative", "non_contest", "ineligible", "non_technical"}


class GeminiRefiner:
    """Reject only clearly evidenced mistakes; uncertain or failed reviews keep candidates."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or config.gemini_api_key
        self.model = model or config.gemini_refine_model

    def _review_batch(self, contests: List[Contest]) -> List[Contest]:
        fields = [
            {"id": c.id, "title": c.title, "target": c.target,
             "category": c.category, "description": (c.description or "")[:400]}
            for c in contests
        ]
        prompt = (
            "다음은 공개 공모전 사이트에서 수집하고 날짜·참가자격 키워드 검사를 통과한 후보입니다. "
            "기술 공모전/해커톤이 아닌 것이 명백할 때만 exclude 하세요. "
            "교육·채용·광고/영상 제작·비기술 행사·참가자격 불일치를 살피세요. "
            "확신이 없으면 uncertain으로 답하세요. 근거는 제공된 텍스트에서 그대로 짧게 인용하세요. "
            "외부 검색이나 추측은 하지 마세요. "
            "JSON 배열만 출력: [{\"id\":\"...\",\"decision\":\"include|exclude|uncertain\","
            "\"reason\":\"education|creative|non_contest|ineligible|non_technical|none\","
            "\"evidence\":\"원문 구절\"}].\n"
            + json.dumps(fields, ensure_ascii=False)
        )
        try:
            response = requests.post(
                API_URL.format(self.model),
                headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
                json={"contents": [{"parts": [{"text": prompt}]}],
                      "generationConfig": {"temperature": 0, "responseMimeType": "application/json"}},
                timeout=config.request_timeout,
            )
            response.raise_for_status()
            parts = response.json()["candidates"][0]["content"]["parts"]
            decisions = extract_json_array("".join(part.get("text", "") for part in parts))
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
            logger.warning("Gemini review unavailable; keeping %d candidates (%s).", len(contests), type(exc).__name__)
            return contests

        by_id = {item.get("id"): item for item in decisions if isinstance(item, dict)}
        kept = []
        for contest in contests:
            decision = by_id.get(contest.id, {})
            evidence = str(decision.get("evidence", "")).strip()
            source_text = f"{contest.title} {contest.target} {contest.category} {contest.description or ''}"
            exclude = (
                decision.get("decision") == "exclude"
                and decision.get("reason") in EXCLUSION_REASONS
                and len(evidence) >= 4
                and evidence.casefold() in source_text.casefold()
            )
            if exclude:
                logger.info("Gemini excluded '%s': %s", contest.title, decision.get("reason"))
            else:
                kept.append(contest)
        return kept

    def refine(self, contests: List[Contest]) -> List[Contest]:
        if not self.api_key or not contests:
            return contests
        kept = []
        for start in range(0, len(contests), 20):
            kept.extend(self._review_batch(contests[start:start + 20]))
        return kept
