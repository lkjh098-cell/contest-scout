"""CLI와 HTTP API가 함께 쓰는 서비스 레이어.

    CLI ─┐
         ├─→ services ─→ crawl / db / evaluators
    API ─┘

크롤링 로직을 UI 쪽에 다시 구현하지 않기 위한 층이다. 여기 있는 함수는
FastAPI에 의존하지 않으므로 CLI에서도 그대로 호출된다.
"""

from contest_scout.services.settings import (
    AppSettings,
    load_settings,
    profile_hash,
    read_profile_document,
    save_settings,
    write_profile_document,
)

__all__ = [
    "AppSettings",
    "load_settings",
    "profile_hash",
    "read_profile_document",
    "save_settings",
    "write_profile_document",
]
