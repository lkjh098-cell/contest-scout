#!/usr/bin/env python3
"""개발용 시드 데이터 주입기.

화면 작업을 하려는데 마침 새 공모전이 없거나 네트워크를 쓸 수 없을 때 쓴다.
**앱 본체에는 가짜 공모전이 하나도 들어 있지 않다.** 여기서 넣는 데이터도
지어낸 것이 아니라 테스트 픽스처에 저장해 둔 실제 씽굿 응답을 그대로 파싱한
것이고, 기본 DB가 아니라 별도 파일에 들어간다.

    python scripts/seed_dev_db.py                      # data/dev.sqlite3 생성
    CONTEST_SCOUT_DB=data/dev.sqlite3 ./start.sh       # 그 DB로 대시보드 실행
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from contest_scout.config import load_profile  # noqa: E402
from contest_scout.db import Database  # noqa: E402
from contest_scout.evaluators.rules import RuleEvaluator  # noqa: E402
from contest_scout.repository import Repository  # noqa: E402
from contest_scout.schema_ext import upsert_score  # noqa: E402
from contest_scout.sources.thinkgood import ThinkgoodSource  # noqa: E402
from contest_scout.taxonomy import tags_for  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "thinkgood_live_sample.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="data/dev.sqlite3", help="만들 DB 경로")
    args = parser.parse_args()

    payload = json.loads(FIXTURE.read_text("utf-8"))
    rows = payload.get("listJsonData") or []
    if not rows:
        print("픽스처에 공모전이 없습니다.", file=sys.stderr)
        return 1

    source = ThinkgoodSource.__new__(ThinkgoodSource)  # HTTP 클라이언트 없이 정규화만
    source.http = None  # type: ignore[assignment]

    profile = load_profile()
    evaluator = RuleEvaluator(profile)

    db_path = Path(args.db)
    with Database(db_path) as db:
        repo = Repository(db)
        run_id = db.start_run(["thinkgood"])
        new_count = 0
        for row in rows:
            pk = row.get("contest_pk")
            if pk in (None, ""):
                continue
            url = f"https://www.thinkcontest.com/thinkgood/user/contest/view.do?contest_pk={pk}"
            contest = source._normalize(row, url)
            if db.upsert(contest):
                new_count += 1
            evaluation = evaluator.evaluate(contest)
            db.save_recommendation(run_id, contest.key, evaluation)
            upsert_score(db.conn, contest.key, evaluation)
            repo.replace_tags(contest.key, tags_for(contest))
        db.conn.commit()
        db.finish_run(
            run_id,
            total_new=new_count,
            total_seen=len(rows),
            requests=0,
            stats={
                "thinkgood": {
                    "source": "thinkgood",
                    "robots": "ALLOW",
                    "list_pages": 1,
                    "discovered": len(rows),
                    "new": new_count,
                    "existing": len(rows) - new_count,
                    "details_fetched": 0,
                    "requests": 0,
                    "errors": 0,
                    "skipped_reason": None,
                }
            },
        )
        db.expire_past_deadline()

    print(f"{db_path} 에 공모전 {new_count}건을 넣었습니다 (픽스처 {len(rows)}건).")
    print(f"실행:  CONTEST_SCOUT_DB={db_path} ./start.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
