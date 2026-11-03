"""DB(증분·상태·중복)와 규칙 평가기 테스트."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from contest_scout.config import load_profile
from contest_scout.db import Database
from contest_scout.evaluators.rules import RuleEvaluator
from contest_scout.models import Contest, ContestStatus
from contest_scout.normalize import (
    extract_top_prize,
    parse_date,
    parse_date_range,
    parse_krw,
    parse_man_won,
    similarity,
    strip_html,
)


@pytest.fixture()
def db(tmp_path) -> Database:
    return Database(tmp_path / "test.sqlite3")


@pytest.fixture()
def profile():
    return load_profile()


def make_contest(**kwargs) -> Contest:
    base = dict(
        source="thinkgood",
        source_id="1",
        url="https://example.test/1",
        title="2026 생성형 AI 광고 영상 공모전",
        organizer="한국방송광고진흥공사",
        organizer_type="공공기관",
        categories=["영상/UCC", "광고/마케팅"],
        eligibility=["대학생", "일반인"],
        deadline=date.today() + timedelta(days=30),
        prize_text="1,000만원",
        top_prize_krw=10_000_000,
        detail_text="AI 영상 광고 캠페인 기획 및 제작",
    )
    base.update(kwargs)
    return Contest(**base)


# ------------------------------------------------------------------ 정규화
def test_parse_krw_units() -> None:
    assert parse_krw("1,000만원") == 10_000_000
    assert parse_krw("1억원") == 100_000_000
    assert parse_krw("300만원") == 3_000_000
    assert parse_krw("500,000원") == 500_000
    assert parse_krw("총상금 3000만") == 300_000_000 // 10  # 3,000만원
    assert parse_krw("상금 없음") is None
    # 비상식적으로 큰 값은 입력 오류로 보고 버린다.
    assert parse_krw("999999억원") is None


def test_parse_man_won() -> None:
    assert parse_man_won(1400) == 14_000_000
    assert parse_man_won(0) is None
    assert parse_man_won(1_000_000) is None  # 100억 → 입력 오류


def test_parse_dates() -> None:
    assert parse_date("2026-09-30 23:59:00.0") == date(2026, 9, 30)
    assert parse_date("2026.09.30") == date(2026, 9, 30)
    assert parse_date("2026년 9월 30일") == date(2026, 9, 30)
    assert parse_date("미정") is None
    assert parse_date_range("2026-08-26 ~ 2026-09-23") == (
        date(2026, 8, 26),
        date(2026, 9, 23),
    )


def test_strip_html_and_top_prize() -> None:
    body = "<p>● 시상<br>대상 1,000만원<br>최우수상 300만원</p>"
    text = strip_html(body)
    assert "<" not in text
    assert extract_top_prize(text) == 10_000_000


# ------------------------------------------------------------------ DB
def test_upsert_marks_new_then_existing(db: Database) -> None:
    contest = make_contest()
    assert db.upsert(contest) is True
    assert db.upsert(contest) is False
    assert db.known_keys("thinkgood") == {"thinkgood:1"}


def test_known_keys_drive_incremental_skip(db: Database) -> None:
    db.upsert(make_contest())
    assert "thinkgood:1" in db.known_keys("thinkgood")
    assert db.known_keys("linkareer") == set()


def test_status_transitions_and_ignore_is_sticky(db: Database) -> None:
    db.upsert(make_contest())
    assert db.get_status("thinkgood:1") is ContestStatus.NEW
    db.set_status("thinkgood:1", ContestStatus.IGNORE)
    # IGNORE는 자동 추천이 덮어쓰지 못한다.
    db.mark_recommended(["thinkgood:1"])
    assert db.get_status("thinkgood:1") is ContestStatus.IGNORE
    assert db.is_suppressed("thinkgood:1") is True


def test_mark_recommended_updates_new_only(db: Database) -> None:
    db.upsert(make_contest())
    db.upsert(make_contest(source_id="2", url="https://example.test/2", title="다른 공모전"))
    db.set_status("thinkgood:2", ContestStatus.ENTERING)
    db.mark_recommended(["thinkgood:1", "thinkgood:2"])
    assert db.get_status("thinkgood:1") is ContestStatus.RECOMMENDED
    assert db.get_status("thinkgood:2") is ContestStatus.ENTERING


def test_expire_past_deadline(db: Database) -> None:
    db.upsert(make_contest(deadline=date.today() - timedelta(days=1)))
    assert db.expire_past_deadline() == 1
    assert db.get_status("thinkgood:1") is ContestStatus.EXPIRED


def test_cross_source_dedupe_shares_canonical_key(db: Database) -> None:
    deadline = date.today() + timedelta(days=20)
    a = make_contest(
        source="linkareer",
        source_id="500",
        title="2026 XXX AI 영상 공모전",
        deadline=deadline,
    )
    b = make_contest(
        source="thinkgood",
        source_id="600",
        title="2026년 XXX 생성형 AI 영상 공모전",
        deadline=deadline,
    )
    db.upsert(a)
    db.upsert(b)
    rows = {r["contest_key"]: r["canonical_key"] for r in db.list_contests(limit=10)}
    assert rows["linkareer:500"] == rows["thinkgood:600"]


def test_different_contests_keep_separate_canonical_keys(db: Database) -> None:
    db.upsert(make_contest(source="linkareer", source_id="700", title="전국 사진 공모전"))
    db.upsert(make_contest(source="thinkgood", source_id="800", title="브랜드 네이밍 아이디어"))
    rows = {r["contest_key"]: r["canonical_key"] for r in db.list_contests(limit=10)}
    assert rows["linkareer:700"] != rows["thinkgood:800"]


def test_similarity_behaviour() -> None:
    assert similarity("ai 영상", "ai 영상") == 1.0
    assert similarity("ai 영상", "건축 설계") == 0.0


def test_run_and_recommendation_tables(db: Database, profile) -> None:
    contest = make_contest()
    db.upsert(contest)
    run_id = db.start_run(["thinkgood"])
    evaluation = RuleEvaluator(profile).evaluate(contest)
    db.save_recommendation(run_id, contest.key, evaluation)
    db.save_recommendation(run_id, contest.key, evaluation)  # 멱등
    db.finish_run(run_id, total_new=1, total_seen=5, requests=1, stats={})
    rows = db.conn.execute("SELECT * FROM recommendations").fetchall()
    assert len(rows) == 1
    assert db.last_runs()[0]["total_new"] == 1


def test_load_contest_roundtrip(db: Database) -> None:
    original = make_contest()
    db.upsert(original)
    restored = db.load_contest("thinkgood:1")
    assert restored is not None
    assert restored.title == original.title
    assert restored.deadline == original.deadline
    assert restored.categories == original.categories


# ------------------------------------------------------------------ 평가
def test_scoring_weights_sum_to_100(profile) -> None:
    assert profile.max_score == 100


def test_good_match_scores_high(profile) -> None:
    evaluation = RuleEvaluator(profile).evaluate(make_contest())
    assert evaluation.total >= 75
    assert evaluation.tier in {"S", "A"}
    assert evaluation.parts["award_value"] == 20
    assert sum(evaluation.parts.values()) == evaluation.total


def test_off_profile_contest_scores_low(profile) -> None:
    contest = make_contest(
        title="제12회 전국 학생 백일장 및 독후감 공모전",
        organizer=None,
        organizer_type=None,
        categories=["문학/수기"],
        eligibility=["초등학생", "중학생"],
        prize_text=None,
        top_prize_krw=None,
        detail_text="시와 수필을 제출하는 문학 백일장. 논문 심사 병행.",
    )
    evaluation = RuleEvaluator(profile).evaluate(contest)
    assert evaluation.tier == "SKIP"
    assert evaluation.total < 60


def test_no_part_exceeds_its_weight(profile) -> None:
    contest = make_contest(top_prize_krw=500_000_000)
    evaluation = RuleEvaluator(profile).evaluate(contest)
    for key, value in evaluation.parts.items():
        assert 0 <= value <= profile.weights[key], key


def test_tight_deadline_is_penalised(profile) -> None:
    contest = make_contest(deadline=date.today() + timedelta(days=1))
    evaluation = RuleEvaluator(profile).evaluate(contest)
    assert evaluation.parts["feasibility"] <= 2
    assert any("마감" in risk for risk in evaluation.risks)


def test_team_requirement_blocks_solo_points(profile) -> None:
    contest = make_contest(detail_text="반드시 3인 이상 팀으로 참가해야 합니다.")
    evaluation = RuleEvaluator(profile).evaluate(contest)
    assert evaluation.parts["solo_friendly"] == 1


def test_missing_deadline_produces_risk(profile) -> None:
    evaluation = RuleEvaluator(profile).evaluate(make_contest(deadline=None))
    assert any("마감일" in risk for risk in evaluation.risks)


# --- 실제 씽굿 데이터로 확인한 회귀 케이스 ------------------------------- #
def _score_live_sample(profile):
    """실제 씽굿 목록 응답(2026-08-31 캡처)으로 순위를 매긴다."""
    import json

    from contest_scout.sources.thinkgood import ThinkgoodSource
    from tests.conftest import FIXTURES

    data = json.loads((FIXTURES / "thinkgood_live_sample.json").read_text("utf-8"))

    class Http:
        request_count = 0

        def post_json(self, url, payload):
            return data

    source = ThinkgoodSource(Http())
    evaluator = RuleEvaluator(profile)
    out = {}
    for ref in source.discover():
        contest = source.fetch_detail(ref)
        out[contest.title] = (evaluator.evaluate(contest), contest)
    return out


def test_live_sample_ranks_ai_content_contest_first(profile) -> None:
    scored = _score_live_sample(profile)
    ranked = sorted(scored.items(), key=lambda kv: -kv[1][0].total)
    assert "AI 활용" in ranked[0][0]
    assert ranked[0][1][0].tier in {"S", "A"}


def test_live_sample_demotes_literature_contest(profile) -> None:
    scored = _score_live_sample(profile)
    evaluation, _ = scored["제19회 장애인 독후활동 대회"]
    assert evaluation.tier == "SKIP"


def test_live_sample_demotes_pure_dev_contest(profile) -> None:
    """상금 2,000만원이어도 순수 개발 성격이면 상위 추천이 아니어야 한다."""
    scored = _score_live_sample(profile)
    evaluation, _ = scored["2026 국방 AI 경진대회 참가자 모집 및 이벤트 안내"]
    assert evaluation.tier in {"B", "SKIP"}


def test_broad_eligibility_list_is_not_treated_as_youth_only(profile) -> None:
    """씽굿은 전 연령을 나열한다. '초등학생'이 있다고 감점하면 안 된다."""
    scored = _score_live_sample(profile)
    evaluation, contest = scored["2026년 밀양시 SNS 영상 공모전"]
    assert "초등학생" in contest.eligibility
    assert "제한 없음" in contest.eligibility
    assert evaluation.tier != "SKIP"
    assert not any("청소년" in risk for risk in evaluation.risks)


def test_body_text_does_not_trigger_topic_negatives(profile) -> None:
    """본문의 '청소년 불법도박 예방'이 분야 판정을 오염시키면 안 된다."""
    scored = _score_live_sample(profile)
    evaluation, contest = scored["건전경마 활성화&불법도박 예방 영상공모전"]
    assert "청소년" in (contest.detail_text or "")
    assert evaluation.parts["skill_fit"] >= 8
    assert evaluation.tier != "SKIP"


def test_youth_only_contest_is_flagged(profile) -> None:
    scored = _score_live_sample(profile)
    evaluation, _ = scored["서대문구청소년상담복지센터 캐릭터 공모전"]
    assert evaluation.tier == "SKIP"
