"""대시보드용 스키마 확장 (v3).

기존 :mod:`contest_scout.db` 의 3개 테이블(``contests`` / ``crawl_runs`` /
``recommendations``)은 그대로 두고, UI가 필요로 하는 것만 **덧붙인다**.

``contest_scores``   공모전별 *현재* 점수. ``recommendations`` 는 회차별 이력이라
                     "지금 이 공모전의 점수"를 뽑기에 불편하다. 목록 정렬·필터가
                     매번 서브쿼리를 돌지 않도록 최신값을 1행으로 유지한다.
``projects``         `참가하기` → Contest Builder 로 넘어가는 프로젝트 레코드.
``contest_tags``     UI 필터가 쓰는 정규화된 분야 태그.
``status_events``    상태 전환 로그. Analytics의 "선택 패턴" 은 추정이 아니라
                     이 로그에서 계산한다.

``crawl_runs`` 에는 실행 상태(RUNNING/SUCCESS/PARTIAL/FAILED)를 담을 컬럼만
ALTER 로 추가한다. 기존 DB 파일도 그대로 열린다.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

SCHEMA_EXT_VERSION = 3

DDL = """
CREATE TABLE IF NOT EXISTS contest_scores (
    contest_key        TEXT PRIMARY KEY,
    evaluator          TEXT NOT NULL,
    total              INTEGER NOT NULL,
    tier               TEXT NOT NULL,
    parts_json         TEXT NOT NULL,
    reasons_json       TEXT NOT NULL DEFAULT '[]',
    risks_json         TEXT NOT NULL DEFAULT '[]',
    estimated_workdays TEXT,
    idea_seeds_json    TEXT NOT NULL DEFAULT '[]',
    profile_hash       TEXT,
    updated_at         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_scores_tier  ON contest_scores(tier);
CREATE INDEX IF NOT EXISTS idx_scores_total ON contest_scores(total);

CREATE TABLE IF NOT EXISTS projects (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    contest_key  TEXT NOT NULL UNIQUE,
    title        TEXT NOT NULL,
    brief        TEXT,
    deadline     TEXT,
    requirements TEXT,
    stage        TEXT NOT NULL DEFAULT 'RESEARCH',
    next_action  TEXT,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS contest_tags (
    contest_key TEXT NOT NULL,
    tag         TEXT NOT NULL,
    PRIMARY KEY (contest_key, tag)
);
CREATE INDEX IF NOT EXISTS idx_tags_tag ON contest_tags(tag);

CREATE TABLE IF NOT EXISTS status_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    contest_key TEXT NOT NULL,
    from_status TEXT,
    to_status   TEXT NOT NULL,
    tier        TEXT,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_key ON status_events(contest_key);
"""

#: 프로젝트 진행 단계. UI 진행률 막대는 이 순서에서 계산한다.
PROJECT_STAGES = ["RESEARCH", "IDEA_DEVELOPMENT", "PRODUCTION", "REVIEW", "SUBMITTED"]

RUN_STATUSES = ("RUNNING", "SUCCESS", "PARTIAL", "FAILED")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def apply_extensions(conn: sqlite3.Connection) -> None:
    """새 테이블 생성 + 기존 테이블 컬럼 추가. 여러 번 호출해도 안전하다."""
    conn.executescript(DDL)

    existing = _columns(conn, "crawl_runs")
    if "status" not in existing:
        conn.execute(
            "ALTER TABLE crawl_runs ADD COLUMN status TEXT NOT NULL DEFAULT 'SUCCESS'"
        )
    if "error_json" not in existing:
        conn.execute(
            "ALTER TABLE crawl_runs ADD COLUMN error_json TEXT NOT NULL DEFAULT '[]'"
        )
    if "trigger" not in existing:
        conn.execute(
            "ALTER TABLE crawl_runs ADD COLUMN trigger TEXT NOT NULL DEFAULT 'cli'"
        )

    conn.execute(
        "INSERT INTO meta(key, value) VALUES('schema_ext_version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (str(SCHEMA_EXT_VERSION),),
    )
    conn.commit()


def upsert_score(
    conn: sqlite3.Connection, contest_key: str, evaluation: Any, profile_hash: str | None = None
) -> None:
    """공모전의 *현재* 점수를 1행으로 유지한다."""
    conn.execute(
        """
        INSERT INTO contest_scores(
            contest_key, evaluator, total, tier, parts_json, reasons_json,
            risks_json, estimated_workdays, idea_seeds_json, profile_hash, updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(contest_key) DO UPDATE SET
            evaluator = excluded.evaluator,
            total = excluded.total,
            tier = excluded.tier,
            parts_json = excluded.parts_json,
            reasons_json = excluded.reasons_json,
            risks_json = excluded.risks_json,
            estimated_workdays = excluded.estimated_workdays,
            idea_seeds_json = excluded.idea_seeds_json,
            profile_hash = excluded.profile_hash,
            updated_at = excluded.updated_at
        """,
        (
            contest_key,
            getattr(evaluation, "evaluator", "rules"),
            int(evaluation.total),
            evaluation.tier,
            json.dumps(evaluation.parts, ensure_ascii=False),
            json.dumps(evaluation.reasons, ensure_ascii=False),
            json.dumps(evaluation.risks, ensure_ascii=False),
            getattr(evaluation, "estimated_workdays", None),
            json.dumps(getattr(evaluation, "idea_seeds", []) or [], ensure_ascii=False),
            profile_hash,
            _now(),
        ),
    )


__all__ = [
    "PROJECT_STAGES",
    "RUN_STATUSES",
    "SCHEMA_EXT_VERSION",
    "apply_extensions",
    "upsert_score",
]
