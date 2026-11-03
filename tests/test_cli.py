"""CLI 표면 테스트 (네트워크 없음)."""

from __future__ import annotations

import pytest

from contest_scout.cli import build_parser, main
from contest_scout.db import Database
from contest_scout.models import ContestStatus
from tests.test_db_and_scoring import make_contest


def test_help_lists_subcommands(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for command in ("crawl", "doctor", "list", "mark", "sources"):
        assert command in out


def test_crawl_flags_exist() -> None:
    parser = build_parser()
    args = parser.parse_args(
        ["crawl", "--source", "thinkgood", "--pages", "2", "--limit", "5"]
    )
    assert args.source == "thinkgood"
    assert args.pages == 2
    assert args.limit == 5
    assert args.ignore_robots is False


def test_sources_command(capsys) -> None:
    assert main(["sources"]) == 0
    out = capsys.readouterr().out
    assert "thinkgood" in out and "linkareer" in out


def test_mark_and_list_roundtrip(tmp_path, capsys) -> None:
    db_path = tmp_path / "cli.sqlite3"
    with Database(db_path) as db:
        db.upsert(make_contest())

    assert main(["mark", "thinkgood:1", "IGNORE", "--db", str(db_path)]) == 0
    capsys.readouterr()

    assert main(["list", "--db", str(db_path), "--status", "IGNORE"]) == 0
    out = capsys.readouterr().out
    assert "thinkgood:1" in out
    assert ContestStatus.IGNORE.value in out


def test_mark_unknown_key_fails(tmp_path, capsys) -> None:
    db_path = tmp_path / "cli.sqlite3"
    Database(db_path).close()
    assert main(["mark", "nope:1", "IGNORE", "--db", str(db_path)]) == 1
