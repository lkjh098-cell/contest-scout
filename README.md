# Contest Scout v0.3.0

매일 국내 공모전 사이트를 확인해 **어제 이후 새로 올라온 공모전만** 수집하고,
개인 역량·상금·수상가치·제작 난이도를 100점으로 평가해 **S / A / B / SKIP** 등급으로
추천하는 개인용 공모전 스카우트.

v0.3.0부터는 터미널 없이 **웹 대시보드**에서 전부 처리한다. 수집 엔진은 그대로다.

> Contest Scout의 역할은 *무엇을 만들 것인가*가 아니라
> **어떤 공모전에 시간을 투자할 것인가**를 판단하는 것이다.

---

## 빠른 시작

```bash
cd contest-scout
bash ./start.sh
```

처음 실행하면 Python 가상환경을 만들고, 브라우저에서 <http://localhost:3000> 을 연다.

GitHub 소스판은 **Python 3.11+와 Node 20+**가 필요하다. 빌드 산출물은 포함하지
않으며, `bash ./start.sh`를 처음 실행하면 화면 패키지 설치와 빌드를 진행한다.

공개 소스에는 개인 설정, 수집 DB와 리포트, 인증키를 포함하지 않는다.
처음 실행하면 빈 상태로 시작하며, 오른쪽 위 **Scout 실행**으로 공모전을 수집할 수 있다.
수집 시간과 결과는 대상 사이트의 응답 및 접근 정책에 따라 달라진다.

```bash
bash ./start.sh dev      # 코드 수정용 — Vite(3000) + FastAPI(8000), 저장 시 즉시 반영
bash ./start.sh build    # 프론트엔드만 다시 빌드
make test           # 테스트
```

---

## 화면

| 화면 | 하는 일 |
| --- | --- |
| **오늘의 브리핑** | 오늘 신규·S등급·마감 임박 건수, 추천 상위 5건, 기회 매트릭스 |
| **공모전 탐색** | 등급·분야·상금·마감·소스 필터. 카드/표 전환 |
| **전체 공모전** | 상태별 탭이 있는 밀집 표. 정렬·검색 |
| **Shortlist** | 담아 둔 공모전 |
| **참가 중** | 참가하기로 정한 공모전의 진행 단계 관리 |
| **Analytics** | 발견 추이, 분야·상금·마감 분포, 선택 패턴 |
| **Scout 실행 기록** | 회차별 소스 통계, robots 판정, 실패 사유 |
| **소스** | 수집 대상 사이트 상태 |
| **설정** | 수집 간격, 자동 실행, 100점 배점 조정 |

공모전 하나를 누르면 점수 9개 항목의 분해, 왜 나갈 만한지, 무엇을 확인해야 하는지,
예상 작업량, 공고 원문을 한 화면에서 볼 수 있다.

### 상태 흐름

```
NEW ─→ RECOMMENDED ─→ INTERESTED ─→ ENTERING ─→ SUBMITTED
                           └────────→ IGNORE
마감일이 지나면 자동으로 EXPIRED
```

UI에서 `Shortlist` 로 부르는 상태의 DB 값은 `INTERESTED` 다. 엔진과 CLI가 쓰던
이름을 그대로 두고 표시만 바꾼 것이라, API는 `SHORTLISTED` 로 보내도 받아 준다.

`참가하기` 를 누르면 상태가 `ENTERING` 으로 바뀌고 `projects` 레코드가 생긴다.
Contest Builder에 넘길 데이터(제목·요강·마감·참가자격)를 미리 확정해 둔 자리다.

---

## 아키텍처

```
        React + TypeScript (web/)
                  │  REST
                  ▼
        FastAPI  (src/contest_scout/api/)
                  │
                  ▼
        services / repository          ← CLI와 공유
                  │
                  ▼
        crawl · sources · evaluators   ← 기존 엔진 (그대로)
                  │
                  ▼
              SQLite
```

수집 로직은 대시보드용으로 다시 구현하지 않았다. CLI의 `contest-scout crawl` 과
대시보드의 `Scout 실행` 은 **같은 함수**(`services.scout.run_scout`)를 호출한다.
API를 통째로 걷어내도 CLI는 그대로 돌아간다.

프론트엔드는 SQL을 모른다. 화면이 쓰는 모양은 전부
`src/contest_scout/repository.py` 한 곳에서 만든다.

### 실행 방식 두 가지

| | 프론트엔드 | 백엔드 | 주소 |
| --- | --- | --- | --- |
| `bash ./start.sh` | 빌드된 정적 파일을 FastAPI가 서빙 | 같은 프로세스 | 3000 |
| `bash ./start.sh dev` | Vite 개발 서버 (HMR) | 별도 프로세스 | 3000 → 8000 프록시 |

---

## API

```
GET    /api/dashboard                    KPI · 추천 · 매트릭스
GET    /api/contests                     목록 (검색·필터·정렬·페이지)
GET    /api/contests/facets              필터에 쓸 후보값과 개수
GET    /api/contests/{key}               상세 + 점수 분해 + 상태 이력
PATCH  /api/contests/{key}/status        상태 변경
POST   /api/scout/run                    수집 시작 (202, 비동기)
GET    /api/scout/status                 진행 상황 (프론트가 폴링)
GET    /api/scout/runs                   실행 이력
GET    /api/sources                      소스 상태
GET    /api/analytics                    통계
GET    /api/settings                     설정 + 미구현 기능 플래그
PATCH  /api/settings                     설정 저장 (배점 변경 시 전체 재채점)
GET    /api/projects                     참가 중 프로젝트
POST   /api/projects                     `참가하기`
```

서버가 떠 있으면 <http://localhost:3000/docs> 에서 직접 호출해 볼 수 있다.

`/api/contests` 는 `canonical_key` 가 같은 공모전을 한 줄로 접어서 준다. 씽굿과
링커리어에 같은 공모전이 올라와도 목록에는 한 번만 나오고, `duplicate_sources` 에
어느 사이트에서 왔는지 담긴다. (같은 사이트 안의 중복 게시는 엔진이 별개 공모전으로
보므로 접지 않는다.)

---

## 명령어

| 명령 | 설명 |
|---|---|
| `contest-scout crawl` | 신규 공모전 수집 → DB 저장 → 평가 → Markdown 리포트 |
| `contest-scout doctor` | robots.txt 판정(ALLOW/DENY/UNKNOWN)과 목록 파싱 진단 |
| `contest-scout list` | 저장된 공모전 조회 (`--status NEW` 등) |
| `contest-scout mark` | 상태 변경 — `contest-scout mark thinkgood:110290 IGNORE` |
| `contest-scout sources` | 사용 가능한 소스 목록 |
| `contest-scout serve` | 대시보드 API 서버만 실행 (`--port`, `--reload`) |

### `crawl` 주요 옵션

```
--source {all,thinkgood,linkareer}  수집 대상 (쉼표 구분 가능)
--pages N                           목록 페이지 수 (기본 1)
--limit N                           소스당 신규 수집 상한
--db PATH                           기본 data/contest_scout.sqlite3
--report PATH                       기본 data/daily_report.md
--profile PATH                      기본 config/profile.json
--delay SECONDS                     요청 간 최소 간격 (기본 2.0)
--user-agent STRING                 사이트가 기본 UA를 막을 때만 변경
--ignore-robots                     권장하지 않음
-v / -vv                            로그 상세도 (파싱 경고 확인용)
```

### 상태 관리

```
NEW → RECOMMENDED → INTERESTED → ENTERING → SUBMITTED
                              ↘ IGNORE
                              ↘ EXPIRED (마감일 경과 시 자동)
```

`IGNORE`로 표시한 공모전은 다음 날 다시 추천되지 않는다. 링커리어와 씽굿에
동시에 올라온 같은 공모전은 하나의 canonical 그룹으로 묶이므로, 한쪽을 IGNORE하면
다른 쪽도 함께 숨겨진다.

`ENTERING`으로 바꾼 공모전이 이후 Contest Builder로 넘어갈 대상이다.

---

## 수집 방식

사이트 전체를 매일 훑지 않는다.

```
목록 요청 1회
    ↓
공모전 ID / URL / 제목 확인
    ↓
DB의 known_keys와 비교
    ↓
이미 본 공모전 → last_seen만 갱신 (요청 0회)
신규 공모전   → 상세 확보 → 정규화 → DB 저장 → 평가
```

**하루 실제 요청 수**

| 소스 | robots.txt | 목록 | 상세 | 신규 3건일 때 합계 |
|---|---:|---:|---:|---:|
| 씽굿 | 1 | 1 | 0 | **2** |
| 링커리어 | 1 | 1 | 3 | **5** |

- **씽굿**: 목록 페이지의 `<tbody id="dataList">`는 서버 HTML에서 비어 있고
  `POST /thinkgood/user/contest/subList.do`가 JSON으로 채운다. 이 JSON에는 상세
  요강(`competition_syllabus`)까지 들어 있어 **요청 1회로 상세까지 확보**된다.
  (v0.1.x가 씽굿에서 링크를 하나도 못 찾은 진짜 이유가 이것이다.)
- **링커리어**: Next.js SSR이라 목록 HTML에 JSON-LD `ItemList`가, 상세 HTML에
  `__NEXT_DATA__.__APOLLO_STATE__`가 들어 있다. CSS selector 대신 이 구조화
  데이터를 먼저 읽는다.

### 파서 안정성

selector 하나에 의존하지 않는다.

1. 구조화 데이터(JSON-LD / `__NEXT_DATA__` / JSON API)
2. semantic attribute
3. 안정적인 DOM 구조
4. 마지막 fallback (`<h1>`, `og:title`, 링크 정규식)

파싱에 실패한 필드는 조용히 빈 값으로 넘어가지 않고 `ParseWarning`으로 남는다.

```
ParseWarning[thinkgood] field=deadline reason=receive_period/finish_dt에서 마감일을 찾지 못함 url=...
```

`-v` 로 실행하거나 리포트 하단의 "파싱 경고" 섹션에서 확인할 수 있다.

---

## robots.txt 처리

**v0.1.3에서 두 사이트가 모두 SKIP된 원인**은 `urllib.robotparser.RobotFileParser.read()`가
크롤러와 **다른 경로**(urllib, 기본 User-Agent)로 robots.txt를 따로 요청한 것이었다.
curl로는 200이 나와도 파이썬 쪽에서는 확인 실패 → `could not verify` → 전 소스 skip.

v0.2.0은 robots.txt를 **크롤러와 동일한 httpx client·동일한 User-Agent**로 가져와
그 본문만 파싱한다. 판정은 세 상태로 명확히 나눈다.

| robots.txt 응답 | 판정 | 동작 |
|---|---|---|
| 200 | 경로 규칙 적용 후 ALLOW / DENY | 규칙대로 |
| 401 / 403 | DENY | 해당 소스 skip |
| 404 / 410 | ALLOW | robots.txt 없음 = 제한 없음 |
| 5xx | UNKNOWN | 이번 회차만 안전하게 skip |
| 네트워크 오류 | UNKNOWN | 이번 회차만 안전하게 skip |

`UNKNOWN`은 영구 DENY로 취급하지 않는다. 다음 실행에서 다시 확인한다.

또한 robots.txt 파서를 직접 구현했다. `urllib.robotparser`는 규칙을 **먼저 나온
순서대로** 매칭하는데, 씽굿 robots.txt처럼 `Allow: /`를 맨 위에 두고 아래에
`Disallow`를 나열하면 `/login*` 같은 금지 경로까지 허용으로 판정한다. 여기서는
RFC 9309대로 **가장 구체적인(긴) 규칙이 이기고, 길이가 같으면 Allow가 이긴다.**

현재 두 사이트 정책상 공모전 경로는 모두 허용이다.

- 씽굿: `User-agent: *` / `Allow: /` — 금지 대상은 `/login*`, `/logout*`,
  `/*/auth/`, `/ebook/`, `/upload/files/`, `/ufiles/`, 첨부파일 확장자,
  `/thinkgood/user/contest/thinkgood-talk*`, `/test|temp|dev/`
- 링커리어: `User-agent: *` / `Allow: /` — 금지 대상은 `/stem/learn/*` 계열

`--ignore-robots`는 기본값이 아니며, 쓰지 않는 것을 권장한다.

### 사이트 정책 원칙

- robots.txt 준수, 이용약관 고려
- 요청 간 delay 기본 2초 + robots.txt의 `Crawl-delay` 반영
- 지수 백오프 재시도(최대 3회), 병렬 요청 없음
- incremental crawl — 신규 공고만 상세 조회
- 공식 API·뉴스레터 등 공식 수단이 있으면 우선 검토

---

## 평가 (Phase 1: 규칙 기반)

100점 배점은 확정안을 그대로 따른다.

| 평가 기준 | 배점 |
|---|---:|
| 상금·수상가치 | 20 |
| 현재 제작역량 적합성 | 20 |
| 남은 기간 대비 제작 가능성 | 15 |
| 예상 경쟁강도 대비 수상 가능성 | 15 |
| 아이디어 차별화 여지 | 10 |
| AI 활용 / workflow 재활용성 | 5 |
| 혼자 제작 가능 여부 | 5 |
| 포트폴리오 가치 | 5 |
| 주최기관·공모전 신뢰도 | 5 |
| **합계** | **100** |

등급: `S` 85점 이상 · `A` 75점 이상 · `B` 60점 이상 · 그 외 `SKIP`.

키워드·배점·임계값은 설정 화면 또는 선택 파일인 `config/profile.json`에서 조정한다.
파일이 없으면 동봉된 기본 프로필을 사용하고, 설정을 저장하면 개인 설정 파일을 만든다.

```json
{
  "strong_keywords": ["AI 영상", "생성형 AI", "광고기획", "브랜드 전략"],
  "preferred_keywords": ["AI", "영상", "숏폼", "광고", "마케팅", "디자인"],
  "negative_keywords": ["문학", "독후감", "건축설계", "논문", "해커톤"],
  "tier_thresholds": { "S": 85, "A": 75, "B": 60 }
}
```

## 평가 (Phase 2: AI Evaluator)

규칙 점수는 **1차 필터**다. 최종 추천은 AI 평가기가 맡도록 자리를 비워 두었다.

```
Crawler → Normalizer → DB → 신규만 → Hard Filter → AI Evaluator → S/A/B/SKIP → Daily Digest
```

`src/contest_scout/evaluators/ai.py`에 프롬프트 빌더와 응답 파서가 이미 있다.
LLM 호출 함수만 주입하면 된다.

```python
from contest_scout.evaluators.ai import AIEvaluator

evaluator = AIEvaluator(profile, complete=my_llm_call)   # (system, user) -> JSON 문자열
```

CLI·DB·리포트는 `Evaluator` 프로토콜(`evaluate(contest) -> Evaluation`)만 알기
때문에 다른 코드는 손대지 않아도 된다.

---

## 새 소스 추가

```python
# src/contest_scout/sources/wevity.py
from contest_scout.sources.base import BaseSource

class WevitySource(BaseSource):
    name = "wevity"
    entry_url = "https://www.wevity.com/?c=find&s=1&gub=1"
    needs_detail_request = True

    def discover(self, page: int = 1) -> list[ContestRef]: ...
    def fetch_detail(self, ref: ContestRef) -> Contest: ...
```

`src/contest_scout/sources/__init__.py`의 `SOURCES`에 등록하면 CLI `--source`
선택지와 `doctor` 진단에 자동으로 나타난다.

---

## 프로젝트 구조

```
contest-scout/
├── start.sh                    # 설치 → 빌드 → 실행 한 번에
├── Makefile
├── pyproject.toml
├── config/
│   ├── profile.json            # 로컬 개인 설정 (설정 저장 시 생성, Git 제외)
│   └── settings.json           # 로컬 수집 설정 (대시보드가 생성, Git 제외)
├── data/                       # DB·리포트 (git 제외)
├── scripts/
│   └── seed_dev_db.py          # 개발용 시드 (앱 본체에는 가짜 데이터 없음)
├── src/
│   └── contest_scout/
│       ├── cli.py              # crawl / doctor / list / mark / sources / serve
│       ├── crawl.py            # incremental crawl 오케스트레이터
│       ├── db.py               # SQLite 저장소
│       ├── schema_ext.py       # 대시보드용 테이블 (기존 스키마는 그대로)
│       ├── repository.py       # 화면이 쓰는 조회 계층
│       ├── taxonomy.py         # 소스별 분야 표기 → 공통 태그
│       ├── paths.py            # 경로 해석 (환경변수로 덮어쓰기 가능)
│       ├── http.py             # httpx + delay + retry + robots 연동
│       ├── models.py / normalize.py / report.py / robots.py / config.py
│       ├── evaluators/         # base / rules / ai(Phase 2 자리)
│       ├── sources/            # base / linkareer / thinkgood
│       ├── services/           # CLI와 API가 공유하는 층
│       │   ├── scout.py        # run_scout · ScoutRunner · sync_scores
│       │   ├── settings.py     # profile.json / settings.json 읽고 쓰기
│       │   └── scheduler.py    # 자동 실행 스레드
│       └── api/
│           ├── app.py          # FastAPI + 정적 파일 서빙
│           ├── deps.py / schemas.py
│           └── routers/
├── web/                        # React + TypeScript + Tailwind
│   └── src/
│       ├── lib/                # api · types · format · queries
│       ├── components/         # ui · layout · contest · charts · scout
│       └── pages/              # 화면 10개
└── tests/
```

`src` layout이라 설치 없이 `src/`가 import 경로에 섞이는 일이 없다.

---

## 데이터베이스

`data/contest_scout.sqlite3`

기존 3개 테이블은 손대지 않았고, 대시보드가 필요로 하는 것만 덧붙였다.
예전 DB 파일을 그대로 열어도 마이그레이션이 자동으로 돈다.

| 테이블 | 내용 |
| --- | --- |
| `contests` | 정규화된 공모전 + 상태 + `canonical_key`(중복 통합) + `payload_json` |
| `crawl_runs` | 회차별 실행 요약 (+ `status` / `trigger` / `error_json`) |
| `recommendations` | 회차별 평가 이력 |
| `contest_scores` | 공모전별 **현재** 점수 (목록 정렬·필터가 읽는다) |
| `contest_tags` | 정규화된 분야 태그 |
| `projects` | 참가 중 프로젝트 (Contest Builder 인계용) |
| `status_events` | 상태 전환 로그 — Analytics의 선택 패턴은 여기서 계산한다 |

```bash
sqlite3 data/contest_scout.sqlite3 \
  "SELECT tier, count(*) FROM contest_scores GROUP BY tier;"
```

경로를 바꾸려면 환경변수를 쓴다.

```bash
CONTEST_SCOUT_DB=data/dev.sqlite3 bash ./start.sh
```

---

## 테스트

```bash
make test          # 또는 .venv/bin/python -m pytest
```

| 파일 | 검증 대상 |
| --- | --- |
| `test_robots.py` | ALLOW / DENY / UNKNOWN 판정 |
| `test_sources.py` | 씽굿·링커리어 파서 (fixture 기반) |
| `test_db_and_scoring.py` | 증분 수집·중복 통합·상태·규칙 평가 |
| `test_crawl_integration.py` | 오케스트레이터 |
| `test_end_to_end_replay.py` | 로컬 HTTP 서버로 robots→목록→상세→DB→리포트 전 구간 |
| `test_cli.py` | CLI |
| `test_repository.py` | 필터·정렬·페이지·중복 접기·대시보드 집계·프로젝트 |
| `test_services.py` | 분야 태깅·점수 동기화·설정 저장 |
| `test_api.py` | HTTP 엔드포인트 (네트워크 없이) |

`test_end_to_end_replay.py`는 2회차 실행에서 상세 요청이 0건인지,
robots.txt를 origin당 한 번만 가져오는지까지 확인한다.

프론트엔드 타입 검사:

```bash
make typecheck
```

---

## 매일 자동 실행 (선택)

설정 화면의 **자동 Scout** 은 백엔드 프로세스가 떠 있는 동안에만 동작한다.
맥을 껐다 켜도 알아서 돌게 하려면 `launchd` 에 CLI를 걸어 둔다. 대시보드와 같은
DB를 쓰므로, 아침에 화면을 열면 밤사이 수집분이 이미 들어와 있다.

macOS `launchd` 예시 — 매일 09:00:

```bash
mkdir -p ~/Library/LaunchAgents
cat > ~/Library/LaunchAgents/com.contestscout.daily.plist <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.contestscout.daily</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string><string>-lc</string>
    <string>cd ~/Desktop/contest-scout && ./.venv/bin/contest-scout crawl --source all --pages 1</string>
  </array>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>9</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardOutPath</key><string>/tmp/contest-scout.log</string>
  <key>StandardErrorPath</key><string>/tmp/contest-scout.err</string>
</dict></plist>
PLIST
launchctl load ~/Library/LaunchAgents/com.contestscout.daily.plist
```

---

## 로드맵

- [x] Phase 1 — incremental crawler + 규칙 평가 + 일일 리포트
- [x] Phase 1.5 — FastAPI + React 대시보드 (수집·평가·상태 관리 전부 화면에서)
- [ ] Phase 2 — AI Evaluator (경쟁강도·수상 가능성·아이디어 잠재력 정성 평가)
- [ ] Phase 3 — 씽굿 뉴스레터 이메일 ingestion (보조 수집원)
- [ ] Phase 4 — Telegram / Discord / Gmail 일일 다이제스트 발송
- [ ] Phase 5 — Contest Builder 연동 (`ENTERING` 공모전 인계)

미구현 기능은 화면에서 그럴듯하게 그리지 않는다. `/api/settings` 의
`capabilities` 플래그가 꺼져 있으면 UI는 "분석 준비 중" 이라고 적는다.
