from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def load_text(name: str) -> str:
    return (FIXTURES / name).read_text("utf-8")


def load_json(name: str) -> Any:
    return json.loads(load_text(name))


class FakeHttp:
    """SafeHttpClient 대역. 네트워크 없이 소스 어댑터를 돌린다."""

    def __init__(
        self,
        texts: dict[str, str] | None = None,
        json_payloads: dict[str, Any] | None = None,
    ) -> None:
        self.texts = texts or {}
        self.json_payloads = json_payloads or {}
        self.request_count = 0
        self.calls: list[tuple[str, str]] = []

    def get_text(self, url: str, **_: Any) -> str:
        self.calls.append(("GET", url))
        self.request_count += 1
        for prefix, body in self.texts.items():
            if url.startswith(prefix):
                return body
        raise AssertionError(f"예상하지 못한 GET: {url}")

    def post_json(self, url: str, payload: dict[str, Any]) -> Any:
        self.calls.append(("POST", url))
        self.request_count += 1
        for prefix, body in self.json_payloads.items():
            if url.startswith(prefix):
                return body
        raise AssertionError(f"예상하지 못한 POST: {url}")


@pytest.fixture()
def thinkgood_payload() -> Any:
    return load_json("thinkgood_sublist.json")


@pytest.fixture()
def linkareer_list_html() -> str:
    return load_text("linkareer_list.html")


@pytest.fixture()
def linkareer_detail_html() -> str:
    return load_text("linkareer_detail.html")
