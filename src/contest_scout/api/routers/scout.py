"""Scout 실행 / 실행 이력.

``POST /api/scout/run`` 은 즉시 응답하고 실제 수집은 백그라운드 스레드에서 돈다.
프론트엔드는 ``GET /api/scout/status`` 를 폴링해 진행 상황을 그린다.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from contest_scout.api.deps import get_repo
from contest_scout.api.schemas import ScoutRunRequest
from contest_scout.repository import Repository
from contest_scout.services.scout import runner
from contest_scout.services.settings import load_settings
from contest_scout.sources import source_names

router = APIRouter(prefix="/api/scout", tags=["scout"])

RepoDep = Annotated[Repository, Depends(get_repo)]


@router.post("/run", status_code=202)
def run_scout(body: ScoutRunRequest | None = None) -> dict[str, Any]:
    body = body or ScoutRunRequest()
    settings = load_settings()

    selection = None
    if body.sources:
        unknown = [s for s in body.sources if s not in source_names()]
        if unknown:
            raise HTTPException(400, f"알 수 없는 소스: {', '.join(unknown)}")
        settings.enabled_sources = body.sources
        selection = ",".join(body.sources)

    outcome = runner.start(
        trigger="manual",
        settings=settings,
        source_selection=selection,
        pages=body.pages,
        limit=body.limit,
    )
    if not outcome["started"]:
        raise HTTPException(409, "이미 Scout이 실행 중입니다")
    return outcome["state"]


@router.get("/status")
def scout_status() -> dict[str, Any]:
    return runner.snapshot()


@router.get("/runs")
def runs(repo: RepoDep, limit: int = 30) -> list[dict[str, Any]]:
    return repo.runs(limit=limit)


@router.get("/runs/{run_id}")
def run_detail(run_id: int, repo: RepoDep) -> dict[str, Any]:
    item = repo.run(run_id)
    if item is None:
        raise HTTPException(404, f"실행 기록을 찾을 수 없습니다: {run_id}")
    return item
