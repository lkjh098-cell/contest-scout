"""참가 중 프로젝트 (Contest Builder 연결 지점).

`참가하기` 를 누르면 공모전 상태가 ENTERING 으로 바뀌고 여기 레코드가 생긴다.
Builder 본체는 아직 없지만, 넘겨줄 데이터 모양은 지금 확정해 둔다.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from contest_scout.api.deps import get_repo
from contest_scout.api.schemas import ProjectCreate, ProjectPatch
from contest_scout.models import ContestStatus
from contest_scout.repository import Repository
from contest_scout.schema_ext import PROJECT_STAGES

router = APIRouter(prefix="/api/projects", tags=["projects"])

RepoDep = Annotated[Repository, Depends(get_repo)]


@router.get("")
def list_projects(repo: RepoDep) -> dict[str, Any]:
    return {"items": repo.list_projects(), "stages": PROJECT_STAGES}


@router.post("", status_code=201)
def create_project(body: ProjectCreate, repo: RepoDep) -> dict[str, Any]:
    project = repo.create_project(body.contest_key)
    if project is None:
        raise HTTPException(404, f"공모전을 찾을 수 없습니다: {body.contest_key}")
    repo.set_status(body.contest_key, ContestStatus.ENTERING)
    return project


@router.patch("/{contest_key:path}")
def patch_project(contest_key: str, body: ProjectPatch, repo: RepoDep) -> dict[str, Any]:
    try:
        project = repo.update_project(
            contest_key, stage=body.stage, next_action=body.next_action
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if project is None:
        raise HTTPException(404, f"프로젝트를 찾을 수 없습니다: {contest_key}")
    if body.stage == "SUBMITTED":
        repo.set_status(contest_key, ContestStatus.SUBMITTED)
    return project


@router.delete("/{contest_key:path}", status_code=204)
def delete_project(contest_key: str, repo: RepoDep) -> None:
    if not repo.delete_project(contest_key):
        raise HTTPException(404, f"프로젝트를 찾을 수 없습니다: {contest_key}")
