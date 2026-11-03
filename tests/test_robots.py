"""robots.txt 3상태 판정 테스트.

v0.1.x의 회귀 방지가 목적: 씽굿/링커리어 실제 robots.txt에서 공모전 경로가
ALLOW로 판정되어야 한다.
"""

from __future__ import annotations

import pytest

from contest_scout.robots import RobotsPolicy, RobotsState, evaluate_response
from tests.conftest import load_text

THINKGOOD = "https://www.thinkcontest.com"
LINKAREER = "https://linkareer.com"


def policy_for(origin: str, status: int, body: str) -> RobotsPolicy:
    return RobotsPolicy(lambda url: (status, body), user_agent="ContestScout")


# --- 회귀 테스트: 실제 정책에서 공모전 경로는 허용되어야 한다 ------------- #
def test_thinkgood_contest_paths_allowed() -> None:
    policy = policy_for(THINKGOOD, 200, load_text("robots_thinkgood.txt"))
    for path in (
        "/thinkgood/user/contest/index.do",
        "/thinkgood/user/contest/view.do?contest_pk=110290",
        "/thinkgood/user/contest/subList.do",
    ):
        report = policy.check(THINKGOOD + path)
        assert report.state is RobotsState.ALLOW, f"{path} -> {report}"


def test_thinkgood_blocked_paths_denied() -> None:
    """``Allow: /`` 가 맨 위에 있어도 더 구체적인 Disallow가 이겨야 한다.

    urllib.robotparser는 먼저 나온 규칙을 그대로 채택해 이 경로들을 허용해버린다.
    """
    policy = policy_for(THINKGOOD, 200, load_text("robots_thinkgood.txt"))
    for path in (
        "/login.do",
        "/logout.do",
        "/thinkgood/user/contest/thinkgood-talk.do",
        "/ufiles/a.png",
        "/thinkgood/user/auth/login.do",
        "/upload/files/x",
        "/board/notice.pdf",
        "/thinkgood/index.do;jsessionid=ABC",
    ):
        assert policy.check(THINKGOOD + path).state is RobotsState.DENY, path


def test_extension_rule_only_matches_at_end() -> None:
    """``Disallow: /*.pdf$`` 는 경로 끝에서만 걸려야 한다."""
    policy = policy_for(THINKGOOD, 200, load_text("robots_thinkgood.txt"))
    assert policy.check(THINKGOOD + "/notes.pdf").state is RobotsState.DENY
    assert policy.check(THINKGOOD + "/pdf-guide/index.do").state is RobotsState.ALLOW


def test_named_bot_group_does_not_leak_into_wildcard() -> None:
    """AhrefsBot 전용 ``Disallow: /`` 가 우리 UA에 적용되면 안 된다."""
    policy = policy_for(THINKGOOD, 200, load_text("robots_thinkgood.txt"))
    assert policy.check(THINKGOOD + "/thinkgood/user/contest/index.do").state is RobotsState.ALLOW


def test_linkareer_contest_paths_allowed() -> None:
    policy = policy_for(LINKAREER, 200, load_text("robots_linkareer.txt"))
    assert policy.check(LINKAREER + "/list/contest").state is RobotsState.ALLOW
    assert policy.check(LINKAREER + "/activity/346834").state is RobotsState.ALLOW


def test_linkareer_blocked_path_denied() -> None:
    policy = policy_for(LINKAREER, 200, load_text("robots_linkareer.txt"))
    assert policy.check(LINKAREER + "/stem/learn/profile/me").state is RobotsState.DENY


# --- HTTP 상태별 3상태 매핑 --------------------------------------------- #
@pytest.mark.parametrize(
    "status, expected",
    [
        (200, RobotsState.ALLOW),
        (401, RobotsState.DENY),
        (403, RobotsState.DENY),
        (404, RobotsState.ALLOW),
        (410, RobotsState.ALLOW),
        (500, RobotsState.UNKNOWN),
        (503, RobotsState.UNKNOWN),
        (302, RobotsState.UNKNOWN),
    ],
)
def test_status_mapping(status: int, expected: RobotsState) -> None:
    body = "User-agent: *\nAllow: /\n" if status == 200 else ""
    assert evaluate_response(THINKGOOD, status, body).state is expected


def test_network_error_is_unknown_not_deny() -> None:
    def boom(url: str) -> tuple[int, str]:
        raise ConnectionError("DNS 실패")

    policy = RobotsPolicy(boom, user_agent="ContestScout")
    report = policy.check(THINKGOOD + "/thinkgood/user/contest/index.do")
    assert report.state is RobotsState.UNKNOWN
    assert "network error" in report.detail


def test_robots_is_fetched_once_per_origin() -> None:
    calls: list[str] = []

    def fetcher(url: str) -> tuple[int, str]:
        calls.append(url)
        return 200, "User-agent: *\nAllow: /\n"

    policy = RobotsPolicy(fetcher, user_agent="ContestScout")
    for _ in range(4):
        policy.check(THINKGOOD + "/thinkgood/user/contest/index.do")
    assert calls == [THINKGOOD + "/robots.txt"]


def test_disabled_policy_allows_everything() -> None:
    policy = RobotsPolicy(
        lambda url: (403, ""), user_agent="ContestScout", enabled=False
    )
    assert policy.check(THINKGOOD + "/anything").state is RobotsState.ALLOW


def test_crawl_delay_is_read() -> None:
    body = "User-agent: *\nCrawl-delay: 3\nAllow: /\n"
    policy = policy_for(LINKAREER, 200, body)
    assert policy.report_for(LINKAREER + "/list/contest").crawl_delay == 3.0


# --- 파서 단위 동작 ------------------------------------------------------ #
def test_longest_match_wins_over_order() -> None:
    body = "User-agent: *\nAllow: /\nDisallow: /private/\nAllow: /private/public/\n"
    policy = policy_for(LINKAREER, 200, body)
    assert policy.check(LINKAREER + "/private/x").state is RobotsState.DENY
    assert policy.check(LINKAREER + "/private/public/x").state is RobotsState.ALLOW


def test_empty_disallow_means_no_restriction() -> None:
    policy = policy_for(LINKAREER, 200, "User-agent: *\nDisallow:\n")
    assert policy.check(LINKAREER + "/anything").state is RobotsState.ALLOW


def test_no_matching_group_allows_everything() -> None:
    policy = policy_for(LINKAREER, 200, "User-agent: EvilBot\nDisallow: /\n")
    assert policy.check(LINKAREER + "/list/contest").state is RobotsState.ALLOW


def test_query_string_is_considered() -> None:
    body = "User-agent: *\nAllow: /\nDisallow: /*?draft=1\n"
    policy = policy_for(LINKAREER, 200, body)
    assert policy.check(LINKAREER + "/page?draft=1").state is RobotsState.DENY
    assert policy.check(LINKAREER + "/page?draft=0").state is RobotsState.ALLOW
