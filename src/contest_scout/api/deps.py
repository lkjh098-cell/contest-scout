"""요청 단위 의존성.

SQLite 커넥션은 스레드에 묶인다. FastAPI가 요청을 워커 스레드에 흩뿌리므로
커넥션을 전역으로 공유하지 않고 **요청마다 열고 닫는다**. 로컬 SQLite에서는
연결 비용이 무시할 수준이라 이 방식이 가장 안전하다.
"""

from __future__ import annotations

from typing import Iterator

from contest_scout import paths
from contest_scout.db import Database
from contest_scout.repository import Repository


def get_repo() -> Iterator[Repository]:
    with Database(paths.db_path(), check_same_thread=False) as db:
        yield Repository(db)


__all__ = ["get_repo"]
