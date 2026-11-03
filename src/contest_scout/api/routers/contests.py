"""공모전 목록 / 상세 / 상태 전환."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from contest_scout.api.deps import get_repo
from contest_scout.api.schemas import StatusUpdate
from contest_scout.models import ContestStatus
from contest_scout.repository import ContestQuery, Repository

router = APIRouter(prefix="/api/contests", tags=["contests"])

RepoDep = Annotated[Repository, Depends(get_repo)]


@router.get("")
def list_contests(
    repo: RepoDep,
    q: str | None = None,
    tier: Annotated[list[str] | None, Query()] = None,
    tag: Annotated[list[str] | None, Query()] = None,
    source: Annotated[list[str] | None, Query()] = None,
    status: Annotated[list[str] | None, Query()] = None,
    min_prize: int | None = None,
    deadline_within: int | None = None,
    include_inactive: bool = False,
    only_new_today: bool = False,
    sort: str = "score",
    order: str = "desc",
    page: int = 1,
    page_size: int = 30,
) -> dict[str, Any]:
    return repo.list_contests(
        ContestQuery(
            q=q,
            tiers=tier or [],
            tags=tag or [],
            sources=source or [],
            statuses=status or [],
            min_prize=min_prize,
            deadline_within=deadline_within,
            include_inactive=include_inactive,
            only_new_today=only_new_today,
            sort=sort,
            order=order,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/facets")
def facets(repo: RepoDep) -> dict[str, Any]:
    return repo.facets()


@router.get("/{contest_key:path}")
def get_contest(contest_key: str, repo: RepoDep) -> dict[str, Any]:
    item = repo.get_contest(contest_key)
    if item is None:
        raise HTTPException(status_code=404, detail=f"공모전을 찾을 수 없습니다: {contest_key}")
    return item


@router.patch("/{contest_key:path}/status")
def set_status(contest_key: str, body: StatusUpdate, repo: RepoDep) -> dict[str, Any]:
    updated = repo.set_status(contest_key, ContestStatus(body.status))
    if updated is None:
        raise HTTPException(status_code=404, detail=f"공모전을 찾을 수 없습니다: {contest_key}")
    return updated
