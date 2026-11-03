"""소스 어댑터 파싱 테스트 (실제 응답 구조를 축약한 fixture 사용)."""

from __future__ import annotations

from datetime import date

from contest_scout.sources.linkareer import LinkareerSource
from contest_scout.sources.thinkgood import LIST_API, ThinkgoodSource
from tests.conftest import FakeHttp


# ---------------------------------------------------------------- thinkgood
def test_thinkgood_discover_reads_json_endpoint(thinkgood_payload) -> None:
    http = FakeHttp(json_payloads={LIST_API: thinkgood_payload})
    source = ThinkgoodSource(http)
    refs = source.discover(page=1)

    assert [r.source_id for r in refs] == ["110295", "110290"]
    assert refs[0].url.endswith("view.do?contest_pk=110295")
    # 목록 1회 요청으로 끝난다.
    assert http.request_count == 1


def test_thinkgood_detail_needs_no_extra_request(thinkgood_payload) -> None:
    http = FakeHttp(json_payloads={LIST_API: thinkgood_payload})
    source = ThinkgoodSource(http)
    refs = source.discover()
    before = http.request_count

    contest = source.fetch_detail(refs[1])

    assert http.request_count == before, "상세 조회에 추가 HTTP 요청이 발생했다"
    assert source.needs_detail_request is False
    assert contest.title == "2026 AI 활용 전남 앵커 사업 홍보 콘텐츠 공모전"
    assert contest.organizer == "전남대학교(여수) 전남 앵커 사업단"
    assert contest.start_date == date(2026, 8, 26)
    assert contest.deadline == date(2026, 9, 23)
    assert contest.top_prize_krw == 1_000_000
    assert "영상/UCC" in contest.categories
    assert contest.eligibility == ["지역 제한"]
    assert "공모 주제" in (contest.detail_text or "")
    assert "<p>" not in (contest.detail_text or "")
    assert "영상" in contest.keywords


def test_thinkgood_prize_uses_syllabus_when_field_missing(thinkgood_payload) -> None:
    row = dict(thinkgood_payload["listJsonData"][1])
    row["prize_money"] = ""
    payload = {"status": "1", "listJsonData": [row]}
    http = FakeHttp(json_payloads={LIST_API: payload})
    source = ThinkgoodSource(http)
    contest = source.fetch_detail(source.discover()[0])
    # 상세요강의 "대상 100만원" 에서 회수
    assert contest.top_prize_krw == 1_000_000


def test_thinkgood_failure_status_raises(thinkgood_payload) -> None:
    http = FakeHttp(json_payloads={LIST_API: {"status": "0", "msg": "데이타 호출에 실패하였습니다"}})
    source = ThinkgoodSource(http)
    try:
        source.discover()
    except RuntimeError as exc:
        assert "데이타 호출에 실패" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("실패 응답인데 예외가 발생하지 않았다")


def test_thinkgood_records_parse_warning_for_missing_fields() -> None:
    payload = {"status": "1", "listJsonData": [{"contest_pk": 1, "program_nm": "제목만 있는 공모전"}]}
    http = FakeHttp(json_payloads={LIST_API: payload})
    source = ThinkgoodSource(http)
    contest = source.fetch_detail(source.discover()[0])
    fields = {w.field for w in contest.warnings}
    assert {"organizer", "deadline", "detail_text"} <= fields


# ---------------------------------------------------------------- linkareer
def test_linkareer_list_prefers_json_ld(linkareer_list_html) -> None:
    source = LinkareerSource(FakeHttp())
    refs = source._parse_list(linkareer_list_html)
    assert [r.source_id for r in refs] == ["346834", "346824", "346797"]
    assert refs[0].url == "https://linkareer.com/activity/346834"
    assert "직스캐드" in refs[0].title


def test_linkareer_list_falls_back_to_next_data() -> None:
    import json

    from tests.conftest import load_text

    html = load_text("linkareer_list.html")
    # JSON-LD를 통째로 제거해도 __NEXT_DATA__ 로 복구되어야 한다.
    stripped = html.split("<script type=\"application/ld+json\">")
    head = stripped[0]
    tail = html[html.index("</head>") :]
    broken = head + tail
    assert "ld+json" not in broken
    refs = LinkareerSource(FakeHttp())._parse_list(broken)
    assert {r.source_id for r in refs} == {"346834", "346824", "346797"}
    json.loads("{}")  # 문법 확인용 no-op


def test_linkareer_list_last_resort_regex() -> None:
    html = '<html><body><a href="/activity/999001">x</a><a href="/activity/999002">y</a></body></html>'
    refs = LinkareerSource(FakeHttp())._parse_list(html)
    assert [r.source_id for r in refs] == ["999001", "999002"]


def test_linkareer_detail_uses_apollo_state(linkareer_detail_html) -> None:
    source = LinkareerSource(FakeHttp())
    contest = source.parse_detail(
        linkareer_detail_html, "https://linkareer.com/activity/346900"
    )
    assert contest.source_id == "346900"
    assert contest.title == "2026 생성형 AI 광고 영상 공모전"
    assert contest.organizer == "한국방송광고진흥공사"
    assert contest.organizer_type == "공공기관"
    assert contest.categories == ["사진/영상/UCC", "광고/마케팅"]
    assert contest.eligibility == ["대학생", "일반인"]
    assert contest.total_prize_krw == 14_000_000  # 1400 만원
    assert contest.top_prize_krw == 10_000_000  # 본문 "대상 1,000만원"
    assert "상장 수여" in contest.benefits
    assert contest.homepage == "https://www.kobaco.co.kr/"
    assert contest.deadline is not None


def test_linkareer_detail_fallback_when_structure_changes() -> None:
    from tests.conftest import load_text

    source = LinkareerSource(FakeHttp())
    contest = source.parse_detail(
        load_text("linkareer_detail_broken.html"),
        "https://linkareer.com/activity/123456",
    )
    assert contest.title == "구조 변경된 공모전"
    assert contest.source_id == "123456"
    assert any(w.field == "__APOLLO_STATE__" for w in contest.warnings)


def test_linkareer_fetch_detail_issues_one_request(
    linkareer_list_html, linkareer_detail_html
) -> None:
    http = FakeHttp(
        texts={
            "https://linkareer.com/list/contest": linkareer_list_html,
            "https://linkareer.com/activity/": linkareer_detail_html,
        }
    )
    source = LinkareerSource(http)
    refs = source.discover()
    assert http.request_count == 1
    source.fetch_detail(refs[0])
    assert http.request_count == 2
