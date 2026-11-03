"""Incremental crawl 오케스트레이터.

핵심 원칙: **어제 이후 새로 올라온 공모전만 상세 조회한다.**

    목록 요청 1회
        ↓
    ContestRef 목록
        ↓
    DB의 known_keys와 비교
        ↓
    이미 아는 것 → last_seen만 갱신 (요청 0회)
    신규        → fetch_detail (소스에 따라 요청 0~1회)
        ↓
    정규화 → DB 저장 → 평가
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from contest_scout.db import Database
from contest_scout.evaluators.base import Evaluation, Evaluator
from contest_scout.http import RobotsDisallowed, RobotsUnknown, SafeHttpClient
from contest_scout.models import Contest, ParseWarning, SourceStats
from contest_scout.sources.base import BaseSource

log = logging.getLogger(__name__)


@dataclass(slots=True)
class CrawlResult:
    run_id: int
    stats: list[SourceStats] = field(default_factory=list)
    new_contests: list[Contest] = field(default_factory=list)
    evaluations: dict[str, Evaluation] = field(default_factory=dict)
    warnings: list[ParseWarning] = field(default_factory=list)
    total_requests: int = 0

    @property
    def total_new(self) -> int:
        return len(self.new_contests)

    @property
    def total_seen(self) -> int:
        return sum(s.discovered for s in self.stats)


def crawl(
    sources: Sequence[BaseSource],
    http: SafeHttpClient,
    db: Database,
    evaluator: Evaluator,
    *,
    pages: int = 1,
    limit: int | None = None,
    stop_on_known: bool = True,
    on_event: Callable[[str, dict[str, Any]], None] | None = None,
    run_id: int | None = None,
    profile_hash: str | None = None,
) -> CrawlResult:
    """소스들을 순회하며 신규 공모전만 수집·평가한다.

    ``stop_on_known`` 이 참이면, 목록이 등록일 역순인 소스에서 이미 아는 공모전이
    연속으로 나오면 다음 페이지를 요청하지 않는다.

    ``on_event`` 는 진행 상황을 실시간으로 알리기 위한 선택적 콜백이다. 대시보드의
    "Thinkgood ● scanning" 표시가 이 콜백을 쓴다. CLI는 넘기지 않으므로 동작은
    이전과 동일하다.
    """

    def emit(kind: str, **payload: Any) -> None:
        if on_event is not None:
            try:
                on_event(kind, payload)
            except Exception:  # noqa: BLE001 - 진행 표시가 수집을 막으면 안 된다
                log.debug("on_event 콜백 실패", exc_info=True)

    if run_id is None:
        run_id = db.start_run([s.name for s in sources])
    result = CrawlResult(run_id=run_id)
    emit("run_started", run_id=run_id, sources=[s.name for s in sources])

    for source in sources:
        stats = SourceStats(source=source.name)
        result.stats.append(stats)
        before_requests = http.request_count
        emit("source_started", source=source.name)

        # robots.txt 판정 — ALLOW/DENY/UNKNOWN 3상태를 그대로 기록한다.
        report = http.robots.check(source.entry_url)
        stats.robots = report.state.value
        if stats.robots != "ALLOW":
            stats.skipped_reason = f"robots {report}"
            log.warning("[%s] SKIP: %s", source.name, report)
            stats.requests = http.request_count - before_requests
            emit(
                "source_finished",
                source=source.name,
                stats=stats.as_jsonable(),
                reason="robots",
            )
            continue

        known = db.known_keys(source.name)
        collected = 0
        seen_keys: list[str] = []

        for page in range(1, max(1, pages) + 1):
            try:
                refs = source.discover(page=page)
            except (RobotsDisallowed, RobotsUnknown) as exc:
                stats.skipped_reason = str(exc)
                log.warning("[%s] SKIP: %s", source.name, exc)
                break
            except Exception as exc:  # noqa: BLE001 - 한 소스 실패가 전체를 막지 않는다
                stats.errors += 1
                log.error("[%s] 목록 실패(page %s): %s", source.name, page, exc)
                break

            stats.list_pages += 1
            stats.discovered += len(refs)
            emit("page_done", source=source.name, page=page, discovered=len(refs))
            if not refs:
                break

            page_new = 0
            for ref in refs:
                if limit is not None and collected >= limit:
                    break
                if ref.key in known:
                    stats.existing += 1
                    seen_keys.append(ref.key)
                    continue

                page_new += 1
                try:
                    contest = source.fetch_detail(ref)
                except Exception as exc:  # noqa: BLE001
                    stats.errors += 1
                    log.error("[%s] 상세 실패 %s: %s", source.name, ref.url, exc)
                    continue

                if source.needs_detail_request:
                    stats.details_fetched += 1

                for warning in contest.warnings:
                    result.warnings.append(warning)
                    log.info("%s", warning)

                is_new = db.upsert(contest)
                if is_new:
                    stats.new += 1
                    collected += 1
                    result.new_contests.append(contest)
                    evaluation = evaluator.evaluate(contest)
                    result.evaluations[contest.key] = evaluation
                    emit(
                        "contest_new",
                        source=source.name,
                        title=contest.title,
                        tier=evaluation.tier,
                        total=evaluation.total,
                    )
                else:
                    stats.existing += 1
                known.add(ref.key)

            if limit is not None and collected >= limit:
                break
            if stop_on_known and page_new == 0 and page > 1:
                break

        db.touch(seen_keys)
        stats.requests = http.request_count - before_requests
        emit("source_finished", source=source.name, stats=stats.as_jsonable())

    result.total_requests = sum(s.requests for s in result.stats)
    db.finish_run(
        run_id,
        total_new=result.total_new,
        total_seen=result.total_seen,
        requests=result.total_requests,
        stats={s.source: s.as_jsonable() for s in result.stats},
    )
    for key, evaluation in result.evaluations.items():
        db.save_recommendation(run_id, key, evaluation, profile_hash=profile_hash)

    emit("run_finished", run_id=run_id, total_new=result.total_new)
    return result


def format_summary(result: CrawlResult, report_path: str) -> str:
    """터미널용 실행 요약."""
    lines = ["", "Contest Scout run completed", ""]
    for stats in result.stats:
        lines.append(f"{stats.source}")
        if stats.skipped_reason:
            lines.append(f"  SKIPPED: {stats.skipped_reason}")
            lines.append("")
            continue
        lines.append(f"  robots         : {stats.robots}")
        lines.append(f"  list pages     : {stats.list_pages}")
        lines.append(f"  discovered     : {stats.discovered}")
        lines.append(f"  new            : {stats.new}")
        lines.append(f"  existing       : {stats.existing}")
        lines.append(f"  details fetched: {stats.details_fetched}")
        lines.append(f"  http requests  : {stats.requests}")
        lines.append(f"  errors         : {stats.errors}")
        lines.append("")
    lines.append(f"Total new contests: {result.total_new}")
    lines.append(f"Total HTTP requests: {result.total_requests}")
    if result.warnings:
        lines.append(f"Parse warnings: {len(result.warnings)} (자세한 내용은 --verbose)")
    lines.append(f"Report: {report_path}")
    return "\n".join(lines)
