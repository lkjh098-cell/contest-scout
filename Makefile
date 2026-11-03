# Contest Scout — 자주 쓰는 명령 모음
#
#   make install   의존성 설치
#   make dev       개발 모드 (Vite + FastAPI)
#   make start     빌드된 대시보드 실행
#   make crawl     터미널에서 수집만 실행
#   make test      Python 테스트
#
.DEFAULT_GOAL := start
PY := .venv/bin/python
export PYTHONPATH := $(CURDIR)/src

.PHONY: install dev start build crawl doctor test typecheck clean

install:
	python3 -m venv .venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -e ".[dev]"
	cd web && npm install --no-audit --no-fund

dev:
	./start.sh dev

start:
	./start.sh

build:
	./start.sh build

crawl:
	$(PY) -m contest_scout crawl --source all

doctor:
	$(PY) -m contest_scout doctor

test:
	$(PY) -m pytest

typecheck:
	cd web && npx tsc -b --noEmit

clean:
	rm -rf web/dist web/node_modules .venv
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
