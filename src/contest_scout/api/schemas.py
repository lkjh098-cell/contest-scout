"""요청 본문 스키마.

응답은 :mod:`contest_scout.repository` 가 만든 dict를 그대로 내보낸다. 같은 모양을
두 군데에 적어두면 반드시 어긋나기 때문이다.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from contest_scout.models import ContestStatus

#: 사용자가 익숙한 이름 → DB에 저장된 상태값.
STATUS_ALIASES = {
    "SHORTLISTED": ContestStatus.INTERESTED.value,
    "SHORTLIST": ContestStatus.INTERESTED.value,
}


class StatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def _normalize(cls, value: str) -> str:
        upper = value.strip().upper()
        upper = STATUS_ALIASES.get(upper, upper)
        if upper not in ContestStatus.choices():
            raise ValueError(
                f"알 수 없는 상태입니다: {value} (가능한 값: {', '.join(ContestStatus.choices())})"
            )
        return upper


class ScoutRunRequest(BaseModel):
    sources: list[str] | None = None
    pages: int | None = Field(default=None, ge=1, le=10)
    limit: int | None = Field(default=None, ge=1, le=200)


class CrawlSettingsPatch(BaseModel):
    delay: float | None = Field(default=None, ge=0.5, le=30)
    timeout: float | None = Field(default=None, ge=5, le=120)
    pages: int | None = Field(default=None, ge=1, le=10)
    limit: int | None = Field(default=None, ge=1, le=200)
    respect_robots: bool | None = None
    user_agent: str | None = None


class SchedulePatch(BaseModel):
    enabled: bool | None = None
    time: str | None = None

    @field_validator("time")
    @classmethod
    def _check_time(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parts = value.split(":")
        if len(parts) != 2 or not all(p.isdigit() for p in parts):
            raise ValueError("시각은 HH:MM 형식이어야 합니다")
        hour, minute = int(parts[0]), int(parts[1])
        if not (0 <= hour < 24 and 0 <= minute < 60):
            raise ValueError("시각 범위를 벗어났습니다")
        return f"{hour:02d}:{minute:02d}"


class ProfilePatch(BaseModel):
    weights: dict[str, int] | None = None
    strong_keywords: list[str] | None = None
    preferred_keywords: list[str] | None = None
    negative_keywords: list[str] | None = None
    tier_thresholds: dict[str, int] | None = None
    min_days_left: int | None = Field(default=None, ge=0, le=60)
    strong_prize_krw: int | None = Field(default=None, ge=0)
    good_prize_krw: int | None = Field(default=None, ge=0)


class SettingsPatch(BaseModel):
    crawl: CrawlSettingsPatch | None = None
    schedule: SchedulePatch | None = None
    enabled_sources: list[str] | None = None
    profile: ProfilePatch | None = None


class ProjectCreate(BaseModel):
    contest_key: str


class ProjectPatch(BaseModel):
    stage: str | None = None
    next_action: str | None = None


class ApiError(BaseModel):
    detail: str
    hint: str | None = None
    technical: Any | None = None


__all__ = [
    "ApiError",
    "CrawlSettingsPatch",
    "ProfilePatch",
    "ProjectCreate",
    "ProjectPatch",
    "SchedulePatch",
    "ScoutRunRequest",
    "SettingsPatch",
    "StatusUpdate",
]
