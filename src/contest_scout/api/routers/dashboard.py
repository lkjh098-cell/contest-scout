"""Overview 화면 데이터."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from contest_scout.api.deps import get_repo
from contest_scout.repository import Repository
from contest_scout.services.scheduler import scheduler
from contest_scout.services.scout import runner

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard")
def dashboard(repo: Annotated[Repository, Depends(get_repo)]) -> dict[str, Any]:
    data = repo.dashboard()
    data["scout"] = runner.snapshot()
    data["schedule"] = scheduler.status()
    return data
