"""소스 어댑터 레지스트리.

새 플랫폼을 추가하려면 :class:`~contest_scout.sources.base.BaseSource` 구현체를
만들고 아래 ``SOURCES`` 에 등록하기만 하면 CLI 옵션까지 자동으로 확장된다.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from contest_scout.sources.base import BaseSource
from contest_scout.sources.linkareer import LinkareerSource
from contest_scout.sources.thinkgood import ThinkgoodSource

if TYPE_CHECKING:  # pragma: no cover
    from contest_scout.http import SafeHttpClient

SOURCES: dict[str, type[BaseSource]] = {
    ThinkgoodSource.name: ThinkgoodSource,
    LinkareerSource.name: LinkareerSource,
}

__all__ = ["SOURCES", "BaseSource", "LinkareerSource", "ThinkgoodSource", "build_sources"]


def source_names() -> list[str]:
    return list(SOURCES)


def build_sources(selection: str, http: SafeHttpClient) -> list[BaseSource]:
    """``"all"`` 또는 소스 이름 → 어댑터 인스턴스 목록."""
    if selection == "all":
        names = source_names()
    else:
        names = [n.strip() for n in selection.split(",") if n.strip()]
    unknown = [n for n in names if n not in SOURCES]
    if unknown:
        raise KeyError(f"알 수 없는 소스: {', '.join(unknown)}")
    return [SOURCES[name](http) for name in names]
