"""서비스 레이어 테스트 — 분야 태깅, 점수 동기화, 설정 저장."""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

from contest_scout import paths
from contest_scout.db import Database
from contest_scout.models import Contest
from contest_scout.repository import ContestQuery, Repository
from contest_scout.services.scout import sync_scores
from contest_scout.services.settings import (
    AppSettings,
    load_settings,
    profile_hash,
    save_settings,
    write_profile_document,
)
from contest_scout.taxonomy import tags_for


def contest(title: str, **kwargs) -> Contest:
    base = dict(
        source="thinkgood",
        source_id="1",
        url="https://example.test/1",
        title=title,
        deadline=date.today() + timedelta(days=20),
        top_prize_krw=2_000_000,
    )
    base.update(kwargs)
    return Contest(**base)


# ---------------------------------------------------------------------- #
# 분야 태깅
# ---------------------------------------------------------------------- #
def test_tags_come_from_title_categories_and_keywords() -> None:
    tags = tags_for(contest("2026 생성형 AI 숏폼 광고 공모전"))
    assert {"AI", "숏폼", "광고"} <= set(tags)

    from_category = tags_for(contest("무제 공모전", categories=["포스터/그래픽"]))
    assert "포스터" in from_category


def test_body_text_does_not_pollute_tags() -> None:
    """본문까지 뒤지면 '청소년 불법도박 예방' 같은 주제어가 분야를 오염시킨다."""
    tagged = tags_for(
        contest(
            "브랜드 영상 공모전",
            detail_text="본 공모전은 건축 및 소프트웨어 분야 종사자도 관람 가능합니다.",
        )
    )
    assert "건축·공간" not in tagged
    assert "개발·SW" not in tagged
    assert "영상" in tagged


def test_unmatched_contest_still_gets_a_tag() -> None:
    assert tags_for(contest("제3회 전통 장 담그기 대회")) == ["기타"]


# ---------------------------------------------------------------------- #
# 점수·태그 동기화
# ---------------------------------------------------------------------- #
def test_sync_scores_backfills_contests_without_scores(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CONTEST_SCOUT_CONFIG_DIR", str(tmp_path / "config"))
    db = Database(tmp_path / "sync.sqlite3")
    db.upsert(contest("2026 AI 영상 공모전"))
    db.upsert(contest("문학 백일장", source_id="2", categories=["문학"]))

    repo = Repository(db)
    assert len(repo.unscored_keys()) == 2

    assert sync_scores(db) == 2
    assert repo.unscored_keys() == []
    assert repo.untagged_keys() == []

    # 두 번째 호출은 할 일이 없다 (프로필이 그대로라 재채점하지 않는다).
    assert sync_scores(db) == 0
    db.close()


def test_sync_scores_reruns_when_profile_changes(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CONTEST_SCOUT_CONFIG_DIR", str(tmp_path / "config"))
    db = Database(tmp_path / "sync2.sqlite3")
    db.upsert(contest("2026 AI 영상 공모전"))
    sync_scores(db)

    before = db.conn.execute("SELECT profile_hash FROM contest_scores").fetchone()[0]
    write_profile_document(
        {
            "weights": {
                "award_value": 10,
                "skill_fit": 30,
                "feasibility": 15,
                "win_probability": 15,
                "idea_headroom": 10,
                "workflow_reuse": 5,
                "solo_friendly": 5,
                "portfolio_value": 5,
                "organizer_trust": 5,
            }
        }
    )
    assert sync_scores(db) == 1
    after = db.conn.execute("SELECT profile_hash FROM contest_scores").fetchone()[0]
    assert before != after
    db.close()


# ---------------------------------------------------------------------- #
# 설정
# ---------------------------------------------------------------------- #
def test_settings_roundtrip_through_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CONTEST_SCOUT_CONFIG_DIR", str(tmp_path / "config"))
    settings = AppSettings()
    settings.crawl.delay = 4.0
    settings.schedule.enabled = True
    settings.enabled_sources = ["thinkgood"]
    save_settings(settings)

    loaded = load_settings()
    assert loaded.crawl.delay == 4.0
    assert loaded.schedule.enabled is True
    assert loaded.source_selection == "thinkgood"


def test_broken_settings_file_falls_back_to_defaults(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CONTEST_SCOUT_CONFIG_DIR", str(tmp_path / "config"))
    paths.ensure_dirs()
    paths.settings_path().write_text("{ not json", "utf-8")
    assert load_settings().crawl.delay == 2.0


def test_profile_write_rejects_bad_weight_total(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CONTEST_SCOUT_CONFIG_DIR", str(tmp_path / "config"))
    with pytest.raises(ValueError, match="100"):
        write_profile_document({"weights": {"award_value": 99}})
    assert not paths.profile_path().exists()


def test_profile_hash_tracks_scoring_inputs(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CONTEST_SCOUT_CONFIG_DIR", str(tmp_path / "config"))
    first = profile_hash()
    write_profile_document({"strong_keywords": ["ai 영상", "새 키워드"]})
    assert profile_hash() != first


def test_written_profile_is_self_contained(tmp_path, monkeypatch) -> None:
    """부분 수정으로 저장해도 나머지 항목이 사라지면 안 된다."""
    monkeypatch.setenv("CONTEST_SCOUT_CONFIG_DIR", str(tmp_path / "config"))
    write_profile_document({"min_days_left": 5})
    saved = json.loads(paths.profile_path().read_text("utf-8"))
    assert saved["min_days_left"] == 5
    assert sum(saved["weights"].values()) == 100
    assert saved["strong_keywords"]


def test_repository_query_defaults_hide_inactive() -> None:
    assert ContestQuery().include_inactive is False
    assert ContestQuery().collapse_duplicates is True
