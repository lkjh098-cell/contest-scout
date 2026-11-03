"""소스 어댑터 공통 인터페이스.

새 플랫폼(위비티, 콘테스트코리아 …)을 붙일 때는 :class:`BaseSource` 를 상속해
``discover`` 와 ``fetch_detail`` 두 개만 구현하면 된다.

Incremental crawl 계약:

* ``discover(page)`` 는 목록 요청 **1회**로 :class:`ContestRef` 목록을 돌려준다.
* 오케스트레이터가 DB와 비교해 신규 ref만 골라 ``fetch_detail(ref)`` 를 호출한다.
* 이미 상세 정보를 목록 응답에서 받은 소스는 ``needs_detail_request = False`` 로
  선언하고, ``fetch_detail`` 안에서 추가 HTTP 요청 없이 정규화만 한다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from contest_scout.models import Contest, ContestRef

if TYPE_CHECKING:  # pragma: no cover
    from contest_scout.http import SafeHttpClient


class BaseSource(ABC):
    #: 어댑터 식별자 (DB / CLI에서 쓰는 이름).
    name: str
    #: robots.txt 판정을 위해 대표로 검사할 URL.
    entry_url: str
    #: 상세 정보를 위해 별도 요청이 필요한가?
    needs_detail_request: bool = True

    def __init__(self, http: SafeHttpClient) -> None:
        self.http = http

    @abstractmethod
    def discover(self, page: int = 1) -> list[ContestRef]:
        """목록 1페이지를 읽어 식별 정보만 뽑는다."""

    @abstractmethod
    def fetch_detail(self, ref: ContestRef) -> Contest:
        """신규 공모전 1건을 정규화된 :class:`Contest` 로 만든다."""
