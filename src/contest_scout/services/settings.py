"""설정 읽기/쓰기.

두 파일로 나눈다.

``config/profile.json``   점수 배점·키워드·등급 기준. **엔진이 읽는 파일**이라
                          CLI와 대시보드가 같은 값을 본다.
``config/settings.json``  크롤링 옵션·자동 실행 스케줄처럼 엔진 밖의 운영 설정.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Any

from contest_scout import paths
from contest_scout.config import load_profile

log = logging.getLogger(__name__)


@dataclass(slots=True)
class CrawlSettings:
    delay: float = 2.0
    timeout: float = 20.0
    pages: int = 1
    limit: int | None = None
    respect_robots: bool = True
    user_agent: str | None = None


@dataclass(slots=True)
class ScheduleSettings:
    enabled: bool = False
    #: 로컬 시각 ``HH:MM``.
    time: str = "08:00"


@dataclass(slots=True)
class AppSettings:
    crawl: CrawlSettings = field(default_factory=CrawlSettings)
    schedule: ScheduleSettings = field(default_factory=ScheduleSettings)
    enabled_sources: list[str] = field(default_factory=lambda: ["thinkgood", "linkareer"])

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def source_selection(self) -> str:
        return ",".join(self.enabled_sources) if self.enabled_sources else "all"


def load_settings() -> AppSettings:
    path = paths.settings_path()
    if not path.is_file():
        return AppSettings()
    try:
        raw = json.loads(path.read_text("utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("settings.json 을 읽지 못해 기본값을 씁니다: %s", exc)
        return AppSettings()

    crawl = CrawlSettings(**{**asdict(CrawlSettings()), **(raw.get("crawl") or {})})
    schedule = ScheduleSettings(
        **{**asdict(ScheduleSettings()), **(raw.get("schedule") or {})}
    )
    sources = raw.get("enabled_sources")
    settings = AppSettings(crawl=crawl, schedule=schedule)
    if isinstance(sources, list) and sources:
        settings.enabled_sources = [str(s) for s in sources]
    return settings


def save_settings(settings: AppSettings) -> AppSettings:
    paths.ensure_dirs()
    paths.settings_path().write_text(
        json.dumps(settings.as_dict(), ensure_ascii=False, indent=2) + "\n", "utf-8"
    )
    return settings


# ---------------------------------------------------------------------- #
# 프로필 (점수 배점 / 키워드)
# ---------------------------------------------------------------------- #
def read_profile_document() -> dict[str, Any]:
    """현재 적용 중인 프로필 전체를 dict로 돌려준다 (기본값 + 사용자 파일)."""
    from importlib import resources

    base = json.loads(
        resources.files("contest_scout").joinpath("default_profile.json").read_text("utf-8")
    )
    path = paths.profile_path()
    if path.is_file():
        try:
            base.update(json.loads(path.read_text("utf-8")))
        except json.JSONDecodeError as exc:
            log.warning("profile.json 파싱 실패, 기본 프로필을 씁니다: %s", exc)
    return base


def write_profile_document(patch: dict[str, Any]) -> dict[str, Any]:
    """프로필을 부분 수정해 파일로 저장한다.

    배점 합계가 100이 아니면 저장하지 않고 :class:`ValueError` 를 던진다.
    """
    document = read_profile_document()
    for key, value in patch.items():
        if value is None:
            continue
        document[key] = value

    weights = document.get("weights") or {}
    total = sum(int(v) for v in weights.values())
    if total != 100:
        raise ValueError(f"배점 합계는 100이어야 합니다 (현재 {total}).")

    paths.ensure_dirs()
    paths.profile_path().write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", "utf-8"
    )
    return document


def profile_hash(profile: Any | None = None) -> str:
    """평가에 영향을 주는 값들의 지문. 설정이 바뀌면 재채점이 필요하다는 신호."""
    if profile is None:
        profile = load_profile(str(paths.profile_path()) if paths.profile_path().is_file() else None)
    payload = {
        "weights": profile.weights,
        "strong": profile.strong_keywords,
        "preferred": profile.preferred_keywords,
        "negative": profile.negative_keywords,
        "thresholds": profile.tier_thresholds,
        "min_days_left": profile.min_days_left,
        "strong_prize": profile.strong_prize_krw,
        "good_prize": profile.good_prize_krw,
    }
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def current_profile():
    """파일이 있으면 파일을, 없으면 패키지 기본 프로필을 로드한다."""
    path = paths.profile_path()
    return load_profile(str(path) if path.is_file() else None)


__all__ = [
    "AppSettings",
    "CrawlSettings",
    "ScheduleSettings",
    "current_profile",
    "load_settings",
    "profile_hash",
    "read_profile_document",
    "save_settings",
    "write_profile_document",
]
