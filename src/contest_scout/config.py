"""사용자 프로필 / 평가 설정 로딩.

``config/profile.json`` 이 있으면 그것을, 없으면 패키지에 동봉된 기본 프로필을
쓴다. 덕분에 어느 디렉터리에서 실행해도 CLI가 죽지 않는다.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

DEFAULT_PROFILE_PATHS = (
    Path("config/profile.json"),
    Path.home() / ".config" / "contest-scout" / "profile.json",
)


@dataclass(slots=True)
class Profile:
    weights: dict[str, int]
    preferred_keywords: list[str]
    strong_keywords: list[str]
    negative_keywords: list[str]
    solo_blocker_keywords: list[str]
    open_eligibility_terms: list[str]
    youth_only_terms: list[str]
    region_restricted_terms: list[str]
    trusted_organizer_keywords: list[str]
    min_days_left: int
    strong_prize_krw: int
    good_prize_krw: int
    tier_thresholds: dict[str, int]
    source_path: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def max_score(self) -> int:
        return sum(self.weights.values())

    def tier_for(self, total: int) -> str:
        if total >= self.tier_thresholds.get("S", 85):
            return "S"
        if total >= self.tier_thresholds.get("A", 75):
            return "A"
        if total >= self.tier_thresholds.get("B", 60):
            return "B"
        return "SKIP"


def _default_profile_dict() -> dict[str, Any]:
    raw = resources.files("contest_scout").joinpath("default_profile.json").read_text("utf-8")
    return json.loads(raw)


def load_profile(path: str | Path | None = None) -> Profile:
    data = _default_profile_dict()
    used: str | None = None

    candidates = [Path(path)] if path else list(DEFAULT_PROFILE_PATHS)
    for candidate in candidates:
        if candidate.is_file():
            try:
                user_data = json.loads(candidate.read_text("utf-8"))
            except json.JSONDecodeError as exc:
                raise ValueError(f"프로필 JSON 파싱 실패: {candidate} ({exc})") from exc
            data.update(user_data)
            used = str(candidate)
            break
    else:
        if path:
            raise FileNotFoundError(f"프로필 파일을 찾을 수 없습니다: {path}")

    known = {
        "weights",
        "preferred_keywords",
        "strong_keywords",
        "negative_keywords",
        "solo_blocker_keywords",
        "open_eligibility_terms",
        "youth_only_terms",
        "region_restricted_terms",
        "trusted_organizer_keywords",
        "min_days_left",
        "strong_prize_krw",
        "good_prize_krw",
        "tier_thresholds",
    }
    # "_comment_*" 같은 주석 키는 무시한다.
    return Profile(
        weights=data["weights"],
        preferred_keywords=data["preferred_keywords"],
        strong_keywords=data["strong_keywords"],
        negative_keywords=data["negative_keywords"],
        solo_blocker_keywords=data["solo_blocker_keywords"],
        open_eligibility_terms=data["open_eligibility_terms"],
        youth_only_terms=data["youth_only_terms"],
        region_restricted_terms=data["region_restricted_terms"],
        trusted_organizer_keywords=data["trusted_organizer_keywords"],
        min_days_left=data["min_days_left"],
        strong_prize_krw=data["strong_prize_krw"],
        good_prize_krw=data["good_prize_krw"],
        tier_thresholds=data["tier_thresholds"],
        source_path=used,
        extra={k: v for k, v in data.items() if k not in known},
    )
