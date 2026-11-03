"""통합 테스트: 2회 실행 시 신규/기존 구분, 리포트 생성, 요청 절약."""

from __future__ import annotations

from contest_scout.config import load_profile
from contest_scout.crawl import crawl, format_summary
from contest_scout.db import Database
from contest_scout.evaluators.rules import RuleEvaluator
from contest_scout.report import render_markdown
from contest_scout.robots import RobotsPolicy
from contest_scout.sources.linkareer import LinkareerSource
from contest_scout.sources.thinkgood import LIST_API, ThinkgoodSource
from tests.conftest import FakeHttp, load_json, load_text


class FakeClient(FakeHttp):
    """FakeHttp + robots 정책 (항상 ALLOW인 robots.txt)."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.robots = RobotsPolicy(
            lambda url: (200, "User-agent: *\nAllow: /\n"), user_agent="ContestScout"
        )


def build_client() -> FakeClient:
    return FakeClient(
        texts={
            "https://linkareer.com/list/contest": load_text("linkareer_list.html"),
            "https://linkareer.com/activity/": load_text("linkareer_detail.html"),
        },
        json_payloads={LIST_API: load_json("thinkgood_sublist.json")},
    )


def run_once(http: FakeClient, db: Database, **kwargs):
    sources = [ThinkgoodSource(http), LinkareerSource(http)]
    evaluator = RuleEvaluator(load_profile())
    return crawl(sources, http, db, evaluator, **kwargs)


def test_first_run_collects_and_second_run_finds_nothing_new(tmp_path) -> None:
    db = Database(tmp_path / "t.sqlite3")

    http1 = build_client()
    first = run_once(http1, db)
    assert first.total_new == 5  # thinkgood 2 + linkareer 3
    assert {s.source: s.new for s in first.stats} == {"thinkgood": 2, "linkareer": 3}
    assert all(s.robots == "ALLOW" for s in first.stats)

    http2 = build_client()
    second = run_once(http2, db)
    assert second.total_new == 0
    assert {s.source: s.existing for s in second.stats} == {"thinkgood": 2, "linkareer": 3}
    # 이미 아는 공모전은 상세 요청을 하지 않는다 → 링커리어는 목록 1회뿐.
    assert [s.details_fetched for s in second.stats] == [0, 0]
    assert http2.request_count < http1.request_count


def test_thinkgood_uses_a_single_request_per_run(tmp_path) -> None:
    db = Database(tmp_path / "t.sqlite3")
    http = build_client()
    sources = [ThinkgoodSource(http)]
    crawl(sources, http, db, RuleEvaluator(load_profile()))
    # 목록 POST 1회로 상세까지 전부 확보한다.
    assert http.request_count == 1


def test_robots_deny_skips_source_without_crawling(tmp_path) -> None:
    db = Database(tmp_path / "t.sqlite3")
    http = build_client()
    http.robots = RobotsPolicy(
        lambda url: (403, ""), user_agent="ContestScout"
    )
    result = run_once(http, db)
    assert result.total_new == 0
    assert http.request_count == 0
    assert all(s.robots == "DENY" for s in result.stats)
    assert all(s.skipped_reason for s in result.stats)


def test_robots_unknown_skips_this_run(tmp_path) -> None:
    db = Database(tmp_path / "t.sqlite3")
    http = build_client()
    http.robots = RobotsPolicy(lambda url: (503, ""), user_agent="ContestScout")
    result = run_once(http, db)
    assert all(s.robots == "UNKNOWN" for s in result.stats)
    assert result.total_new == 0


def test_limit_caps_new_contests(tmp_path) -> None:
    db = Database(tmp_path / "t.sqlite3")
    http = build_client()
    result = run_once(http, db, limit=1)
    assert {s.source: s.new for s in result.stats} == {"thinkgood": 1, "linkareer": 1}


def test_report_is_written_and_readable(tmp_path) -> None:
    db = Database(tmp_path / "t.sqlite3")
    http = build_client()
    result = run_once(http, db)
    path = render_markdown(result, tmp_path / "daily_report.md")
    text = path.read_text("utf-8")

    assert "Contest Scout" in text
    assert "오늘 신규 공모전 **5개** 발견" in text
    assert "## 수집 요약" in text
    assert "생성형 AI 광고 영상 공모전" in text
    assert "종합점수" in text
    # 표 안의 등급 열이 존재
    assert "등급" in text


def test_summary_mentions_counts(tmp_path) -> None:
    db = Database(tmp_path / "t.sqlite3")
    http = build_client()
    result = run_once(http, db)
    summary = format_summary(result, "data/daily_report.md")
    assert "Total new contests: 5" in summary
    assert "thinkgood" in summary and "linkareer" in summary


def test_source_error_does_not_kill_the_run(tmp_path) -> None:
    db = Database(tmp_path / "t.sqlite3")
    http = build_client()

    class Broken(ThinkgoodSource):
        def discover(self, page: int = 1):
            raise RuntimeError("목록 구조 변경")

    sources = [Broken(http), LinkareerSource(http)]
    result = crawl(sources, http, db, RuleEvaluator(load_profile()))
    assert result.total_new == 3  # 링커리어는 정상 수집
    broken_stats = next(s for s in result.stats if s.source == "thinkgood")
    assert broken_stats.errors == 1
