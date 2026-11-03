"""Analytics / Sources 화면 데이터."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from contest_scout.api.deps import get_repo
from contest_scout.repository import Repository

router = APIRouter(prefix="/api", tags=["insights"])

RepoDep = Annotated[Repository, Depends(get_repo)]


@router.get("/analytics")
def analytics(repo: RepoDep) -> dict[str, Any]:
    return repo.analytics()


@router.get("/sources")
def sources(repo: RepoDep) -> list[dict[str, Any]]:
    return repo.sources_overview()
