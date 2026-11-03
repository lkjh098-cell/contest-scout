#!/usr/bin/env bash
#
# Contest Scout 실행기.
#
#   ./start.sh          설치 → 프론트엔드 빌드 → http://localhost:3000 하나로 서비스
#   ./start.sh dev      코드 수정용. Vite(3000) + FastAPI(8000) 를 함께 띄운다.
#   ./start.sh build    프론트엔드만 다시 빌드
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

VENV="$ROOT/.venv"
PY="$VENV/bin/python"
APP_PORT="${CONTEST_SCOUT_PORT:-3000}"
API_PORT="${CONTEST_SCOUT_API_PORT:-8000}"
MODE="${1:-start}"

# 패키지를 editable로 깔아도 일부 환경에서 경로가 안 잡히는 경우가 있어 못을 박아 둔다.
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

bold() { printf "\033[1m%s\033[0m\n" "$1"; }
info() { printf "  %s\n" "$1"; }
die()  { printf "\033[31m%s\033[0m\n" "$1" >&2; exit 1; }

need() {
  command -v "$1" >/dev/null 2>&1 || die "$1 이(가) 필요합니다. $2"
}

# ---------------------------------------------------------------------- #
# 준비
# ---------------------------------------------------------------------- #
ensure_python() {
  need python3 "https://www.python.org/downloads/ 에서 3.11 이상을 설치하세요."
  if [ ! -x "$PY" ]; then
    bold "Python 가상환경을 만듭니다"
    python3 -m venv "$VENV"
  fi
  if ! "$PY" -c "import fastapi" >/dev/null 2>&1; then
    bold "Python 패키지를 설치합니다"
    "$PY" -m pip install --quiet --upgrade pip
    "$PY" -m pip install --quiet -e ".[dev]"
  fi
}

ensure_node() {
  need node "https://nodejs.org 에서 Node 20 이상을 설치하세요."
  need npm "Node를 설치하면 함께 들어옵니다."
  if [ ! -d "$ROOT/web/node_modules" ]; then
    bold "프론트엔드 패키지를 설치합니다 (처음 한 번, 1~2분)"
    (cd "$ROOT/web" && npm install --no-audit --no-fund)
  fi
}

# web/src 가 dist 보다 새로우면 다시 빌드한다.
needs_build() {
  [ ! -f "$ROOT/web/dist/index.html" ] && return 0
  [ -n "$(find "$ROOT/web/src" "$ROOT/web/index.html" "$ROOT/web/package.json" \
          -newer "$ROOT/web/dist/index.html" -print -quit 2>/dev/null)" ]
}

build_web() {
  bold "프론트엔드를 빌드합니다"
  (cd "$ROOT/web" && npm run build)
}

open_browser() {
  local url="$1"
  ( sleep 2.5
    if command -v open >/dev/null 2>&1; then open "$url" >/dev/null 2>&1 || true; fi
  ) &
}

# ---------------------------------------------------------------------- #
# 모드
# ---------------------------------------------------------------------- #
case "$MODE" in
  build)
    ensure_node
    build_web
    ;;

  dev)
    ensure_python
    ensure_node
    bold "개발 모드"
    info "화면  http://localhost:$APP_PORT   (Vite · 저장하면 즉시 반영)"
    info "API   http://localhost:$API_PORT/docs"
    echo

    CONTEST_SCOUT_WEB_DIST="/dev/null" \
      "$PY" -m uvicorn contest_scout.api.app:app \
      --host 127.0.0.1 --port "$API_PORT" --reload --reload-dir "$ROOT/src" &
    API_PID=$!
    trap 'kill $API_PID 2>/dev/null || true' EXIT INT TERM

    open_browser "http://localhost:$APP_PORT"
    (cd "$ROOT/web" && CONTEST_SCOUT_API="http://127.0.0.1:$API_PORT" npm run dev -- --port "$APP_PORT")
    ;;

  start|"")
    ensure_python
    # 빌드된 화면이 이미 있고 소스가 그대로면 Node 없이도 실행된다.
    if needs_build; then
      ensure_node
      build_web
    fi

    bold "Contest Scout"
    info "화면  http://localhost:$APP_PORT"
    info "API   http://localhost:$APP_PORT/docs"
    info "종료  Ctrl+C"
    echo

    open_browser "http://localhost:$APP_PORT"
    exec "$PY" -m uvicorn contest_scout.api.app:app \
      --host 127.0.0.1 --port "$APP_PORT" --log-level warning
    ;;

  *)
    die "알 수 없는 명령: $MODE  (start | dev | build)"
    ;;
esac
