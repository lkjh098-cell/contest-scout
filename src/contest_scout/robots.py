"""robots.txt 처리.

**v0.1.x의 버그**: ``urllib.robotparser.RobotFileParser.read()`` 가 크롤러와 전혀
다른 경로(urllib, 기본 User-Agent)로 robots.txt를 따로 요청했다. 사이트가 기본
urllib UA를 막으면 curl로는 200이 나와도 파이썬에서는 실패 → 전 소스 SKIP.

이 모듈은 robots.txt를 **크롤러와 동일한 httpx client / 동일한 User-Agent**로
가져온 뒤 그 본문만 파싱한다. 결과는 ALLOW / DENY / UNKNOWN 세 상태로 관리한다.

파서도 직접 구현했다. ``urllib.robotparser`` 는 규칙을 **먼저 나온 순서대로**
매칭해서, 씽굿처럼 ``Allow: /`` 를 맨 위에 두고 그 아래에 ``Disallow`` 를 나열하는
robots.txt에서는 금지 경로까지 허용으로 판정한다. 여기서는 RFC 9309대로
**가장 긴(구체적인) 규칙이 이기고, 길이가 같으면 Allow가 이긴다.**
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol
from urllib.parse import unquote, urlparse

log = logging.getLogger(__name__)


class RobotsState(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    UNKNOWN = "UNKNOWN"


# --------------------------------------------------------------------- #
# robots.txt 파서 (RFC 9309 스타일 longest-match)
# --------------------------------------------------------------------- #
@dataclass(slots=True)
class _Rule:
    allow: bool
    pattern: str
    regex: re.Pattern[str]

    @property
    def specificity(self) -> int:
        return len(self.pattern)


@dataclass(slots=True)
class _Group:
    agents: list[str] = field(default_factory=list)
    rules: list[_Rule] = field(default_factory=list)
    crawl_delay: float | None = None


def _compile_pattern(pattern: str) -> re.Pattern[str]:
    """``/foo*bar$`` 형태의 robots 경로 패턴을 정규식으로."""
    anchored_end = pattern.endswith("$")
    body = pattern[:-1] if anchored_end else pattern
    parts = [re.escape(chunk) for chunk in body.split("*")]
    regex = ".*".join(parts)
    return re.compile("^" + regex + ("$" if anchored_end else ""))


def parse_robots_txt(body: str) -> list[_Group]:
    groups: list[_Group] = []
    current: _Group | None = None
    expecting_agent = False

    for raw_line in body.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field_name, _, value = line.partition(":")
        key = field_name.strip().lower()
        value = value.strip()

        if key == "user-agent":
            if current is None or not expecting_agent:
                current = _Group()
                groups.append(current)
                expecting_agent = True
            current.agents.append(value.lower())
            continue

        if current is None:
            continue
        expecting_agent = False

        if key in ("allow", "disallow"):
            if key == "disallow" and value == "":
                # "Disallow:" (빈 값) = 아무것도 금지하지 않음
                continue
            if not value.startswith("/"):
                value = "/" + value
            current.rules.append(_Rule(key == "allow", value, _compile_pattern(value)))
        elif key == "crawl-delay":
            try:
                current.crawl_delay = float(value)
            except ValueError:
                pass

    return groups


def select_group(groups: list[_Group], user_agent: str) -> _Group | None:
    """UA에 가장 잘 맞는 그룹. 정확 매칭이 없으면 ``*`` 그룹."""
    ua = user_agent.lower()
    best: tuple[int, _Group] | None = None
    wildcard: _Group | None = None

    for group in groups:
        for agent in group.agents:
            if agent == "*":
                if wildcard is None:
                    wildcard = group
                continue
            if ua.startswith(agent) or agent in ua:
                if best is None or len(agent) > best[0]:
                    best = (len(agent), group)

    if best is not None:
        return best[1]
    return wildcard


def group_allows(group: _Group | None, path: str) -> bool:
    """가장 구체적인 규칙이 이긴다. 동률이면 Allow."""
    if group is None or not group.rules:
        return True
    best: _Rule | None = None
    for rule in group.rules:
        if not rule.regex.match(path):
            continue
        if best is None:
            best = rule
        elif rule.specificity > best.specificity:
            best = rule
        elif rule.specificity == best.specificity and rule.allow:
            best = rule
    return True if best is None else best.allow


def path_of(url: str) -> str:
    """robots 규칙과 비교할 경로.

    ``urlparse`` 는 ``/a.do;jsessionid=X`` 의 ``;jsessionid=X`` 를 ``params`` 로
    떼어내기 때문에, robots.txt의 ``Disallow: /*;jsessionid=*`` 규칙이 걸리지
    않는다. 여기서는 다시 붙여 원래 경로 문자열을 복원한다.
    """
    parsed = urlparse(url)
    path = parsed.path or "/"
    if parsed.params:
        path = f"{path};{parsed.params}"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    return unquote(path)


# --------------------------------------------------------------------- #
# 정책
# --------------------------------------------------------------------- #
@dataclass(slots=True)
class RobotsReport:
    """origin 단위 robots.txt 조회 결과."""

    origin: str
    state: RobotsState
    detail: str
    crawl_delay: float | None = None
    groups: list[_Group] | None = None

    def __str__(self) -> str:
        return f"{self.state.value} ({self.detail})"


class _Fetcher(Protocol):
    def __call__(self, url: str) -> tuple[int, str]: ...


def origin_of(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def evaluate_response(origin: str, status_code: int, body: str) -> RobotsReport:
    """HTTP 응답 하나를 robots 판정으로 변환 (네트워크 없음 → 테스트 가능)."""
    if status_code in (401, 403):
        # 접근이 통제된 robots.txt = 전체 크롤 금지로 해석 (RFC 9309).
        return RobotsReport(origin, RobotsState.DENY, f"robots.txt {status_code}")

    if status_code in (404, 410):
        # robots.txt 자체가 없음 = 제한 없음.
        return RobotsReport(origin, RobotsState.ALLOW, f"no robots.txt ({status_code})")

    if 500 <= status_code <= 599:
        return RobotsReport(origin, RobotsState.UNKNOWN, f"server error {status_code}")

    if status_code != 200:
        return RobotsReport(origin, RobotsState.UNKNOWN, f"unexpected status {status_code}")

    try:
        groups = parse_robots_txt(body)
    except Exception as exc:  # pragma: no cover
        return RobotsReport(origin, RobotsState.UNKNOWN, f"parse error: {exc}")

    return RobotsReport(origin, RobotsState.ALLOW, "parsed 200", groups=groups)


class RobotsPolicy:
    """origin별 robots.txt 캐시 + 경로 판정."""

    def __init__(self, fetcher: _Fetcher, user_agent: str, enabled: bool = True) -> None:
        self._fetch = fetcher
        self.user_agent = user_agent
        self.enabled = enabled
        self._cache: dict[str, RobotsReport] = {}

    def report_for(self, url: str) -> RobotsReport:
        origin = origin_of(url)
        if not self.enabled:
            return RobotsReport(origin, RobotsState.ALLOW, "robots check disabled")
        cached = self._cache.get(origin)
        if cached is not None:
            return cached

        try:
            status_code, body = self._fetch(f"{origin}/robots.txt")
        except Exception as exc:  # noqa: BLE001
            report = RobotsReport(origin, RobotsState.UNKNOWN, f"network error: {exc}")
        else:
            report = evaluate_response(origin, status_code, body)
            if report.groups is not None:
                group = select_group(report.groups, self.user_agent)
                if group is not None:
                    report.crawl_delay = group.crawl_delay

        self._cache[origin] = report
        log.info("robots %s -> %s", origin, report)
        return report

    def check(self, url: str) -> RobotsReport:
        """URL 하나에 대한 최종 판정 (경로 규칙까지 적용)."""
        report = self.report_for(url)
        if report.state is not RobotsState.ALLOW or report.groups is None:
            return report

        group = select_group(report.groups, self.user_agent)
        if group_allows(group, path_of(url)):
            return report
        return RobotsReport(
            report.origin,
            RobotsState.DENY,
            f"disallowed path for UA {self.user_agent!r}",
            crawl_delay=report.crawl_delay,
            groups=report.groups,
        )

    def allowed(self, url: str) -> bool:
        return self.check(url).state is RobotsState.ALLOW
