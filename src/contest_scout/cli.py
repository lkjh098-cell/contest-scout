"""명령줄 인터페이스.

    contest-scout crawl   신규 공모전 수집 → DB 저장 → 평가 → 리포트
    contest-scout doctor  robots.txt / 목록 접근 가능 여부 진단
    contest-scout list    저장된 공모전 조회
    contest-scout mark    공모전 상태 변경 (IGNORE / ENTERING …)
    contest-scout sources 사용 가능한 소스 목록
    contest-scout serve   대시보드 API 서버 실행
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from contest_scout import __version__
from contest_scout.config import load_profile
from contest_scout.crawl import format_summary
from contest_scout.db import Database
from contest_scout.http import DEFAULT_USER_AGENT, SafeHttpClient
from contest_scout.models import ContestStatus
from contest_scout.services.scout import run_scout
from contest_scout.services.settings import CrawlSettings, load_settings
from contest_scout.sources import SOURCES, build_sources, source_names

DEFAULT_DB = "data/contest_scout.sqlite3"
DEFAULT_REPORT = "data/daily_report.md"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="contest-scout",
        description="개인 맞춤형 공모전 자동 탐색·추천 시스템",
    )
    parser.add_argument("--version", action="version", version=f"contest-scout {__version__}")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="로그 상세도")
    sub = parser.add_subparsers(dest="command", required=True)

    # crawl ------------------------------------------------------------ #
    crawl_cmd = sub.add_parser("crawl", help="신규 공모전 수집 및 평가")
    crawl_cmd.add_argument(
        "--source",
        default="all",
        help=f"수집 대상 (all 또는 쉼표 구분: {', '.join(source_names())})",
    )
    crawl_cmd.add_argument("--pages", type=int, default=1, help="목록 페이지 수 (기본 1)")
    crawl_cmd.add_argument("--limit", type=int, default=None, help="소스당 신규 수집 상한")
    crawl_cmd.add_argument("--db", default=DEFAULT_DB)
    crawl_cmd.add_argument("--report", default=DEFAULT_REPORT)
    crawl_cmd.add_argument("--profile", default=None, help="config/profile.json 경로")
    crawl_cmd.add_argument("--delay", type=float, default=2.0, help="요청 간 최소 간격(초)")
    crawl_cmd.add_argument("--timeout", type=float, default=20.0)
    crawl_cmd.add_argument(
        "--user-agent",
        default=DEFAULT_USER_AGENT,
        help="사이트가 기본 UA를 막을 때만 변경하세요",
    )
    crawl_cmd.add_argument(
        "--ignore-robots",
        action="store_true",
        help="권장하지 않음. 사이트 정책을 직접 확인한 경우에만 사용",
    )
    crawl_cmd.set_defaults(func=cmd_crawl)

    # doctor ----------------------------------------------------------- #
    doctor = sub.add_parser("doctor", help="robots.txt / 접근 가능 여부 진단")
    doctor.add_argument("--source", default="all")
    doctor.add_argument("--delay", type=float, default=2.0)
    doctor.add_argument("--timeout", type=float, default=20.0)
    doctor.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    doctor.set_defaults(func=cmd_doctor)

    # list ------------------------------------------------------------- #
    listing = sub.add_parser("list", help="저장된 공모전 조회")
    listing.add_argument("--db", default=DEFAULT_DB)
    listing.add_argument("--status", default=None, choices=ContestStatus.choices())
    listing.add_argument("--limit", type=int, default=30)
    listing.set_defaults(func=cmd_list)

    # mark ------------------------------------------------------------- #
    mark = sub.add_parser("mark", help="공모전 상태 변경")
    mark.add_argument("contest_key", help="예: thinkgood:110290")
    mark.add_argument("status", choices=ContestStatus.choices())
    mark.add_argument("--db", default=DEFAULT_DB)
    mark.set_defaults(func=cmd_mark)

    # sources ---------------------------------------------------------- #
    srcs = sub.add_parser("sources", help="사용 가능한 소스 목록")
    srcs.set_defaults(func=cmd_sources)

    # serve ------------------------------------------------------------- #
    serve = sub.add_parser("serve", help="대시보드 API 서버 실행")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true", help="코드 변경 시 자동 재시작")
    serve.add_argument("--db", default=DEFAULT_DB)
    serve.set_defaults(func=cmd_serve)

    return parser


def _setup_logging(verbosity: int) -> None:
    level = logging.WARNING
    if verbosity == 1:
        level = logging.INFO
    elif verbosity >= 2:
        level = logging.DEBUG
    logging.basicConfig(
        level=level,
        format="%(levelname)-7s %(name)s: %(message)s",
        stream=sys.stderr,
    )


# ---------------------------------------------------------------------- #
# 명령 구현
# ---------------------------------------------------------------------- #
def cmd_crawl(args: argparse.Namespace) -> int:
    """수집은 서비스 레이어에 맡긴다. 대시보드의 `Run Scout` 과 같은 코드다."""
    profile = load_profile(args.profile)
    settings = load_settings()
    settings.crawl = CrawlSettings(
        delay=args.delay,
        timeout=args.timeout,
        pages=args.pages,
        limit=args.limit,
        respect_robots=not args.ignore_robots,
        user_agent=args.user_agent,
    )
    Path(args.db).parent.mkdir(parents=True, exist_ok=True)

    outcome = run_scout(
        settings=settings,
        db_path=args.db,
        report=args.report,
        source_selection=args.source,
        pages=args.pages,
        limit=args.limit,
        profile=profile,
        trigger="cli",
    )

    if outcome.result is None:
        print("수집에 실패했습니다.", file=sys.stderr)
        for error in outcome.errors:
            print(f"  {error['source']}: {error['reason']}", file=sys.stderr)
        return 1

    result = outcome.result
    print(format_summary(result, outcome.report_path or ""))
    if outcome.expired:
        print(f"(마감 지난 공모전 {outcome.expired}건을 EXPIRED로 정리했습니다)")
    if outcome.rescored:
        print(f"(점수·태그 {outcome.rescored}건 동기화)")

    top = sorted(result.evaluations.values(), key=lambda e: e.total, reverse=True)[:10]
    if top:
        print("\n상위 후보")
        by_key = {c.key: c for c in result.new_contests}
        for evaluation in top:
            contest = by_key.get(evaluation.contest_key)
            title = contest.title if contest else evaluation.contest_key
            print(f"  {evaluation.tier:<4} {evaluation.total:>3}  {title}")

    return 1 if outcome.status == "FAILED" else 0


def cmd_doctor(args: argparse.Namespace) -> int:
    with SafeHttpClient(
        delay=args.delay, timeout=args.timeout, user_agent=args.user_agent
    ) as http:
        try:
            sources = build_sources(args.source, http)
        except KeyError as exc:
            print(f"오류: {exc}", file=sys.stderr)
            return 2

        print(f"contest-scout {__version__} 진단\n")
        print(f"User-Agent: {http.user_agent}\n")
        exit_code = 0
        for source in sources:
            report = http.robots.check(source.entry_url)
            print(f"[{source.name}]")
            print(f"  entry     : {source.entry_url}")
            print(f"  robots    : {report.state.value} — {report.detail}")
            if report.crawl_delay:
                print(f"  crawl-delay: {report.crawl_delay}s")
            if report.state.value != "ALLOW":
                exit_code = 1
                if "403" in report.detail or "401" in report.detail:
                    print(
                        "  힌트      : 사이트가 이 User-Agent로 온 robots.txt 요청을 거부했습니다.\n"
                        "              --user-agent 로 다른 값을 시험해 보세요."
                    )
                print()
                continue
            try:
                refs = source.discover(page=1)
            except Exception as exc:  # noqa: BLE001
                exit_code = 1
                print(f"  목록      : 실패 — {type(exc).__name__}: {exc}")
            else:
                print(f"  목록      : OK — {len(refs)}건 발견")
                for ref in refs[:3]:
                    print(f"              · {ref.title or ref.source_id} ({ref.url})")
            print()
        print(f"총 HTTP 요청: {http.request_count}")
    return exit_code


def cmd_list(args: argparse.Namespace) -> int:
    with Database(args.db) as db:
        rows = db.list_contests(status=args.status, limit=args.limit)
        if not rows:
            print("저장된 공모전이 없습니다. 먼저 `contest-scout crawl` 을 실행하세요.")
            return 0
        for row in rows:
            prize = f"{row['top_prize_krw']:,}원" if row["top_prize_krw"] else "-"
            print(
                f"{row['status']:<12} {row['deadline'] or '----------':<10} "
                f"{prize:>12}  {row['title'][:44]:<44} {row['contest_key']}"
            )
    return 0


def cmd_mark(args: argparse.Namespace) -> int:
    with Database(args.db) as db:
        ok = db.set_status(args.contest_key, ContestStatus(args.status))
    if not ok:
        print(f"해당 키를 찾지 못했습니다: {args.contest_key}", file=sys.stderr)
        return 1
    print(f"{args.contest_key} → {args.status}")
    return 0


def cmd_sources(args: argparse.Namespace) -> int:
    for name, cls in SOURCES.items():
        detail = "목록 응답에 상세 포함" if not cls.needs_detail_request else "상세 페이지 별도 요청"
        print(f"{name:<12} {cls.entry_url}  ({detail})")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    import os

    import uvicorn

    os.environ.setdefault("CONTEST_SCOUT_DB", args.db)
    print(f"Contest Scout API  →  http://{args.host}:{args.port}")
    print(f"API 문서            →  http://{args.host}:{args.port}/docs")
    uvicorn.run(
        "contest_scout.api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _setup_logging(args.verbose)
    return int(args.func(args) or 0)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
