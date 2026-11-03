"""대시보드 조회 계층.

``Database`` 는 수집기가 쓰는 저장소다. 여기서는 그 위에 **읽기 중심**의 질의를
얹는다. 프론트엔드는 SQL을 모르고, API는 여기서 만든 dict를 그대로 직렬화한다.

시간 처리 규칙 하나만 기억하면 된다. ``first_seen`` / ``last_seen`` 은 UTC ISO로
저장돼 있으므로, "오늘 발견" 같은 판단은 반드시 ``date(x, 'localtime')`` 으로
로컬 날짜를 만든 뒤에 한다.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Iterable, Sequence

from contest_scout.db import Database, contest_from_payload
from contest_scout.models import ContestStatus
from contest_scout.schema_ext import PROJECT_STAGES, _now
from contest_scout.taxonomy import DISPLAY_ORDER

#: 대시보드 기본 집계에서 빼는 상태.
INACTIVE_STATUSES = (ContestStatus.IGNORE.value, ContestStatus.EXPIRED.value)
#: 사용자가 "고르겠다"고 의사표시한 상태.
SELECTED_STATUSES = (
    ContestStatus.INTERESTED.value,
    ContestStatus.ENTERING.value,
    ContestStatus.SUBMITTED.value,
)
TIER_RANK = {"S": 0, "A": 1, "B": 2, "SKIP": 3}

SORT_COLUMNS = {
    "score": "s.total",
    "deadline": "c.deadline",
    "prize": "c.top_prize_krw",
    "discovered": "c.first_seen",
    "title": "c.title",
}


@dataclass(slots=True)
class ContestQuery:
    """목록 필터. 프론트엔드 쿼리스트링과 1:1로 대응한다."""

    q: str | None = None
    tiers: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    statuses: list[str] = field(default_factory=list)
    min_prize: int | None = None
    deadline_within: int | None = None
    include_inactive: bool = False
    only_new_today: bool = False
    #: 같은 공모전이 소스마다 한 줄씩 나오지 않도록 canonical_key로 접는다.
    collapse_duplicates: bool = True
    sort: str = "score"
    order: str = "desc"
    page: int = 1
    page_size: int = 30


def _loads(raw: str | None, fallback: Any) -> Any:
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return fallback


def _days_left(deadline: str | None, today: date) -> int | None:
    if not deadline:
        return None
    try:
        return (date.fromisoformat(deadline) - today).days
    except ValueError:
        return None


class Repository:
    """읽기 질의 + 상태 전환. :class:`Database` 의 커넥션을 빌려 쓴다."""

    def __init__(self, db: Database, today: date | None = None) -> None:
        self.db = db
        self.conn: sqlite3.Connection = db.conn
        self.today = today or date.today()

    # ------------------------------------------------------------------ #
    # 직렬화
    # ------------------------------------------------------------------ #
    def _row_to_contest(self, row: sqlite3.Row, *, detail: bool = False) -> dict[str, Any]:
        payload = _loads(row["payload_json"], {})
        keys = row.keys()
        deadline = row["deadline"]
        days_left = _days_left(deadline, self.today)

        item: dict[str, Any] = {
            "key": row["contest_key"],
            "source": row["source"],
            "source_id": row["source_id"],
            "title": row["title"],
            "organizer": row["organizer"],
            "organizer_type": payload.get("organizer_type"),
            "url": row["url"],
            "homepage": payload.get("homepage"),
            "categories": payload.get("categories") or [],
            "eligibility": payload.get("eligibility") or [],
            "keywords": payload.get("keywords") or [],
            "start_date": row["start_date"],
            "deadline": deadline,
            "days_left": days_left,
            "prize_text": payload.get("prize_text"),
            "top_prize_krw": payload.get("top_prize_krw"),
            "total_prize_krw": payload.get("total_prize_krw"),
            "best_prize_krw": row["top_prize_krw"],
            "status": row["status"],
            "first_seen": row["first_seen"],
            "last_seen": row["last_seen"],
            "is_new_today": bool(row["is_new_today"]) if "is_new_today" in keys else False,
            "tags": (row["tags"] or "").split("\x1f") if "tags" in keys and row["tags"] else [],
            "duplicate_count": row["dup_count"] if "dup_count" in keys else 1,
            "duplicate_sources": (
                sorted(set((row["dup_sources"] or "").split(",")))
                if "dup_sources" in keys and row["dup_sources"]
                else [row["source"]]
            ),
            "score": None,
        }

        if "total" in keys and row["total"] is not None:
            item["score"] = {
                "total": row["total"],
                "tier": row["tier"],
                "evaluator": row["evaluator"],
                "parts": _loads(row["parts_json"], {}),
                "reasons": _loads(row["reasons_json"], []),
                "risks": _loads(row["risks_json"], []),
                "estimated_workdays": row["estimated_workdays"],
                "idea_seeds": _loads(row["idea_seeds_json"], []),
                "updated_at": row["score_updated_at"] if "score_updated_at" in keys else None,
            }

        if detail:
            item["benefits"] = payload.get("benefits") or []
            item["detail_text"] = payload.get("detail_text")
        return item

    # ------------------------------------------------------------------ #
    # 목록
    # ------------------------------------------------------------------ #
    _SELECT_COLUMNS = """
        SELECT c.*,
               s.total, s.tier, s.evaluator, s.parts_json, s.reasons_json,
               s.risks_json, s.estimated_workdays, s.idea_seeds_json,
               s.updated_at AS score_updated_at,
               (date(c.first_seen, 'localtime') = date('now', 'localtime')) AS is_new_today,
               (SELECT group_concat(t.tag, char(31)) FROM contest_tags t
                 WHERE t.contest_key = c.contest_key) AS tags,
               (SELECT COUNT(*) FROM contests x
                 WHERE x.canonical_key = c.canonical_key) AS dup_count,
               (SELECT group_concat(DISTINCT x.source) FROM contests x
                 WHERE x.canonical_key = c.canonical_key) AS dup_sources"""

    _FROM_JOIN = """
          FROM contests c
          LEFT JOIN contest_scores s ON s.contest_key = c.contest_key"""

    #: 중복 그룹에서 대표 1건만 남기는 창 함수. 점수가 높은 쪽을 남긴다.
    _DEDUPE_RANK = """,
               ROW_NUMBER() OVER (
                   PARTITION BY c.canonical_key
                   ORDER BY (s.total IS NULL), s.total DESC, c.contest_key
               ) AS dup_rank"""

    def _where(self, query: ContestQuery) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        params: list[Any] = []

        if not query.include_inactive and not query.statuses:
            clauses.append(
                f"c.status NOT IN ({','.join('?' * len(INACTIVE_STATUSES))})"
            )
            params.extend(INACTIVE_STATUSES)

        if query.statuses:
            clauses.append(f"c.status IN ({','.join('?' * len(query.statuses))})")
            params.extend(query.statuses)

        if query.q:
            clauses.append("(c.title LIKE ? OR IFNULL(c.organizer,'') LIKE ?)")
            needle = f"%{query.q.strip()}%"
            params.extend([needle, needle])

        if query.tiers:
            clauses.append(f"IFNULL(s.tier,'SKIP') IN ({','.join('?' * len(query.tiers))})")
            params.extend(query.tiers)

        if query.sources:
            clauses.append(f"c.source IN ({','.join('?' * len(query.sources))})")
            params.extend(query.sources)

        if query.tags:
            clauses.append(
                "EXISTS (SELECT 1 FROM contest_tags t WHERE t.contest_key = c.contest_key "
                f"AND t.tag IN ({','.join('?' * len(query.tags))}))"
            )
            params.extend(query.tags)

        if query.min_prize:
            clauses.append("IFNULL(c.top_prize_krw, 0) >= ?")
            params.append(int(query.min_prize))

        if query.deadline_within is not None:
            limit = (self.today + timedelta(days=query.deadline_within)).isoformat()
            clauses.append("c.deadline IS NOT NULL AND c.deadline BETWEEN ? AND ?")
            params.extend([self.today.isoformat(), limit])

        if query.only_new_today:
            clauses.append("date(c.first_seen, 'localtime') = date('now', 'localtime')")

        return (" WHERE " + " AND ".join(clauses)) if clauses else "", params

    def list_contests(self, query: ContestQuery) -> dict[str, Any]:
        where, params = self._where(query)

        column = SORT_COLUMNS.get(query.sort, "s.total")
        plain = column.split(".", 1)[1]
        direction = "DESC" if query.order.lower() == "desc" else "ASC"

        page_size = max(1, min(200, query.page_size))
        offset = max(0, (max(1, query.page) - 1) * page_size)

        if query.collapse_duplicates:
            inner = f"{self._SELECT_COLUMNS}{self._DEDUPE_RANK}{self._FROM_JOIN}{where}"
            # NULL은 항상 뒤로. 점수 없는 공모전이 목록 맨 위에 오면 안 된다.
            order_by = f"({plain} IS NULL), {plain} {direction}, first_seen DESC"
            count_sql = f"SELECT COUNT(*) AS n FROM ({inner}) WHERE dup_rank = 1"
            list_sql = (
                f"SELECT * FROM ({inner}) WHERE dup_rank = 1 "
                f"ORDER BY {order_by} LIMIT ? OFFSET ?"
            )
        else:
            order_by = f"({column} IS NULL), {column} {direction}, c.first_seen DESC"
            count_sql = f"SELECT COUNT(*) AS n{self._FROM_JOIN}{where}"
            list_sql = (
                f"{self._SELECT_COLUMNS}{self._FROM_JOIN}{where} "
                f"ORDER BY {order_by} LIMIT ? OFFSET ?"
            )

        total = self.conn.execute(count_sql, params).fetchone()["n"]
        rows = self.conn.execute(list_sql, [*params, page_size, offset]).fetchall()

        return {
            "items": [self._row_to_contest(r) for r in rows],
            "total": total,
            "page": max(1, query.page),
            "page_size": page_size,
            "has_more": offset + len(rows) < total,
        }

    def get_contest(self, key: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            f"{self._SELECT_COLUMNS}{self._FROM_JOIN} WHERE c.contest_key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        item = self._row_to_contest(row, detail=True)
        item["project"] = self.get_project(key)
        item["history"] = [
            dict(r)
            for r in self.conn.execute(
                "SELECT from_status, to_status, created_at FROM status_events "
                "WHERE contest_key = ? ORDER BY id DESC LIMIT 20",
                (key,),
            ).fetchall()
        ]
        return item

    # ------------------------------------------------------------------ #
    # 상태 전환
    # ------------------------------------------------------------------ #
    def set_status(self, key: str, status: ContestStatus) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT c.status, s.tier FROM contests c "
            "LEFT JOIN contest_scores s ON s.contest_key = c.contest_key "
            "WHERE c.contest_key = ?",
            (key,),
        ).fetchone()
        if row is None:
            return None
        if not self.db.set_status(key, status):
            return None
        self.conn.execute(
            "INSERT INTO status_events(contest_key, from_status, to_status, tier, created_at) "
            "VALUES(?,?,?,?,?)",
            (key, row["status"], status.value, row["tier"], _now()),
        )
        self.conn.commit()
        return self.get_contest(key)

    # ------------------------------------------------------------------ #
    # 대시보드
    # ------------------------------------------------------------------ #
    def _scalar(self, sql: str, params: Sequence[Any] = ()) -> int:
        return int(self.conn.execute(sql, params).fetchone()[0] or 0)

    def dashboard(self) -> dict[str, Any]:
        today = self.today.isoformat()
        inactive = ",".join("?" * len(INACTIVE_STATUSES))

        new_today = self._scalar(
            "SELECT COUNT(*) FROM contests "
            "WHERE date(first_seen, 'localtime') = date('now', 'localtime')"
        )
        active = self._scalar(
            f"SELECT COUNT(*) FROM contests WHERE status NOT IN ({inactive}) "
            "AND (deadline IS NULL OR deadline >= ?)",
            (*INACTIVE_STATUSES, today),
        )
        s_tier = self._scalar(
            f"SELECT COUNT(*) FROM contests c JOIN contest_scores s "
            f"ON s.contest_key = c.contest_key WHERE s.tier = 'S' "
            f"AND c.status NOT IN ({inactive}) AND (c.deadline IS NULL OR c.deadline >= ?)",
            (*INACTIVE_STATUSES, today),
        )
        ending_soon = self._scalar(
            f"SELECT COUNT(*) FROM contests WHERE status NOT IN ({inactive}) "
            "AND deadline IS NOT NULL AND deadline BETWEEN ? AND ?",
            (*INACTIVE_STATUSES, today, (self.today + timedelta(days=7)).isoformat()),
        )

        top = self.list_contests(
            ContestQuery(
                tiers=["S", "A", "B"],
                sort="score",
                order="desc",
                page_size=5,
                deadline_within=None,
            )
        )["items"]
        top = [t for t in top if t["days_left"] is None or t["days_left"] >= 0][:5]

        matrix_rows = self.conn.execute(
            f"""
            SELECT c.contest_key, c.title, c.organizer, c.top_prize_krw, c.deadline,
                   s.total, s.tier, s.parts_json
              FROM contests c JOIN contest_scores s ON s.contest_key = c.contest_key
             WHERE c.status NOT IN ({inactive})
               AND (c.deadline IS NULL OR c.deadline >= ?)
             ORDER BY s.total DESC LIMIT 120
            """,
            (*INACTIVE_STATUSES, today),
        ).fetchall()

        matrix = []
        for row in matrix_rows:
            parts = _loads(row["parts_json"], {})
            matrix.append(
                {
                    "key": row["contest_key"],
                    "title": row["title"],
                    "organizer": row["organizer"],
                    "tier": row["tier"],
                    "total": row["total"],
                    # X축: 수상 가능성(15점 만점) → 0~100 정규화
                    "win": round(parts.get("win_probability", 0) / 15 * 100),
                    # Y축: 상금·수상가치(20) + 포트폴리오 가치(5) → 0~100 정규화
                    "value": round(
                        (parts.get("award_value", 0) + parts.get("portfolio_value", 0))
                        / 25
                        * 100
                    ),
                    "prize": row["top_prize_krw"],
                    "days_left": _days_left(row["deadline"], self.today),
                }
            )

        last_run = self.conn.execute(
            "SELECT id, started_at, finished_at, status, total_new FROM crawl_runs "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()

        return {
            "kpi": {
                "new_today": new_today,
                "s_tier": s_tier,
                "ending_soon": ending_soon,
                "active_contests": active,
            },
            "top_opportunities": top,
            "matrix": matrix,
            "new_contests": self.list_contests(
                ContestQuery(only_new_today=True, sort="score", page_size=20)
            )["items"],
            "last_run": dict(last_run) if last_run else None,
            "has_any_data": self._scalar("SELECT COUNT(*) FROM contests") > 0,
        }

    # ------------------------------------------------------------------ #
    # 필터 후보값
    # ------------------------------------------------------------------ #
    def facets(self) -> dict[str, Any]:
        tag_rows = self.conn.execute(
            "SELECT t.tag, COUNT(*) AS n FROM contest_tags t "
            "JOIN contests c ON c.contest_key = t.contest_key "
            "GROUP BY t.tag ORDER BY n DESC"
        ).fetchall()
        counts = {r["tag"]: r["n"] for r in tag_rows}
        tags = [
            {"tag": tag, "count": counts[tag]} for tag in DISPLAY_ORDER if tag in counts
        ]
        sources = [
            {"source": r["source"], "count": r["n"]}
            for r in self.conn.execute(
                "SELECT source, COUNT(*) AS n FROM contests GROUP BY source ORDER BY n DESC"
            ).fetchall()
        ]
        statuses = {
            r["status"]: r["n"]
            for r in self.conn.execute(
                "SELECT status, COUNT(*) AS n FROM contests GROUP BY status"
            ).fetchall()
        }
        tiers = {
            r["tier"]: r["n"]
            for r in self.conn.execute(
                "SELECT tier, COUNT(*) AS n FROM contest_scores GROUP BY tier"
            ).fetchall()
        }
        return {"tags": tags, "sources": sources, "statuses": statuses, "tiers": tiers}

    # ------------------------------------------------------------------ #
    # Analytics
    # ------------------------------------------------------------------ #
    def analytics(self) -> dict[str, Any]:
        week_ago = (self.today - timedelta(days=7)).isoformat()
        two_weeks = (self.today - timedelta(days=14)).isoformat()

        this_week = self._scalar(
            "SELECT COUNT(*) FROM contests WHERE date(first_seen,'localtime') > ?", (week_ago,)
        )
        last_week = self._scalar(
            "SELECT COUNT(*) FROM contests "
            "WHERE date(first_seen,'localtime') > ? AND date(first_seen,'localtime') <= ?",
            (two_weeks, week_ago),
        )

        discovery_daily = [
            {"date": r["d"], "count": r["n"]}
            for r in self.conn.execute(
                "SELECT date(first_seen,'localtime') AS d, COUNT(*) AS n FROM contests "
                "WHERE date(first_seen,'localtime') > ? GROUP BY d ORDER BY d",
                ((self.today - timedelta(days=29)).isoformat(),),
            ).fetchall()
        ]

        categories = [
            {"name": r["tag"], "count": r["n"]}
            for r in self.conn.execute(
                "SELECT tag, COUNT(*) AS n FROM contest_tags GROUP BY tag "
                "ORDER BY n DESC LIMIT 8"
            ).fetchall()
        ]

        tiers = {
            r["tier"]: r["n"]
            for r in self.conn.execute(
                "SELECT tier, COUNT(*) AS n FROM contest_scores GROUP BY tier"
            ).fetchall()
        }
        recommended = sum(tiers.get(t, 0) for t in ("S", "A", "B"))
        ignored = self._scalar(
            "SELECT COUNT(*) FROM contests WHERE status = ?", (ContestStatus.IGNORE.value,)
        )

        prize_buckets = [
            ("상금 미확인", "IFNULL(top_prize_krw,0) = 0"),
            ("~100만원", "top_prize_krw > 0 AND top_prize_krw < 1000000"),
            ("100~300만원", "top_prize_krw >= 1000000 AND top_prize_krw < 3000000"),
            ("300~500만원", "top_prize_krw >= 3000000 AND top_prize_krw < 5000000"),
            ("500~1000만원", "top_prize_krw >= 5000000 AND top_prize_krw < 10000000"),
            ("1000만원 이상", "top_prize_krw >= 10000000"),
        ]
        prize_distribution = [
            {"name": label, "count": self._scalar(f"SELECT COUNT(*) FROM contests WHERE {cond}")}
            for label, cond in prize_buckets
        ]

        today_s = self.today.isoformat()
        deadline_buckets = [
            ("D-7 이내", 0, 7),
            ("D-8~14", 8, 14),
            ("D-15~30", 15, 30),
            ("D-31~60", 31, 60),
            ("D-60 초과", 61, 3650),
        ]
        deadline_distribution = []
        for label, lo, hi in deadline_buckets:
            start = (self.today + timedelta(days=lo)).isoformat()
            end = (self.today + timedelta(days=hi)).isoformat()
            deadline_distribution.append(
                {
                    "name": label,
                    "count": self._scalar(
                        "SELECT COUNT(*) FROM contests WHERE deadline BETWEEN ? AND ? "
                        "AND status NOT IN (?,?)",
                        (start, end, *INACTIVE_STATUSES),
                    ),
                }
            )

        sources = [
            {"name": r["source"], "count": r["n"]}
            for r in self.conn.execute(
                "SELECT source, COUNT(*) AS n FROM contests GROUP BY source ORDER BY n DESC"
            ).fetchall()
        ]

        selected = ",".join("?" * len(SELECTED_STATUSES))
        s_total = self._scalar("SELECT COUNT(*) FROM contest_scores WHERE tier = 'S'")
        s_selected = self._scalar(
            f"SELECT COUNT(*) FROM contests c JOIN contest_scores s "
            f"ON s.contest_key = c.contest_key "
            f"WHERE s.tier = 'S' AND c.status IN ({selected})",
            SELECTED_STATUSES,
        )
        video_total = self._scalar(
            "SELECT COUNT(*) FROM contest_tags WHERE tag = '영상'"
        )
        video_selected = self._scalar(
            f"SELECT COUNT(*) FROM contests c JOIN contest_tags t "
            f"ON t.contest_key = c.contest_key "
            f"WHERE t.tag = '영상' AND c.status IN ({selected})",
            SELECTED_STATUSES,
        )
        avg_prize_row = self.conn.execute(
            f"SELECT AVG(top_prize_krw) AS avg FROM contests "
            f"WHERE status IN ({selected}) AND top_prize_krw > 0",
            SELECTED_STATUSES,
        ).fetchone()
        selected_count = self._scalar(
            f"SELECT COUNT(*) FROM contests WHERE status IN ({selected})",
            SELECTED_STATUSES,
        )

        return {
            "discovery": {
                "this_week": this_week,
                "last_week": last_week,
                "delta_pct": (
                    round((this_week - last_week) / last_week * 100)
                    if last_week
                    else None
                ),
                "daily": discovery_daily,
            },
            "categories": categories,
            "tiers": [
                {"name": t, "count": tiers.get(t, 0)} for t in ("S", "A", "B", "SKIP")
            ],
            "recommended_vs_ignored": {"recommended": recommended, "ignored": ignored},
            "prize_distribution": prize_distribution,
            "deadline_distribution": deadline_distribution,
            "sources": sources,
            "selection": {
                "s_tier_shortlist_rate": (
                    round(s_selected / s_total * 100) if s_total else None
                ),
                "s_tier_total": s_total,
                "video_selection_rate": (
                    round(video_selected / video_total * 100) if video_total else None
                ),
                "video_total": video_total,
                "avg_selected_prize": (
                    int(avg_prize_row["avg"]) if avg_prize_row and avg_prize_row["avg"] else None
                ),
                "selected_count": selected_count,
            },
        }

    # ------------------------------------------------------------------ #
    # 실행 이력 / 소스
    # ------------------------------------------------------------------ #
    def runs(self, limit: int = 30) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM crawl_runs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [self._run_row(r) for r in rows]

    def run(self, run_id: int) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM crawl_runs WHERE id = ?", (run_id,)
        ).fetchone()
        return self._run_row(row) if row else None

    def _run_row(self, row: sqlite3.Row) -> dict[str, Any]:
        stats = _loads(row["stats_json"], {})
        keys = row.keys()
        duration = None
        if row["started_at"] and row["finished_at"]:
            duration = self.conn.execute(
                "SELECT (julianday(?) - julianday(?)) * 86400.0 AS s",
                (row["finished_at"], row["started_at"]),
            ).fetchone()["s"]
        return {
            "id": row["id"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "status": row["status"] if "status" in keys else "SUCCESS",
            "trigger": row["trigger"] if "trigger" in keys else "cli",
            "sources": [s for s in (row["sources"] or "").split(",") if s],
            "total_new": row["total_new"],
            "total_seen": row["total_seen"],
            "requests": row["requests"],
            "duration_sec": round(duration, 1) if duration is not None else None,
            "stats": stats,
            "errors": _loads(row["error_json"] if "error_json" in keys else None, []),
            "new_titles": [
                {"key": r["contest_key"], "title": r["title"], "tier": r["tier"], "total": r["total"]}
                for r in self.conn.execute(
                    "SELECT r.contest_key, r.tier, r.total, c.title FROM recommendations r "
                    "JOIN contests c ON c.contest_key = r.contest_key "
                    "WHERE r.run_id = ? ORDER BY r.total DESC LIMIT 10",
                    (row["id"],),
                ).fetchall()
            ],
        }

    def sources_overview(self) -> list[dict[str, Any]]:
        from contest_scout.sources import SOURCES

        overview = []
        for name, cls in SOURCES.items():
            last = self.conn.execute(
                "SELECT id, started_at, finished_at, status, stats_json FROM crawl_runs "
                "WHERE sources LIKE ? ORDER BY id DESC LIMIT 1",
                (f"%{name}%",),
            ).fetchone()
            stats = _loads(last["stats_json"], {}).get(name) if last else None
            stored = self._scalar(
                "SELECT COUNT(*) FROM contests WHERE source = ?", (name,)
            )
            overview.append(
                {
                    "name": name,
                    "entry_url": cls.entry_url,
                    "needs_detail_request": cls.needs_detail_request,
                    "stored_contests": stored,
                    "last_checked": last["finished_at"] or last["started_at"] if last else None,
                    "last_status": (last["status"] if last else None),
                    "robots": (stats or {}).get("robots"),
                    "last_discovered": (stats or {}).get("discovered"),
                    "last_new": (stats or {}).get("new"),
                    "skipped_reason": (stats or {}).get("skipped_reason"),
                    "errors": (stats or {}).get("errors", 0),
                }
            )
        return overview

    # ------------------------------------------------------------------ #
    # 프로젝트 (Contest Builder 연결)
    # ------------------------------------------------------------------ #
    def get_project(self, contest_key: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM projects WHERE contest_key = ?", (contest_key,)
        ).fetchone()
        return self._project_row(row) if row else None

    def _project_row(self, row: sqlite3.Row) -> dict[str, Any]:
        stage = row["stage"]
        index = PROJECT_STAGES.index(stage) if stage in PROJECT_STAGES else 0
        return {
            "id": row["id"],
            "contest_key": row["contest_key"],
            "title": row["title"],
            "brief": row["brief"],
            "deadline": row["deadline"],
            "requirements": row["requirements"],
            "stage": stage,
            "stage_index": index,
            "stage_count": len(PROJECT_STAGES),
            "progress": round((index + 1) / len(PROJECT_STAGES) * 100),
            "next_action": row["next_action"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "days_left": _days_left(row["deadline"], self.today),
        }

    def list_projects(self) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM projects ORDER BY (deadline IS NULL), deadline"
        ).fetchall()
        return [self._project_row(r) for r in rows]

    def create_project(self, contest_key: str) -> dict[str, Any] | None:
        contest_row = self.conn.execute(
            "SELECT payload_json, title, deadline FROM contests WHERE contest_key = ?",
            (contest_key,),
        ).fetchone()
        if contest_row is None:
            return None
        contest = contest_from_payload(_loads(contest_row["payload_json"], {}))
        brief = (contest.detail_text or "")[:2000] or None
        requirements = " / ".join(contest.eligibility) or None
        now = _now()
        self.conn.execute(
            """
            INSERT INTO projects(contest_key, title, brief, deadline, requirements,
                                 stage, next_action, created_at, updated_at)
            VALUES(?,?,?,?,?,?,?,?,?)
            ON CONFLICT(contest_key) DO UPDATE SET
                title = excluded.title, brief = excluded.brief,
                deadline = excluded.deadline, requirements = excluded.requirements,
                updated_at = excluded.updated_at
            """,
            (
                contest_key,
                contest.title,
                brief,
                contest_row["deadline"],
                requirements,
                PROJECT_STAGES[0],
                "공모 요강 정독 및 레퍼런스 수집",
                now,
                now,
            ),
        )
        self.conn.commit()
        return self.get_project(contest_key)

    def update_project(
        self, contest_key: str, *, stage: str | None = None, next_action: str | None = None
    ) -> dict[str, Any] | None:
        if stage is not None and stage not in PROJECT_STAGES:
            raise ValueError(f"알 수 없는 단계: {stage}")
        sets, params = [], []
        if stage is not None:
            sets.append("stage = ?")
            params.append(stage)
        if next_action is not None:
            sets.append("next_action = ?")
            params.append(next_action)
        if not sets:
            return self.get_project(contest_key)
        sets.append("updated_at = ?")
        params.extend([_now(), contest_key])
        cur = self.conn.execute(
            f"UPDATE projects SET {', '.join(sets)} WHERE contest_key = ?", params
        )
        self.conn.commit()
        return self.get_project(contest_key) if cur.rowcount else None

    def delete_project(self, contest_key: str) -> bool:
        cur = self.conn.execute("DELETE FROM projects WHERE contest_key = ?", (contest_key,))
        self.conn.commit()
        return cur.rowcount > 0

    # ------------------------------------------------------------------ #
    # 태그 유지보수
    # ------------------------------------------------------------------ #
    def replace_tags(self, contest_key: str, tags: Iterable[str]) -> None:
        self.conn.execute("DELETE FROM contest_tags WHERE contest_key = ?", (contest_key,))
        self.conn.executemany(
            "INSERT OR IGNORE INTO contest_tags(contest_key, tag) VALUES(?,?)",
            [(contest_key, tag) for tag in tags],
        )

    def untagged_keys(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT contest_key FROM contests WHERE contest_key NOT IN "
            "(SELECT DISTINCT contest_key FROM contest_tags)"
        ).fetchall()
        return [r["contest_key"] for r in rows]

    def unscored_keys(self, profile_hash: str | None = None) -> list[str]:
        if profile_hash is None:
            rows = self.conn.execute(
                "SELECT contest_key FROM contests WHERE contest_key NOT IN "
                "(SELECT contest_key FROM contest_scores)"
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT c.contest_key FROM contests c "
                "LEFT JOIN contest_scores s ON s.contest_key = c.contest_key "
                "WHERE s.contest_key IS NULL OR IFNULL(s.profile_hash,'') != ?",
                (profile_hash,),
            ).fetchall()
        return [r["contest_key"] for r in rows]


__all__ = ["ContestQuery", "Repository", "SORT_COLUMNS", "TIER_RANK"]
