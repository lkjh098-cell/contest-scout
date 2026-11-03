"""공통 데이터 모델.

사이트별 파서는 서로 다른 원본 구조를 읽지만, 최종적으로는 모두
:class:`Contest` 하나로 정규화된다.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Any


class ContestStatus(StrEnum):
    """사용자 관점의 공모전 상태 (수동 전환 + 자동 만료)."""

    NEW = "NEW"
    RECOMMENDED = "RECOMMENDED"
    INTERESTED = "INTERESTED"
    ENTERING = "ENTERING"
    SUBMITTED = "SUBMITTED"
    IGNORE = "IGNORE"
    EXPIRED = "EXPIRED"

    @classmethod
    def choices(cls) -> list[str]:
        return [s.value for s in cls]


#: 사용자가 직접 정한 상태. 자동 추천/자동 만료가 덮어써서는 안 된다.
USER_LOCKED_STATUSES = frozenset(
    {
        ContestStatus.INTERESTED,
        ContestStatus.ENTERING,
        ContestStatus.SUBMITTED,
        ContestStatus.IGNORE,
    }
)

#: 다시 추천하면 안 되는 상태.
SUPPRESSED_STATUSES = frozenset({ContestStatus.IGNORE, ContestStatus.EXPIRED})


@dataclass(slots=True)
class ContestRef:
    """목록 페이지에서 얻는 '싼' 식별 정보.

    Incremental crawl의 핵심: 이 단계에서 DB와 비교해 이미 아는 공모전이면
    상세 조회를 아예 하지 않는다. ``payload``에 이미 상세 정보가 들어 있는
    소스(씽굿)는 추가 요청 없이 그대로 정규화한다.
    """

    source: str
    source_id: str
    url: str
    title: str = ""
    payload: dict[str, Any] | None = None

    @property
    def key(self) -> str:
        return f"{self.source}:{self.source_id}"


@dataclass(slots=True)
class ParseWarning:
    """파싱 실패를 조용히 삼키지 않기 위한 구조화 경고."""

    source: str
    url: str
    field: str
    reason: str

    def __str__(self) -> str:
        return f"ParseWarning[{self.source}] field={self.field} reason={self.reason} url={self.url}"


@dataclass(slots=True)
class Contest:
    """정규화된 공모전 한 건."""

    source: str
    source_id: str
    url: str
    title: str
    organizer: str | None = None
    organizer_type: str | None = None
    categories: list[str] = field(default_factory=list)
    eligibility: list[str] = field(default_factory=list)
    start_date: date | None = None
    deadline: date | None = None
    posted_at: datetime | None = None
    prize_text: str | None = None
    top_prize_krw: int | None = None
    total_prize_krw: int | None = None
    benefits: list[str] = field(default_factory=list)
    homepage: str | None = None
    keywords: list[str] = field(default_factory=list)
    detail_text: str | None = None
    warnings: list[ParseWarning] = field(default_factory=list)

    @property
    def key(self) -> str:
        return f"{self.source}:{self.source_id}"

    @property
    def days_left(self) -> int | None:
        if self.deadline is None:
            return None
        return (self.deadline - date.today()).days

    @property
    def best_prize_krw(self) -> int | None:
        """개인이 노릴 수 있는 상금의 대표값(1등 상금 우선)."""
        return self.top_prize_krw or self.total_prize_krw

    def fingerprint(self) -> str:
        """cross-source 중복 판정을 위한 정규화 문자열."""
        return normalize_for_match(self.title)

    def topic_haystack(self) -> str:
        """분야 판정용. 제목·분야·키워드처럼 **신뢰도 높은** 필드만 본다.

        본문(detail_text)까지 넣으면 '청소년 불법도박 예방' 같은 문구 때문에
        멀쩡한 영상 공모전이 '청소년 전용'으로 오판된다.
        """
        parts = [
            self.title,
            " ".join(self.categories),
            " ".join(self.keywords),
            self.prize_text or "",
        ]
        return " ".join(parts).lower()

    def full_haystack(self) -> str:
        """본문까지 포함. 팀 구성 요구처럼 본문에만 적히는 조건을 찾을 때 쓴다."""
        parts = [
            self.topic_haystack(),
            self.organizer or "",
            self.organizer_type or "",
            " ".join(self.eligibility),
            " ".join(self.benefits),
            (self.detail_text or "")[:8000],
        ]
        return " ".join(parts).lower()

    def eligibility_text(self) -> str:
        return " ".join(self.eligibility).lower()

    def as_jsonable(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("warnings", None)
        d["start_date"] = self.start_date.isoformat() if self.start_date else None
        d["deadline"] = self.deadline.isoformat() if self.deadline else None
        d["posted_at"] = self.posted_at.isoformat() if self.posted_at else None
        return d


_NOISE = re.compile(
    r"(제\s*\d+\s*회|20\d{2}\s*년?|공모전|공모|대회|경진대회|콘테스트|contest|awards?|"
    r"모집|이벤트|안내|참가자)",
    re.IGNORECASE,
)
_NON_WORD = re.compile(r"[^0-9a-z가-힣]+")


def normalize_for_match(text: str) -> str:
    """제목에서 회차/연도/일반 명사를 걷어낸 매칭용 표준형."""
    s = (text or "").lower()
    s = _NOISE.sub(" ", s)
    s = _NON_WORD.sub(" ", s)
    return " ".join(s.split())


@dataclass(slots=True)
class SourceStats:
    """소스 1개의 이번 회차 실행 요약."""

    source: str
    robots: str = "UNKNOWN"
    list_pages: int = 0
    discovered: int = 0
    new: int = 0
    existing: int = 0
    details_fetched: int = 0
    requests: int = 0
    errors: int = 0
    skipped_reason: str | None = None

    def as_jsonable(self) -> dict[str, Any]:
        return asdict(self)
