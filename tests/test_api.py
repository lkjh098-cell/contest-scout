"""HTTP API 테스트.

프론트엔드가 실제로 호출하는 경로만 검증한다. 네트워크는 타지 않는다 —
``Run Scout`` 은 실행기를 대역으로 갈아 끼워 "요청이 올바르게 전달되는가"만 본다.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from contest_scout import paths
from contest_scout.config import load_profile
from contest_scout.db import Database
from contest_scout.evaluators.rules import RuleEvaluator
from contest_scout.models import Contest
from contest_scout.repository import Repository
from contest_scout.schema_ext import upsert_score
from contest_scout.taxonomy import tags_for

TODAY = date.today()


def seed(db_path) -> None:
    db = Database(db_path)
    evaluator = RuleEvaluator(load_profile())
    repo = Repository(db)
    samples = [
        Contest(
            source="thinkgood",
            source_id="100",
            url="https://example.test/100",
            title="2026 생성형 AI 광고 영상 공모전",
            organizer="한국방송광고진흥공사",
            organizer_type="공공기관",
            categories=["영상/UCC"],
            eligibility=["제한 없음"],
            deadline=TODAY + timedelta(days=25),
            top_prize_krw=10_000_000,
            detail_text="AI 영상 공모전 요강",
        ),
        Contest(
            source="linkareer",
            source_id="200",
            url="https://example.test/200",
            title="제12회 문학 백일장",
            organizer="어느 재단",
            categories=["문학"],
            eligibility=["고등학생"],
            deadline=TODAY + timedelta(days=50),
            top_prize_krw=300_000,
        ),
    ]
    for contest in samples:
        db.upsert(contest)
        upsert_score(db.conn, contest.key, evaluator.evaluate(contest), "hash")
        repo.replace_tags(contest.key, tags_for(contest))
    db.conn.commit()
    db.close()


@pytest.fixture()
def client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("CONTEST_SCOUT_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("CONTEST_SCOUT_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.delenv("CONTEST_SCOUT_DB", raising=False)
    paths.ensure_dirs()
    seed(paths.db_path())

    from contest_scout.api.app import create_app

    # `with` 없이 만들면 lifespan(스케줄러 스레드)이 뜨지 않는다.
    return TestClient(create_app())


def test_health(client: TestClient) -> None:
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["db_exists"] is True


def test_dashboard_shape(client: TestClient) -> None:
    body = client.get("/api/dashboard").json()
    assert body["has_any_data"] is True
    assert body["kpi"]["active_contests"] == 2
    assert isinstance(body["top_opportunities"], list)
    assert body["scout"]["phase"] in {"idle", "running", "done", "failed"}
    assert "enabled" in body["schedule"]


def test_contest_list_filters_and_sorts(client: TestClient) -> None:
    everything = client.get("/api/contests", params={"page_size": 50}).json()
    assert everything["total"] == 2

    video = client.get("/api/contests", params={"tag": "영상"}).json()
    assert [item["source_id"] for item in video["items"]] == ["100"]

    by_prize = client.get(
        "/api/contests", params={"sort": "prize", "order": "desc"}
    ).json()
    assert by_prize["items"][0]["source_id"] == "100"

    rich = client.get("/api/contests", params={"min_prize": 1_000_000}).json()
    assert rich["total"] == 1


def test_contest_detail_and_404(client: TestClient) -> None:
    body = client.get("/api/contests/thinkgood:100").json()
    assert body["title"].startswith("2026 생성형")
    assert body["score"]["total"] > 0
    assert body["detail_text"] == "AI 영상 공모전 요강"

    missing = client.get("/api/contests/nope:1")
    assert missing.status_code == 404
    assert "찾을 수 없습니다" in missing.json()["detail"]


def test_status_transition_accepts_shortlisted_alias(client: TestClient) -> None:
    response = client.patch(
        "/api/contests/thinkgood:100/status", json={"status": "SHORTLISTED"}
    )
    assert response.status_code == 200
    # UI 용어(SHORTLISTED)는 엔진 상태(INTERESTED)로 정규화된다.
    assert response.json()["status"] == "INTERESTED"

    bad = client.patch("/api/contests/thinkgood:100/status", json={"status": "옐로"})
    assert bad.status_code == 422


def test_ignore_hides_from_default_list(client: TestClient) -> None:
    client.patch("/api/contests/linkareer:200/status", json={"status": "IGNORE"})
    default = client.get("/api/contests").json()
    assert all(item["key"] != "linkareer:200" for item in default["items"])
    shown = client.get("/api/contests", params={"include_inactive": "true"}).json()
    assert shown["total"] == 2


def test_project_creation_moves_contest_to_entering(client: TestClient) -> None:
    created = client.post("/api/projects", json={"contest_key": "thinkgood:100"})
    assert created.status_code == 201
    assert created.json()["stage"] == "RESEARCH"

    contest = client.get("/api/contests/thinkgood:100").json()
    assert contest["status"] == "ENTERING"
    assert contest["project"]["contest_key"] == "thinkgood:100"

    moved = client.patch("/api/projects/thinkgood:100", json={"stage": "PRODUCTION"})
    assert moved.json()["stage_index"] == 2

    assert client.post("/api/projects", json={"contest_key": "nope:1"}).status_code == 404


def test_settings_rejects_weights_that_do_not_sum_to_100(client: TestClient) -> None:
    bad = client.patch(
        "/api/settings",
        json={"profile": {"weights": {"award_value": 30, "skill_fit": 20}}},
    )
    assert bad.status_code == 400
    assert "100" in bad.json()["detail"]


def test_settings_roundtrip(client: TestClient) -> None:
    response = client.patch(
        "/api/settings",
        json={"crawl": {"delay": 3.5}, "schedule": {"enabled": True, "time": "7:5"}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["crawl"]["delay"] == 3.5
    assert body["schedule"] == {"enabled": True, "time": "07:05"}
    # 미구현 기능은 UI가 가짜로 그리지 않도록 플래그로 알린다.
    assert body["capabilities"]["ai_evaluator"] is False

    assert client.get("/api/settings").json()["crawl"]["delay"] == 3.5


def test_settings_rejects_unknown_source(client: TestClient) -> None:
    response = client.patch("/api/settings", json={"enabled_sources": ["wevity"]})
    assert response.status_code == 400
    assert client.patch("/api/settings", json={"enabled_sources": []}).status_code == 400


def test_scout_run_delegates_to_runner(client: TestClient, monkeypatch) -> None:
    calls: list[dict] = []

    def fake_start(**kwargs):
        calls.append(kwargs)
        return {"started": True, "state": {"phase": "running", "sources": {}}}

    from contest_scout.services import scout as scout_service

    monkeypatch.setattr(scout_service.runner, "start", fake_start)

    response = client.post("/api/scout/run", json={"sources": ["thinkgood"], "pages": 2})
    assert response.status_code == 202
    assert calls[0]["source_selection"] == "thinkgood"
    assert calls[0]["pages"] == 2

    unknown = client.post("/api/scout/run", json={"sources": ["wevity"]})
    assert unknown.status_code == 400


def test_scout_run_conflicts_when_already_running(client: TestClient, monkeypatch) -> None:
    from contest_scout.services import scout as scout_service

    monkeypatch.setattr(
        scout_service.runner,
        "start",
        lambda **_: {"started": False, "reason": "already_running", "state": {}},
    )
    assert client.post("/api/scout/run", json={}).status_code == 409


def test_sources_and_runs_endpoints(client: TestClient) -> None:
    sources = client.get("/api/sources").json()
    assert {item["name"] for item in sources} == {"thinkgood", "linkareer"}
    assert client.get("/api/scout/runs").json() == []
    assert client.get("/api/scout/runs/999").status_code == 404
