"""Scout 실행 서비스 — CLI와 대시보드가 **같은** 코드를 쓴다.

``run_scout`` 하나가 한 회차의 전부를 담당한다.

    마감 정리 → 소스 구성 → incremental crawl → 추천 표시
             → 점수/태그 동기화 → Markdown 리포트

대시보드의 ``Run Scout`` 버튼은 이 함수를 백그라운드 스레드에서 호출하고,
:class:`ScoutRunner` 가 진행 상황을 들고 있다가 프론트엔드에 넘긴다. 즉 버튼은
가짜가 아니라 CLI와 동일한 수집기를 돌린다.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from contest_scout import paths
from contest_scout.crawl import CrawlResult, crawl
from contest_scout.db import Database, contest_from_payload
from contest_scout.evaluators.rules import RuleEvaluator
from contest_scout.http import DEFAULT_USER_AGENT, SafeHttpClient
from contest_scout.report import render_markdown
from contest_scout.repository import Repository
from contest_scout.schema_ext import upsert_score
from contest_scout.services.settings import AppSettings, current_profile, load_settings, profile_hash
from contest_scout.sources import build_sources
from contest_scout.taxonomy import tags_for

log = logging.getLogger(__name__)

ProgressFn = Callable[[str, dict[str, Any]], None]


# ---------------------------------------------------------------------- #
# 점수 / 태그 동기화
# ---------------------------------------------------------------------- #
def sync_scores(
    db: Database,
    *,
    force: bool = False,
    on_progress: Callable[[int, int], None] | None = None,
) -> int:
    """점수·태그가 없거나 프로필이 바뀐 공모전을 다시 채점한다.

    수집(crawl)은 신규 공모전만 평가한다. 대시보드는 DB 전체를 점수로 정렬해야
    하므로, 과거에 수집만 되고 평가 기록이 없는 건까지 여기서 메꾼다.
    """
    profile = current_profile()
    digest = profile_hash(profile)
    evaluator = RuleEvaluator(profile)
    repo = Repository(db)

    if force:
        keys = [
            r["contest_key"]
            for r in db.conn.execute("SELECT contest_key FROM contests").fetchall()
        ]
    else:
        keys = sorted(set(repo.unscored_keys(digest)) | set(repo.untagged_keys()))

    if not keys:
        return 0

    total = len(keys)
    for index, key in enumerate(keys, start=1):
        row = db.conn.execute(
            "SELECT payload_json FROM contests WHERE contest_key = ?", (key,)
        ).fetchone()
        if row is None:
            continue
        import json as _json

        contest = contest_from_payload(_json.loads(row["payload_json"]))
        upsert_score(db.conn, key, evaluator.evaluate(contest), digest)
        repo.replace_tags(key, tags_for(contest))
        if on_progress and index % 25 == 0:
            on_progress(index, total)
    db.conn.commit()
    log.info("점수/태그 동기화 %s건", total)
    return total


# ---------------------------------------------------------------------- #
# 한 회차 실행
# ---------------------------------------------------------------------- #
@dataclass(slots=True)
class ScoutOutcome:
    run_id: int
    status: str
    result: CrawlResult | None
    report_path: str | None
    expired: int = 0
    rescored: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)


def _classify(result: CrawlResult) -> tuple[str, list[dict[str, str]]]:
    errors: list[dict[str, str]] = []
    ok = 0
    for stats in result.stats:
        if stats.skipped_reason:
            errors.append({"source": stats.source, "reason": stats.skipped_reason})
        elif stats.errors:
            errors.append(
                {"source": stats.source, "reason": f"수집 중 오류 {stats.errors}건"}
            )
        else:
            ok += 1
    if not errors:
        return "SUCCESS", errors
    return ("PARTIAL" if ok else "FAILED"), errors


def run_scout(
    *,
    settings: AppSettings | None = None,
    db_path: str | Path | None = None,
    report: str | Path | None = None,
    source_selection: str | None = None,
    pages: int | None = None,
    limit: int | None = None,
    on_event: ProgressFn | None = None,
    trigger: str = "cli",
    profile: Any | None = None,
) -> ScoutOutcome:
    """한 회차 수집·평가·리포트. CLI와 API가 공유하는 진입점."""
    settings = settings or load_settings()
    profile = profile or current_profile()
    digest = profile_hash(profile)

    db_file = Path(db_path) if db_path else paths.db_path()
    report_file = Path(report) if report else paths.report_path()
    db_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.parent.mkdir(parents=True, exist_ok=True)

    selection = source_selection or settings.source_selection
    crawl_cfg = settings.crawl

    with Database(db_file) as db:
        run_id = db.start_run(
            [s.strip() for s in selection.split(",")] if selection != "all" else ["all"]
        )
        db.conn.execute(
            "UPDATE crawl_runs SET status = 'RUNNING', trigger = ? WHERE id = ?",
            (trigger, run_id),
        )
        db.conn.commit()

        if on_event:
            on_event("run_created", {"run_id": run_id})

        expired = db.expire_past_deadline()
        try:
            with SafeHttpClient(
                delay=crawl_cfg.delay,
                timeout=crawl_cfg.timeout,
                respect_robots=crawl_cfg.respect_robots,
                user_agent=crawl_cfg.user_agent or DEFAULT_USER_AGENT,
            ) as http:
                sources = build_sources(selection, http)
                # 목록 페이지에 실제로 넣을 소스 이름으로 갱신 (all → 실제 목록)
                db.conn.execute(
                    "UPDATE crawl_runs SET sources = ? WHERE id = ?",
                    (",".join(s.name for s in sources), run_id),
                )
                db.conn.commit()

                result = crawl(
                    sources,
                    http,
                    db,
                    RuleEvaluator(profile),
                    pages=pages if pages is not None else crawl_cfg.pages,
                    limit=limit if limit is not None else crawl_cfg.limit,
                    on_event=on_event,
                    run_id=run_id,
                    profile_hash=digest,
                )
        except Exception as exc:  # noqa: BLE001 - 실패도 기록으로 남긴다
            log.exception("scout 실행 실패")
            errors = [{"source": selection, "reason": f"{type(exc).__name__}: {exc}"}]
            _finalize_run(db, run_id, "FAILED", errors)
            if on_event:
                on_event("run_failed", {"run_id": run_id, "reason": str(exc)})
            return ScoutOutcome(run_id, "FAILED", None, None, expired, 0, errors)

        suppressed = db.suppressed_canonical_keys()
        recommended = [
            key
            for key, evaluation in result.evaluations.items()
            if evaluation.tier != "SKIP" and key not in suppressed
        ]
        db.mark_recommended(recommended)

        rescored = sync_scores(db)
        report_path = render_markdown(result, report_file)

        status, errors = _classify(result)
        _finalize_run(db, run_id, status, errors)

        if on_event:
            on_event(
                "run_completed",
                {"run_id": run_id, "status": status, "total_new": result.total_new},
            )

    return ScoutOutcome(
        run_id=run_id,
        status=status,
        result=result,
        report_path=str(report_path),
        expired=expired,
        rescored=rescored,
        errors=errors,
    )


def _finalize_run(db: Database, run_id: int, status: str, errors: list[dict[str, str]]) -> None:
    import json as _json

    db.conn.execute(
        "UPDATE crawl_runs SET status = ?, error_json = ?, "
        "finished_at = COALESCE(finished_at, ?) WHERE id = ?",
        (
            status,
            _json.dumps(errors, ensure_ascii=False),
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
            run_id,
        ),
    )
    db.conn.commit()


# ---------------------------------------------------------------------- #
# 대시보드용 백그라운드 실행기
# ---------------------------------------------------------------------- #
@dataclass
class RunnerState:
    """`Run Scout` 진행 상태. 프론트엔드가 폴링해서 그대로 그린다."""

    phase: str = "idle"  # idle | running | done | failed
    run_id: int | None = None
    started_at: str | None = None
    finished_at: str | None = None
    trigger: str = "manual"
    sources: dict[str, str] = field(default_factory=dict)  # name -> pending|scanning|done|failed
    source_stats: dict[str, dict[str, Any]] = field(default_factory=dict)
    new_contests: list[dict[str, Any]] = field(default_factory=list)
    status: str | None = None
    message: str | None = None
    errors: list[dict[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "run_id": self.run_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "trigger": self.trigger,
            "sources": self.sources,
            "source_stats": self.source_stats,
            "new_contests": self.new_contests,
            "status": self.status,
            "message": self.message,
            "errors": self.errors,
        }


class ScoutRunner:
    """Scout 실행을 한 번에 하나만 돌리고, 진행 상황을 들고 있는다."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self.state = RunnerState()

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return self.state.as_dict()

    def start(self, *, trigger: str = "manual", **kwargs: Any) -> dict[str, Any]:
        with self._lock:
            if self.is_running:
                return {"started": False, "reason": "already_running", "state": self.state.as_dict()}
            settings = kwargs.pop("settings", None) or load_settings()
            names = (
                settings.enabled_sources
                if settings.enabled_sources
                else ["thinkgood", "linkareer"]
            )
            self.state = RunnerState(
                phase="running",
                started_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                trigger=trigger,
                sources={name: "pending" for name in names},
                message="수집을 준비하고 있습니다",
            )
            self._thread = threading.Thread(
                target=self._run,
                kwargs={"settings": settings, "trigger": trigger, **kwargs},
                daemon=True,
                name="scout-runner",
            )
            self._thread.start()
        return {"started": True, "state": self.snapshot()}

    # ------------------------------------------------------------------ #
    def _on_event(self, kind: str, payload: dict[str, Any]) -> None:
        with self._lock:
            state = self.state
            if kind == "run_created":
                state.run_id = payload.get("run_id")
            elif kind == "run_started":
                for name in payload.get("sources", []):
                    state.sources.setdefault(name, "pending")
                state.message = "소스를 확인하고 있습니다"
            elif kind == "source_started":
                state.sources[payload["source"]] = "scanning"
                state.message = f"{payload['source']} 수집 중"
            elif kind == "page_done":
                state.message = (
                    f"{payload['source']} · {payload['discovered']}건 확인"
                )
            elif kind == "contest_new":
                state.new_contests.append(
                    {
                        "title": payload.get("title"),
                        "tier": payload.get("tier"),
                        "total": payload.get("total"),
                        "source": payload.get("source"),
                    }
                )
            elif kind == "source_finished":
                stats = payload.get("stats") or {}
                state.source_stats[payload["source"]] = stats
                failed = bool(stats.get("skipped_reason")) or bool(stats.get("errors"))
                state.sources[payload["source"]] = "failed" if failed else "done"
            elif kind == "run_completed":
                state.status = payload.get("status")
            elif kind == "run_failed":
                state.status = "FAILED"
                state.message = payload.get("reason")

    def _run(self, **kwargs: Any) -> None:
        started = time.monotonic()
        try:
            outcome = run_scout(on_event=self._on_event, **kwargs)
        except Exception as exc:  # noqa: BLE001
            log.exception("scout runner 예외")
            with self._lock:
                self.state.phase = "failed"
                self.state.status = "FAILED"
                self.state.message = f"{type(exc).__name__}: {exc}"
                self.state.finished_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            return

        with self._lock:
            self.state.phase = "done" if outcome.status != "FAILED" else "failed"
            self.state.run_id = outcome.run_id
            self.state.status = outcome.status
            self.state.errors = outcome.errors
            self.state.finished_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            new_count = outcome.result.total_new if outcome.result else 0
            s_tier = sum(
                1
                for evaluation in (outcome.result.evaluations.values() if outcome.result else [])
                if evaluation.tier == "S"
            )
            elapsed = round(time.monotonic() - started, 1)
            if outcome.status == "FAILED":
                self.state.message = "수집에 실패했습니다"
            else:
                self.state.message = (
                    f"신규 공모전 {new_count}건 발견 · S등급 {s_tier}건 ({elapsed}초)"
                )


#: 프로세스당 하나. 동시에 두 번 돌지 않도록 막는 역할도 겸한다.
runner = ScoutRunner()


__all__ = ["RunnerState", "ScoutOutcome", "ScoutRunner", "run_scout", "runner", "sync_scores"]
