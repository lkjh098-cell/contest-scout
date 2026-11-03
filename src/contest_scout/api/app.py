"""FastAPI 애플리케이션.

개발 중에는 Vite(3000)가 프론트를 서빙하고 ``/api`` 만 이 서버(8000)로 프록시된다.
``npm run build`` 로 만든 ``web/dist`` 가 있으면 이 서버가 그대로 정적 파일까지
서빙하므로, 배포 시에는 프로세스 하나로 끝난다.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from contest_scout import __version__, paths
from contest_scout.api.routers import contests, dashboard, insights, projects, scout, settings
from contest_scout.db import Database
from contest_scout.services.scheduler import scheduler
from contest_scout.services.scout import sync_scores

log = logging.getLogger(__name__)

ENV_WEB_DIST = "CONTEST_SCOUT_WEB_DIST"
DEV_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


def _web_dist() -> Path | None:
    raw = os.environ.get(ENV_WEB_DIST)
    candidates = [Path(raw)] if raw else [Path("web/dist"), Path(__file__).resolve().parents[3] / "web" / "dist"]
    for candidate in candidates:
        if candidate.is_dir() and (candidate / "index.html").is_file():
            return candidate
    return None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    paths.ensure_dirs()
    try:
        with Database(paths.db_path(), check_same_thread=False) as db:
            synced = sync_scores(db)
        if synced:
            log.info("기존 공모전 %s건의 점수·태그를 동기화했습니다", synced)
    except Exception:  # noqa: BLE001 - 동기화 실패로 서버가 안 뜨면 곤란하다
        log.exception("시작 시 점수 동기화 실패")
    scheduler.start()
    yield
    scheduler.stop()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Contest Scout API",
        version=__version__,
        description="공모전 자동 탐색·추천 엔진의 HTTP 인터페이스",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=DEV_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    for module in (dashboard, contests, scout, insights, settings, projects):
        app.include_router(module.router)

    @app.get("/api/health", tags=["meta"])
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "version": __version__,
            "db": str(paths.db_path()),
            "db_exists": paths.db_path().is_file(),
        }

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("처리되지 않은 오류: %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "요청을 처리하지 못했습니다.",
                "technical": f"{type(exc).__name__}: {exc}",
            },
        )

    dist = _web_dist()
    if dist is not None:
        log.info("정적 파일 서빙: %s", dist)
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa(full_path: str) -> FileResponse:
            candidate = dist / full_path
            if full_path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(dist / "index.html")

    return app


app = create_app()

__all__ = ["app", "create_app"]
