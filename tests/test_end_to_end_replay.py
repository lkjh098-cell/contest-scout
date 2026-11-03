"""실제 SafeHttpClient(httpx) → robots → 크롤 → DB → 리포트 전 구간 replay 테스트.

로컬 HTTP 서버가 실제 사이트와 같은 형태의 응답(robots.txt / 목록 JSON / 상세
HTML)을 돌려준다. 네트워크 밖으로 나가지 않으면서도 다음을 실제로 검증한다.

* robots.txt를 크롤러와 같은 httpx client/UA로 가져오는가 (v0.1.x 회귀 방지)
* origin당 robots.txt를 한 번만 요청하는가
* 2회차 실행에서 상세 요청이 0건인가
* 리포트/DB가 실제로 기록되는가
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from contest_scout.config import load_profile
from contest_scout.crawl import crawl
from contest_scout.db import Database
from contest_scout.evaluators.rules import RuleEvaluator
from contest_scout.http import SafeHttpClient
from contest_scout.report import render_markdown
from contest_scout.sources.linkareer import LinkareerSource
from contest_scout.sources.thinkgood import ThinkgoodSource
from tests.conftest import load_json, load_text

ROBOTS = """User-agent: *
Allow: /
Disallow: /login*
Disallow: /thinkgood/user/contest/thinkgood-talk*
"""


class ReplayHandler(BaseHTTPRequestHandler):
    hits: dict[str, int] = {}

    def log_message(self, *args: object) -> None:  # 테스트 출력 조용히
        pass

    def _count(self, path: str) -> None:
        ReplayHandler.hits[path] = ReplayHandler.hits.get(path, 0) + 1

    def _send(self, body: str, content_type: str = "text/html; charset=utf-8") -> None:
        payload = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?")[0]
        self._count(path)
        # 크롤러와 동일한 UA로 왔는지 확인 (robots.txt 포함)
        assert self.headers.get("User-Agent", "").startswith("ContestScout/")

        if path == "/robots.txt":
            self._send(ROBOTS, "text/plain; charset=utf-8")
        elif path == "/list/contest":
            self._send(load_text("linkareer_list.html"))
        elif path.startswith("/activity/"):
            self._send(load_text("linkareer_detail.html"))
        else:
            self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?")[0]
        self._count(path)
        if path.endswith("/subList.do"):
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            assert body["recordsPerPage"] > 0
            self._send(
                json.dumps(load_json("thinkgood_sublist.json"), ensure_ascii=False),
                "application/json; charset=utf-8",
            )
        else:
            self.send_error(404)


@pytest.fixture()
def server():
    ReplayHandler.hits = {}
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), ReplayHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def make_sources(base: str, http: SafeHttpClient):
    class LocalThinkgood(ThinkgoodSource):
        entry_url = f"{base}/thinkgood/user/contest/index.do"

        def discover(self, page: int = 1):
            payload = {
                "recordsPerPage": self.records_per_page,
                "currentPageNo": page,
                "searchStatus": "Y",
                "sidx": "putup_sdt",
                "sord": "DESC",
            }
            data = self.http.post_json(f"{base}/thinkgood/user/contest/subList.do", payload)
            refs = []
            from contest_scout.models import ContestRef

            for row in data["listJsonData"]:
                refs.append(
                    ContestRef(
                        source=self.name,
                        source_id=str(row["contest_pk"]),
                        url=f"{base}/thinkgood/user/contest/view.do?contest_pk={row['contest_pk']}",
                        title=row["program_nm"],
                        payload=row,
                    )
                )
            return refs

    class LocalLinkareer(LinkareerSource):
        entry_url = f"{base}/list/contest"

        def discover(self, page: int = 1):
            html_text = self.http.get_text(f"{base}/list/contest")
            refs = self._parse_list(html_text)
            for ref in refs:
                ref.url = f"{base}/activity/{ref.source_id}"
            return refs

    return [LocalThinkgood(http), LocalLinkareer(http)]


def test_full_pipeline_over_real_http(server: str, tmp_path: Path) -> None:
    profile = load_profile()
    db = Database(tmp_path / "e2e.sqlite3")

    with SafeHttpClient(delay=0.0, timeout=5.0) as http:
        first = crawl(make_sources(server, http), http, db, RuleEvaluator(profile))
        first_requests = http.request_count

    assert first.total_new == 5
    assert all(s.robots == "ALLOW" for s in first.stats), [s.robots for s in first.stats]
    # robots.txt는 origin당 한 번만
    assert ReplayHandler.hits["/robots.txt"] == 1
    # 링커리어 상세 3건 + 목록 1건, 씽굿 목록 1건, robots 1건
    assert first_requests == 6

    report = render_markdown(first, tmp_path / "report.md")
    text = report.read_text("utf-8")
    assert "오늘 신규 공모전 **5개** 발견" in text
    assert "생성형 AI 광고 영상 공모전" in text

    rows = db.list_contests(limit=20)
    assert len(rows) == 5

    # --- 2회차: 신규 0건, 상세 요청 0건 ------------------------------- #
    ReplayHandler.hits = {}
    with SafeHttpClient(delay=0.0, timeout=5.0) as http:
        second = crawl(make_sources(server, http), http, db, RuleEvaluator(profile))
        second_requests = http.request_count

    assert second.total_new == 0
    assert sum(s.details_fetched for s in second.stats) == 0
    assert "/activity/346834" not in ReplayHandler.hits
    assert second_requests < first_requests
    db.close()


def test_robots_denied_source_makes_no_page_request(server: str, tmp_path: Path) -> None:
    """robots가 막으면 목록조차 요청하지 않는다."""

    class DenyAll(BaseHTTPRequestHandler):
        pass

    db = Database(tmp_path / "deny.sqlite3")
    with SafeHttpClient(delay=0.0, timeout=5.0) as http:
        sources = make_sources(server, http)
        # entry_url을 robots가 막는 경로로 바꾼다.
        sources[0].__class__.entry_url = f"{server}/login.do"
        ReplayHandler.hits = {}
        result = crawl(sources[:1], http, db, RuleEvaluator(load_profile()))

    assert result.total_new == 0
    assert result.stats[0].robots == "DENY"
    assert "/thinkgood/user/contest/subList.do" not in ReplayHandler.hits
    db.close()
