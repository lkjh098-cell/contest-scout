"""예의 바른 HTTP 클라이언트.

- 명시적 User-Agent
- 요청 간 최소 간격(delay) + robots.txt의 Crawl-delay 반영
- 지수 백오프 재시도 (외부 의존성 없이 직접 구현)
- robots.txt 판정은 :mod:`contest_scout.robots` 에 위임하되, **동일한 client**로
  robots.txt를 가져온다.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Any

import httpx

from contest_scout import __version__
from contest_scout.robots import RobotsPolicy, RobotsReport, RobotsState

log = logging.getLogger(__name__)

DEFAULT_USER_AGENT = (
    f"ContestScout/{__version__} (+personal research; low-frequency daily crawler)"
)
#: robots.txt 규칙 매칭에 쓰는 짧은 토큰.
ROBOTS_USER_AGENT = "ContestScout"

RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})


class RobotsDisallowed(PermissionError):
    """robots.txt가 명시적으로 금지 → 이 소스는 건너뛴다."""


class RobotsUnknown(RuntimeError):
    """robots.txt를 확인할 수 없음 → 이번 회차만 안전하게 중단한다."""


class SafeHttpClient:
    def __init__(
        self,
        *,
        delay: float = 2.0,
        timeout: float = 20.0,
        max_retries: int = 3,
        respect_robots: bool = True,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self.delay = max(0.0, delay)
        self.max_retries = max(1, max_retries)
        self.user_agent = user_agent
        self.request_count = 0
        self._last_request = 0.0
        self._client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": user_agent,
                "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.7",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        self.robots = RobotsPolicy(
            fetcher=self._fetch_robots_txt,
            user_agent=ROBOTS_USER_AGENT,
            enabled=respect_robots,
        )

    # ------------------------------------------------------------------ #
    # 내부
    # ------------------------------------------------------------------ #
    def _throttle(self, extra: float = 0.0) -> None:
        wait = max(self.delay, extra)
        if wait <= 0:
            return
        elapsed = time.monotonic() - self._last_request
        if elapsed < wait:
            time.sleep(wait - elapsed)

    def _fetch_robots_txt(self, url: str) -> tuple[int, str]:
        """robots.txt도 크롤러와 같은 client/UA로 가져온다 (v0.1.x 버그의 원인)."""
        self._throttle()
        response = self._client.get(url)
        self._last_request = time.monotonic()
        self.request_count += 1
        return response.status_code, response.text

    def _guard(self, url: str) -> RobotsReport:
        report = self.robots.check(url)
        if report.state is RobotsState.DENY:
            raise RobotsDisallowed(f"robots.txt disallows {url} ({report.detail})")
        if report.state is RobotsState.UNKNOWN:
            raise RobotsUnknown(f"robots.txt could not be verified for {url} ({report.detail})")
        return report

    def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        report = self._guard(url)
        extra_delay = report.crawl_delay or 0.0
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            self._throttle(extra_delay)
            try:
                response = self._client.request(method, url, **kwargs)
                self._last_request = time.monotonic()
                self.request_count += 1
            except httpx.RequestError as exc:
                last_error = exc
            else:
                if response.status_code in RETRYABLE_STATUS:
                    last_error = httpx.HTTPStatusError(
                        f"{response.status_code} for {url}",
                        request=response.request,
                        response=response,
                    )
                else:
                    response.raise_for_status()
                    return response

            if attempt < self.max_retries:
                backoff = min(8.0, 2.0 ** (attempt - 1)) + random.uniform(0, 0.4)
                log.warning("retry %s/%s in %.1fs: %s", attempt, self.max_retries, backoff, url)
                time.sleep(backoff)

        assert last_error is not None
        raise last_error

    # ------------------------------------------------------------------ #
    # 공개 API
    # ------------------------------------------------------------------ #
    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self._request("GET", url, **kwargs)

    def get_text(self, url: str, **kwargs: Any) -> str:
        return self.get(url, **kwargs).text

    def post_json(self, url: str, payload: dict[str, Any]) -> Any:
        response = self._request(
            "POST",
            url,
            json=payload,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        return response.json()

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> SafeHttpClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
