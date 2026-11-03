"""설정 조회 / 수정.

배점을 바꾸면 이미 채점된 공모전이 옛 기준을 그대로 들고 있게 된다. 그래서
프로필을 수정하면 그 자리에서 전체를 다시 채점한다.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, HTTPException

from contest_scout import paths
from contest_scout.api.schemas import SettingsPatch
from contest_scout.db import Database
from contest_scout.evaluators.base import PART_LABELS
from contest_scout.services.scheduler import scheduler
from contest_scout.services.scout import sync_scores
from contest_scout.services.settings import (
    load_settings,
    read_profile_document,
    save_settings,
    write_profile_document,
)
from contest_scout.sources import SOURCES

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _payload() -> dict[str, Any]:
    settings = load_settings()
    profile = read_profile_document()
    return {
        "crawl": asdict(settings.crawl),
        "schedule": asdict(settings.schedule),
        "enabled_sources": settings.enabled_sources,
        "available_sources": [
            {"name": name, "entry_url": cls.entry_url} for name, cls in SOURCES.items()
        ],
        "profile": {
            "weights": profile.get("weights", {}),
            "strong_keywords": profile.get("strong_keywords", []),
            "preferred_keywords": profile.get("preferred_keywords", []),
            "negative_keywords": profile.get("negative_keywords", []),
            "tier_thresholds": profile.get("tier_thresholds", {}),
            "min_days_left": profile.get("min_days_left"),
            "strong_prize_krw": profile.get("strong_prize_krw"),
            "good_prize_krw": profile.get("good_prize_krw"),
        },
        "part_labels": PART_LABELS,
        "scheduler": scheduler.status(),
        "paths": {
            "db": str(paths.db_path()),
            "profile": str(paths.profile_path()),
            "settings": str(paths.settings_path()),
            "report": str(paths.report_path()),
        },
        "capabilities": {
            # 미구현 기능을 UI에서 그럴듯하게 그리지 않기 위한 플래그.
            "ai_evaluator": False,
            "notifications": False,
            "contest_builder": False,
            "scheduler_persistent": False,
        },
    }


@router.get("")
def get_settings() -> dict[str, Any]:
    return _payload()


@router.patch("")
def patch_settings(body: SettingsPatch) -> dict[str, Any]:
    settings = load_settings()

    if body.crawl:
        for key, value in body.crawl.model_dump(exclude_unset=True).items():
            if value is not None or key in ("limit", "user_agent"):
                setattr(settings.crawl, key, value)
    if body.schedule:
        for key, value in body.schedule.model_dump(exclude_unset=True).items():
            if value is not None:
                setattr(settings.schedule, key, value)
    if body.enabled_sources is not None:
        unknown = [s for s in body.enabled_sources if s not in SOURCES]
        if unknown:
            raise HTTPException(400, f"알 수 없는 소스: {', '.join(unknown)}")
        if not body.enabled_sources:
            raise HTTPException(400, "소스를 최소 하나는 켜 두어야 합니다")
        settings.enabled_sources = body.enabled_sources

    save_settings(settings)

    rescored = 0
    if body.profile:
        patch = body.profile.model_dump(exclude_unset=True, exclude_none=True)
        if patch:
            try:
                write_profile_document(patch)
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
            with Database(paths.db_path(), check_same_thread=False) as db:
                rescored = sync_scores(db, force=True)

    payload = _payload()
    payload["rescored"] = rescored
    return payload
