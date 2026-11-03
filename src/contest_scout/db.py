"""SQLite 저장소.

테이블 3개:

``contests``          정규화된 공모전 + 사용자 상태(NEW/IGNORE/ENTERING …)
``crawl_runs``        회차별 실행 요약 (incremental crawl 통계)
``recommendations``   회차별 평가 결과 (점수·등급·근거)
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

from contest_scout.models import (
    SUPPRESSED_STATUSES,
    USER_LOCKED_STATUSES,
    Contest,
    ContestStatus,
)
from contest_scout.normalize import similarity
from contest_scout.schema_ext import apply_extensions, upsert_score

log = logging.getLogger(__name__)

SCHEMA_VERSION = 2

SCHEMA = """
CREATE TABLE IF NOT EXISTS contests (
    contest_key   TEXT PRIMARY KEY,
    source        TEXT NOT NULL,
    source_id     TEXT NOT NULL,
    canonical_key TEXT NOT NULL,
    fingerprint   TEXT NOT NULL,
    title         TEXT NOT NULL,
    organizer     TEXT,
    url           TEXT NOT NULL,
    start_date    TEXT,
    deadline      TEXT,
    top_prize_krw INTEGER,
    status        TEXT NOT NULL DEFAULT 'NEW',
    payload_json  TEXT NOT NULL,
    first_seen    TEXT NOT NULL,
    last_seen     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_contests_status    ON contests(status);
CREATE INDEX IF NOT EXISTS idx_contests_deadline  ON contests(deadline);
CREATE INDEX IF NOT EXISTS idx_contests_canonical ON contests(canonical_key);
CREATE INDEX IF NOT EXISTS idx_contests_fp        ON contests(fingerprint);

CREATE TABLE IF NOT EXISTS crawl_runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at    TEXT NOT NULL,
    finished_at   TEXT,
    sources       TEXT NOT NULL,
    total_new     INTEGER NOT NULL DEFAULT 0,
    total_seen    INTEGER NOT NULL DEFAULT 0,
    requests      INTEGER NOT NULL DEFAULT 0,
    stats_json    TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS recommendations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id        INTEGER NOT NULL,
    contest_key   TEXT NOT NULL,
    evaluator     TEXT NOT NULL,
    total         INTEGER NOT NULL,
    tier          TEXT NOT NULL,
    parts_json    TEXT NOT NULL,
    reasons_json  TEXT NOT NULL DEFAULT '[]',
    risks_json    TEXT NOT NULL DEFAULT '[]',
    created_at    TEXT NOT NULL,
    FOREIGN KEY (contest_key) REFERENCES contests(contest_key)
);
CREATE INDEX IF NOT EXISTS idx_reco_run ON recommendations(run_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_reco_unique
    ON recommendations(run_id, contest_key, evaluator);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

#: 다른 소스의 같은 공모전으로 볼 제목 유사도 하한.
DEDUPE_THRESHOLD = 0.62


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(
        self,
        path: str | Path = "data/contest_scout.sqlite3",
        *,
        check_same_thread: bool = True,
    ) -> None:
        """``check_same_thread=False`` 는 HTTP API 전용이다.

        FastAPI는 동기 의존성과 동기 핸들러를 서로 다른 워커 스레드에서 실행할 수
        있다. 커넥션은 요청 하나가 독점하므로 동시 사용은 없지만, 스레드는 바뀔 수
        있어서 sqlite3의 스레드 검사만 꺼 준다. CLI는 기본값 그대로다.
        """
        self.path = Path(path)
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), check_same_thread=check_same_thread)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        # 대시보드가 읽는 동안 수집기가 쓸 수 있어야 한다.
        self.conn.execute("PRAGMA busy_timeout = 8000")
        if str(path) != ":memory:":
            self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.executescript(SCHEMA)
        self.conn.execute(
            "INSERT INTO meta(key, value) VALUES('schema_version', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(SCHEMA_VERSION),),
        )
        self.conn.commit()
        # 대시보드가 쓰는 테이블/컬럼을 덧붙인다 (기존 데이터는 그대로).
        apply_extensions(self.conn)

    # ------------------------------------------------------------------ #
    # incremental crawl 지원
    # ------------------------------------------------------------------ #
    def known_keys(self, source: str) -> set[str]:
        rows = self.conn.execute(
            "SELECT contest_key FROM contests WHERE source = ?", (source,)
        ).fetchall()
        return {row["contest_key"] for row in rows}

    def touch(self, keys: Iterable[str]) -> None:
        """이미 아는 공모전의 ``last_seen`` 만 갱신 (상세 요청 없음)."""
        keys = list(keys)
        if not keys:
            return
        now = _now()
        self.conn.executemany(
            "UPDATE contests SET last_seen = ? WHERE contest_key = ?",
            [(now, key) for key in keys],
        )
        self.conn.commit()

    # ------------------------------------------------------------------ #
    # 저장
    # ------------------------------------------------------------------ #
    def upsert(self, contest: Contest) -> bool:
        """공모전 저장. 신규면 ``True``."""
        now = _now()
        key = contest.key
        fingerprint = contest.fingerprint()
        row = self.conn.execute(
            "SELECT contest_key, status FROM contests WHERE contest_key = ?", (key,)
        ).fetchone()
        is_new = row is None
        canonical_key = self._canonical_key(contest, fingerprint) if is_new else None

        if is_new:
            self.conn.execute(
                """
                INSERT INTO contests(
                    contest_key, source, source_id, canonical_key, fingerprint, title,
                    organizer, url, start_date, deadline, top_prize_krw, status,
                    payload_json, first_seen, last_seen)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    key,
                    contest.source,
                    contest.source_id,
                    canonical_key,
                    fingerprint,
                    contest.title,
                    contest.organizer,
                    contest.url,
                    contest.start_date.isoformat() if contest.start_date else None,
                    contest.deadline.isoformat() if contest.deadline else None,
                    contest.best_prize_krw,
                    ContestStatus.NEW.value,
                    json.dumps(contest.as_jsonable(), ensure_ascii=False),
                    now,
                    now,
                ),
            )
        else:
            self.conn.execute(
                """
                UPDATE contests SET
                    fingerprint = ?, title = ?, organizer = ?, url = ?,
                    start_date = ?, deadline = ?, top_prize_krw = ?,
                    payload_json = ?, last_seen = ?
                WHERE contest_key = ?
                """,
                (
                    fingerprint,
                    contest.title,
                    contest.organizer,
                    contest.url,
                    contest.start_date.isoformat() if contest.start_date else None,
                    contest.deadline.isoformat() if contest.deadline else None,
                    contest.best_prize_krw,
                    json.dumps(contest.as_jsonable(), ensure_ascii=False),
                    now,
                    key,
                ),
            )
        self.conn.commit()
        return is_new

    def _canonical_key(self, contest: Contest, fingerprint: str) -> str:
        """cross-source 중복이면 기존 canonical_key를 물려받는다.

        초기 버전은 '정규화 제목 토큰 Jaccard + 마감일 일치' 정도의 가벼운 규칙만
        쓴다. 더 정교한 fuzzy matching을 넣더라도 이 함수만 교체하면 된다.
        """
        if not fingerprint:
            return contest.key
        candidates = self.conn.execute(
            "SELECT contest_key, canonical_key, fingerprint, deadline, organizer "
            "FROM contests WHERE source != ?",
            (contest.source,),
        ).fetchall()

        deadline = contest.deadline.isoformat() if contest.deadline else None
        best: tuple[float, str] | None = None
        for row in candidates:
            score = similarity(fingerprint, row["fingerprint"] or "")
            if score < DEDUPE_THRESHOLD:
                continue
            # 마감일이 둘 다 있는데 다르면 다른 공모전으로 본다.
            if deadline and row["deadline"] and deadline != row["deadline"]:
                continue
            if best is None or score > best[0]:
                best = (score, row["canonical_key"] or row["contest_key"])

        if best is not None:
            log.info("중복 후보 통합: %s -> %s (유사도 %.2f)", contest.key, best[1], best[0])
            return best[1]
        return contest.key

    # ------------------------------------------------------------------ #
    # 상태 관리
    # ------------------------------------------------------------------ #
    def set_status(self, contest_key: str, status: ContestStatus) -> bool:
        cur = self.conn.execute(
            "UPDATE contests SET status = ? WHERE contest_key = ?",
            (status.value, contest_key),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def get_status(self, contest_key: str) -> ContestStatus | None:
        row = self.conn.execute(
            "SELECT status FROM contests WHERE contest_key = ?", (contest_key,)
        ).fetchone()
        return ContestStatus(row["status"]) if row else None

    def is_suppressed(self, contest_key: str) -> bool:
        """IGNORE/EXPIRED는 다시 추천하지 않는다."""
        status = self.get_status(contest_key)
        return status in SUPPRESSED_STATUSES if status else False

    def suppressed_canonical_keys(self) -> set[str]:
        """IGNORE된 공모전과 같은 canonical 그룹은 다른 소스에서도 숨긴다."""
        rows = self.conn.execute(
            "SELECT canonical_key FROM contests WHERE status = ?",
            (ContestStatus.IGNORE.value,),
        ).fetchall()
        return {row["canonical_key"] for row in rows}

    def mark_recommended(self, contest_keys: Sequence[str]) -> None:
        """사용자가 직접 정한 상태는 건드리지 않고 NEW만 RECOMMENDED로."""
        if not contest_keys:
            return
        locked = tuple(s.value for s in USER_LOCKED_STATUSES)
        placeholders = ",".join("?" * len(contest_keys))
        self.conn.execute(
            f"UPDATE contests SET status = ? "
            f"WHERE contest_key IN ({placeholders}) "
            f"AND status NOT IN ({','.join('?' * len(locked))})",
            (ContestStatus.RECOMMENDED.value, *contest_keys, *locked),
        )
        self.conn.commit()

    def expire_past_deadline(self, today: date | None = None) -> int:
        today = today or date.today()
        locked = tuple(s.value for s in USER_LOCKED_STATUSES)
        cur = self.conn.execute(
            f"UPDATE contests SET status = ? "
            f"WHERE deadline IS NOT NULL AND deadline < ? "
            f"AND status NOT IN ({','.join('?' * len(locked))}) AND status != ?",
            (
                ContestStatus.EXPIRED.value,
                today.isoformat(),
                *locked,
                ContestStatus.EXPIRED.value,
            ),
        )
        self.conn.commit()
        return cur.rowcount

    # ------------------------------------------------------------------ #
    # 실행 기록 / 평가 기록
    # ------------------------------------------------------------------ #
    def start_run(self, sources: Sequence[str]) -> int:
        cur = self.conn.execute(
            "INSERT INTO crawl_runs(started_at, sources) VALUES(?,?)",
            (_now(), ",".join(sources)),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def finish_run(
        self,
        run_id: int,
        *,
        total_new: int,
        total_seen: int,
        requests: int,
        stats: dict[str, Any],
    ) -> None:
        self.conn.execute(
            "UPDATE crawl_runs SET finished_at = ?, total_new = ?, total_seen = ?, "
            "requests = ?, stats_json = ? WHERE id = ?",
            (
                _now(),
                total_new,
                total_seen,
                requests,
                json.dumps(stats, ensure_ascii=False),
                run_id,
            ),
        )
        self.conn.commit()

    def save_recommendation(
        self,
        run_id: int,
        contest_key: str,
        evaluation: Any,
        *,
        profile_hash: str | None = None,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO recommendations(
                run_id, contest_key, evaluator, total, tier,
                parts_json, reasons_json, risks_json, created_at)
            VALUES(?,?,?,?,?,?,?,?,?)
            ON CONFLICT(run_id, contest_key, evaluator) DO UPDATE SET
                total = excluded.total, tier = excluded.tier,
                parts_json = excluded.parts_json,
                reasons_json = excluded.reasons_json,
                risks_json = excluded.risks_json
            """,
            (
                run_id,
                contest_key,
                evaluation.evaluator,
                evaluation.total,
                evaluation.tier,
                json.dumps(evaluation.parts, ensure_ascii=False),
                json.dumps(evaluation.reasons, ensure_ascii=False),
                json.dumps(evaluation.risks, ensure_ascii=False),
                _now(),
            ),
        )
        upsert_score(self.conn, contest_key, evaluation, profile_hash)
        self.conn.commit()

    # ------------------------------------------------------------------ #
    # 조회
    # ------------------------------------------------------------------ #
    def load_contest(self, contest_key: str) -> Contest | None:
        row = self.conn.execute(
            "SELECT payload_json FROM contests WHERE contest_key = ?", (contest_key,)
        ).fetchone()
        if row is None:
            return None
        return contest_from_payload(json.loads(row["payload_json"]))

    def list_contests(
        self, *, status: str | None = None, limit: int = 50
    ) -> list[sqlite3.Row]:
        if status:
            return self.conn.execute(
                "SELECT * FROM contests WHERE status = ? "
                "ORDER BY (deadline IS NULL), deadline LIMIT ?",
                (status, limit),
            ).fetchall()
        return self.conn.execute(
            "SELECT * FROM contests ORDER BY first_seen DESC LIMIT ?", (limit,)
        ).fetchall()

    def last_runs(self, limit: int = 5) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM crawl_runs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> Database:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def contest_from_payload(payload: dict[str, Any]) -> Contest:
    """``payload_json`` → :class:`Contest` 복원."""
    from contest_scout.normalize import parse_date

    return Contest(
        source=payload["source"],
        source_id=payload["source_id"],
        url=payload["url"],
        title=payload["title"],
        organizer=payload.get("organizer"),
        organizer_type=payload.get("organizer_type"),
        categories=payload.get("categories") or [],
        eligibility=payload.get("eligibility") or [],
        start_date=parse_date(payload.get("start_date")),
        deadline=parse_date(payload.get("deadline")),
        posted_at=None,
        prize_text=payload.get("prize_text"),
        top_prize_krw=payload.get("top_prize_krw"),
        total_prize_krw=payload.get("total_prize_krw"),
        benefits=payload.get("benefits") or [],
        homepage=payload.get("homepage"),
        keywords=payload.get("keywords") or [],
        detail_text=payload.get("detail_text"),
    )


__all__ = ["Database", "contest_from_payload", "SCHEMA_VERSION"]
