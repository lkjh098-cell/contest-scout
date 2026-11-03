"""실행 경로 해석.

CLI 기본값(``data/`` , ``config/`` 상대 경로)을 그대로 유지하되, 환경변수로
덮어쓸 수 있게 한다. 나중에 컨테이너/클라우드로 옮길 때 코드를 고치지 않고
경로만 바꾸면 되도록 하는 것이 목적이다.
"""

from __future__ import annotations

import os
from pathlib import Path

ENV_DB = "CONTEST_SCOUT_DB"
ENV_CONFIG_DIR = "CONTEST_SCOUT_CONFIG_DIR"
ENV_DATA_DIR = "CONTEST_SCOUT_DATA_DIR"


def data_dir() -> Path:
    return Path(os.environ.get(ENV_DATA_DIR, "data"))


def config_dir() -> Path:
    return Path(os.environ.get(ENV_CONFIG_DIR, "config"))


def db_path() -> Path:
    raw = os.environ.get(ENV_DB)
    return Path(raw) if raw else data_dir() / "contest_scout.sqlite3"


def report_path() -> Path:
    return data_dir() / "daily_report.md"


def profile_path() -> Path:
    return config_dir() / "profile.json"


def settings_path() -> Path:
    return config_dir() / "settings.json"


def ensure_dirs() -> None:
    data_dir().mkdir(parents=True, exist_ok=True)
    config_dir().mkdir(parents=True, exist_ok=True)


__all__ = [
    "config_dir",
    "data_dir",
    "db_path",
    "ensure_dirs",
    "profile_path",
    "report_path",
    "settings_path",
]
