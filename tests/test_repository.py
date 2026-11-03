"""대시보드 조회 계층 테스트.

수집기(crawl)와 분리해 **저장된 데이터를 어떻게 보여 주는가**만 검증한다.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from contest_scout.config import load_profile
from contest_scout.db import Database
from contest_scout.evaluators.rules import RuleEvaluator
from contest_scout.models import Contest, ContestStatus
from contest_scout.repository import ContestQuery, Repository
from contest_scout.schema_ext import PROJECT_STAGES, upsert_score
from contest_scout.taxonomy import tags_for

TODAY = date(2026, 9, 1)


def make_contest(source: str, source_id: str, title: str, **kwargs) -> Contest:
    base = dict(
        source=source,
        source_id=source_id,
        url=f"https://example.test/{source}/{source_id}",
        title=title,
        organizer="한국방송광고진흥공사",
        organizer_type="공공기관",
        categories=["영상/UCC"],
        eligibility=["제한 없음"],
        deadline=TODAY + timedelta(days=20),
        top_prize_krw=5_000_000,
        detail_text="AI 영상 공모전입니다.",
    )
    base.update(kwargs)
    return Contest(**base)


@pytest.fixture()
def repo(tmp_path):
    db = Database(tmp_path / "repo.sqlite3")
    evaluator = RuleEvaluator(load_profile(), today=TODAY)
    repository = Repository(db, today=TODAY)

    contests = [
        make_contest("thinkgood", "1", "2026 생성형 AI 광고 영상 공모전"),
        make_contest(
            "linkareer",
            "2",
            "2026 문학 백일장 수기 공모전",
            categories=["문학"],
            top_prize_krw=300_000,
            deadline=TODAY + timedelta(days=40),
        ),
        make_contest(
            "thinkgood",
            "3",
            "마감 임박 숏폼 브랜드 캠페인 공모전",
            deadline=TODAY + timedelta(days=4),
            top_prize_krw=12_000_000,
        ),
    ]
    for contest in contests:
        db.upsert(contest)
        evaluation = evaluator.evaluate(contest)
        upsert_score(db.conn, contest.key, evaluation, "hash")
        repository.replace_tags(contest.key, tags_for(contest))
    db.conn.commit()

    yield repository
    db.close()


def test_list_applies_filters(repo: Repository) -> None:
    everything = repo.list_contests(ContestQuery(page_size=50))
    assert everything["total"] == 3

    video = repo.list_contests(ContestQuery(tags=["영상"], page_size=50))
    titles = [item["title"] for item in video["items"]]
    assert "2026 문학 백일장 수기 공모전" not in titles

    rich = repo.list_contests(ContestQuery(min_prize=10_000_000, page_size=50))
    assert [item["source_id"] for item in rich["items"]] == ["3"]

    urgent = repo.list_contests(ContestQuery(deadline_within=7, page_size=50))
    assert [item["source_id"] for item in urgent["items"]] == ["3"]

    searched = repo.list_contests(ContestQuery(q="백일장", page_size=50))
    assert searched["total"] == 1


def test_sorting_puts_missing_values_last(repo: Repository) -> None:
    repo.db.upsert(
        make_contest("thinkgood", "9", "마감일 없는 공모전", deadline=None, top_prize_krw=None)
    )
    result = repo.list_contests(ContestQuery(sort="deadline", order="asc", page_size=50))
    assert result["items"][-1]["source_id"] == "9"


def test_pagination_reports_total_not_page_size(repo: Repository) -> None:
    page = repo.list_contests(ContestQuery(page=1, page_size=2))
    assert page["total"] == 3
    assert len(page["items"]) == 2
    assert page["has_more"] is True
    assert repo.list_contests(ContestQuery(page=2, page_size=2))["has_more"] is False


def test_cross_source_duplicates_collapse_into_one_row(repo: Repository) -> None:
    """같은 공모전이 두 사이트에 있으면 목록에는 한 줄만 나와야 한다."""
    twin = make_contest("linkareer", "77", "2026 생성형 AI 광고 영상 공모전")
    repo.db.upsert(twin)
    repo.replace_tags(twin.key, tags_for(twin))
    repo.db.conn.commit()

    collapsed = repo.list_contests(ContestQuery(page_size=50))
    assert collapsed["total"] == 3
    merged = next(item for item in collapsed["items"] if "생성형 AI" in item["title"])
    assert merged["duplicate_count"] == 2
    assert sorted(merged["duplicate_sources"]) == ["linkareer", "thinkgood"]

    expanded = repo.list_contests(ContestQuery(page_size=50, collapse_duplicates=False))
    assert expanded["total"] == 4


def test_ignored_contests_drop_out_of_default_list(repo: Repository) -> None:
    repo.set_status("thinkgood:1", ContestStatus.IGNORE)
    default = repo.list_contests(ContestQuery(page_size=50))
    assert all(item["key"] != "thinkgood:1" for item in default["items"])

    explicit = repo.list_contests(ContestQuery(statuses=["IGNORE"], page_size=50))
    assert [item["key"] for item in explicit["items"]] == ["thinkgood:1"]


def test_status_change_is_logged(repo: Repository) -> None:
    updated = repo.set_status("thinkgood:1", ContestStatus.INTERESTED)
    assert updated is not None
    assert updated["status"] == "INTERESTED"
    assert updated["history"][0]["to_status"] == "INTERESTED"
    assert repo.set_status("nope:0", ContestStatus.IGNORE) is None


def test_dashboard_counts_only_live_contests(repo: Repository) -> None:
    data = repo.dashboard()
    assert data["has_any_data"] is True
    assert data["kpi"]["active_contests"] == 3
    assert data["kpi"]["ending_soon"] == 1
    assert len(data["matrix"]) == 3
    assert all(0 <= point["win"] <= 100 for point in data["matrix"])

    repo.set_status("thinkgood:3", ContestStatus.IGNORE)
    assert repo.dashboard()["kpi"]["ending_soon"] == 0


def test_project_lifecycle(repo: Repository) -> None:
    project = repo.create_project("thinkgood:1")
    assert project is not None
    assert project["stage"] == PROJECT_STAGES[0]
    assert project["progress"] == 20
    assert project["deadline"] is not None

    moved = repo.update_project("thinkgood:1", stage="PRODUCTION")
    assert moved is not None and moved["stage_index"] == 2

    with pytest.raises(ValueError):
        repo.update_project("thinkgood:1", stage="NOT_A_STAGE")

    assert repo.create_project("missing:0") is None
    assert repo.delete_project("thinkgood:1") is True
    assert repo.get_project("thinkgood:1") is None


def test_analytics_reports_zero_instead_of_guessing(repo: Repository) -> None:
    data = repo.analytics()
    selection = data["selection"]
    assert selection["selected_count"] == 0
    # 아직 고른 게 없으면 평균 상금은 지어내지 않고 비운다.
    assert selection["avg_selected_prize"] is None
    # 모수가 있으면 0%도 사실이지만, 모수가 0이면 비율 자체를 만들지 않는다.
    if selection["s_tier_total"]:
        assert selection["s_tier_shortlist_rate"] == 0
    else:
        assert selection["s_tier_shortlist_rate"] is None

    repo.set_status("thinkgood:1", ContestStatus.ENTERING)
    after = repo.analytics()
    assert after["selection"]["selected_count"] == 1
    assert after["selection"]["avg_selected_prize"] == 5_000_000


def test_facets_expose_filter_options(repo: Repository) -> None:
    facets = repo.facets()
    assert {row["source"] for row in facets["sources"]} == {"thinkgood", "linkareer"}
    assert any(row["tag"] == "영상" for row in facets["tags"])
