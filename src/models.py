"""Data models for contests and alerts."""
from __future__ import annotations

import hashlib
import re
from datetime import date, datetime
from typing import List, Optional
from urllib.parse import urlparse, urlunparse

try:
    from pydantic import BaseModel, Field
except ImportError:
    # Pure Python fallback when Pydantic is not installed
    class BaseModel:
        def __init__(self, **kwargs):
            # Apply class default fields first
            for k, v in self.__class__.__dict__.items():
                if not k.startswith("_") and not callable(v) and not isinstance(v, (classmethod, staticmethod)):
                    setattr(self, k, v)
            # Apply provided kwargs
            for k, v in kwargs.items():
                setattr(self, k, v)

        def model_dump(self) -> dict:
            return {
                k: v for k, v in self.__dict__.items()
                if not k.startswith("_") and not callable(v) and not isinstance(v, (classmethod, staticmethod))
            }

    def Field(default=None, default_factory=None, description=""):
        if default_factory is not None:
            return default_factory()
        return default


def normalize_url(url: str) -> str:
    """Normalize URL by stripping tracking parameters, trailing slashes, and fragments."""
    if not url:
        return ""
    try:
        parsed = urlparse(url.strip())
        path = parsed.path.rstrip("/")
        # Keep query parameters that look essential (e.g. id, ix, cidx), drop utm_
        query = parsed.query
        if query:
            filtered_params = [
                p for p in query.split("&")
                if not any(p.lower().startswith(prefix) for prefix in ("utm_", "fbclid=", "ref="))
            ]
            query = "&".join(filtered_params)
        normalized = urlunparse((
            parsed.scheme.lower() or "https",
            parsed.netloc.lower(),
            path,
            parsed.params,
            query,
            "",  # drop fragment
        ))
        return normalized
    except Exception:
        return url.strip()


def normalize_title(title: str) -> str:
    """Normalize contest title for deduplication."""
    if not title:
        return ""
    # Keep bracketed event names; only remove status labels.
    cleaned = re.sub(r"\[(?:접수중|모집중|진행중|마감임박|공고|안내|D-?\d+)\]", " ", title, flags=re.IGNORECASE)
    # Remove special characters and excessive whitespace
    cleaned = re.sub(r"[^\w\s가-힣]", " ", cleaned)
    return " ".join(cleaned.split()).lower()


class Contest(BaseModel):
    """Represents a contest announcement."""

    id: str = Field(description="Unique identifier (deterministic hash)")
    title: str = Field(description="공고명")
    organizer: str = Field(default="미확인 / 상세 공고 참조", description="주최/주관 기관")
    category: str = Field(default="ICT / SW / AI", description="공모 분야")
    target: str = Field(default="미확인 / 상세 공고 참조", description="참가 자격")
    apply_start: Optional[str] = Field(default=None, description="접수 시작일 (YYYY-MM-DD) 또는 None")
    apply_end: Optional[str] = Field(default=None, description="접수 마감일 (YYYY-MM-DD) 또는 None")
    event_date: Optional[str] = Field(default=None, description="행사/대회일 또는 None")
    url: str = Field(description="공식 공고 URL 또는 상세 링크")
    description: Optional[str] = Field(default="", description="공고 간략 요약")
    source: str = Field(default="unknown", description="수집 출처")
    status: str = Field(default="ACTIVE", description="ACTIVE 또는 CLOSED")
    discovered_at: str = Field(description="발견 일시 (ISO 8601)")
    last_alert_at: Optional[str] = Field(default=None, description="최근 알림 일시")
    alert_history: List[str] = Field(default_factory=list, description="발송된 알림 단계 목록 (예: ['NEW', 'D-7'])")

    @classmethod
    def create(
        cls,
        title: str,
        url: str,
        organizer: Optional[str] = None,
        category: Optional[str] = None,
        target: Optional[str] = None,
        apply_start: Optional[str] = None,
        apply_end: Optional[str] = None,
        event_date: Optional[str] = None,
        description: Optional[str] = None,
        source: str = "unknown",
        discovered_at: Optional[str] = None,
    ) -> Contest:
        """Create a new Contest instance with automatic ID generation."""
        clean_url = normalize_url(url)
        clean_title = title.strip()
        contest_id = cls.generate_id(clean_url, clean_title)

        now_str = discovered_at or datetime.now().isoformat()

        return cls(
            id=contest_id,
            title=clean_title,
            organizer=(organizer or "").strip() or "미확인 / 상세 공고 참조",
            category=(category or "").strip() or "ICT / SW / AI",
            target=(target or "").strip() or "미확인 / 상세 공고 참조",
            apply_start=apply_start,
            apply_end=apply_end,
            event_date=event_date,
            url=clean_url or url.strip(),
            description=(description or "").strip(),
            source=source,
            status="ACTIVE",
            discovered_at=now_str,
            alert_history=[],
        )

    @staticmethod
    def generate_id(url: str, title: str) -> str:
        """Generate a deterministic 16-char SHA-256 hash for deduplication."""
        norm_url = normalize_url(url)
        norm_title = normalize_title(title)
        key = f"{norm_url}::{norm_title}".encode("utf-8")
        return hashlib.sha256(key).hexdigest()[:16]

    def days_until_deadline(self, today: date) -> Optional[int]:
        """Calculate days remaining until apply_end date (KST)."""
        if not self.apply_end:
            return None
        try:
            end_date = datetime.strptime(self.apply_end, "%Y-%m-%d").date()
            return (end_date - today).days
        except ValueError:
            return None

    def get_d_day_label(self, today: date) -> str:
        """Return human-readable D-Day string (e.g. 'D-7', 'D-Day', '마감 완료')."""
        days = self.days_until_deadline(today)
        if days is None:
            return "일정 미확인 (상세 공고 참조)"
        if days > 0:
            return f"D-{days}"
        elif days == 0:
            return "D-Day (오늘 마감!)"
        else:
            return f"마감 완료 (D+{abs(days)})"

    def has_alert_sent(self, stage: str) -> bool:
        """Check if a specific alert stage has already been sent."""
        return stage in self.alert_history

    def record_alert(self, stage: str, alert_time: Optional[str] = None) -> None:
        """Record that an alert stage has been sent."""
        if stage not in self.alert_history:
            self.alert_history.append(stage)
        self.last_alert_at = alert_time or datetime.now().isoformat()
