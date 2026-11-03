"""씽굿(Thinkgood) 어댑터.

씽굿 목록 페이지의 ``<tbody id="dataList">`` 는 **서버 HTML에서는 비어 있고**
JS가 ``POST /thinkgood/user/contest/subList.do`` 로 채운다. v0.1.x가 목록에서
공모전 링크를 하나도 못 찾은 근본 원인이 이것이다.

그 JSON 엔드포인트는 목록 + 상세(``competition_syllabus``)를 한 번에 돌려주므로
**하루 요청 1회**로 신규 공모전 상세까지 전부 얻을 수 있다. robots.txt는 해당
경로를 금지하지 않는다(금지 대상은 ``/login*``, ``/thinkgood-talk*``, 첨부파일
확장자 등).
"""

from __future__ import annotations

import logging
from typing import Any

from contest_scout.models import Contest, ContestRef, ParseWarning
from contest_scout.normalize import (
    clean_text,
    parse_date,
    parse_date_range,
    parse_krw,
    split_keywords,
    split_list,
    strip_html,
    extract_top_prize,
)
from contest_scout.sources.base import BaseSource

log = logging.getLogger(__name__)

BASE = "https://www.thinkcontest.com"
LIST_API = f"{BASE}/thinkgood/user/contest/subList.do"
VIEW_URL = f"{BASE}/thinkgood/user/contest/view.do?contest_pk={{pk}}"
ENTRY_URL = f"{BASE}/thinkgood/user/contest/index.do"


class ThinkgoodSource(BaseSource):
    name = "thinkgood"
    entry_url = ENTRY_URL
    #: 목록 응답에 상세가 이미 들어 있다 → 상세 페이지를 다시 요청하지 않는다.
    needs_detail_request = False

    #: 한 번에 가져올 건수. 등록일 역순이므로 신규분만 확인하면 충분하다.
    records_per_page = 20

    def discover(self, page: int = 1) -> list[ContestRef]:
        payload = {
            "recordsPerPage": self.records_per_page,
            "currentPageNo": page,
            "searchStatus": "Y",
            "sidx": "putup_sdt",  # 게시 시작일
            "sord": "DESC",
            "contest_field": "",
            "host_organ": "",
            "enter_qualified": "",
            "award_size": "",
        }
        data = self.http.post_json(LIST_API, payload)

        if not isinstance(data, dict) or str(data.get("status")) != "1":
            message = (data or {}).get("msg") if isinstance(data, dict) else None
            raise RuntimeError(f"thinkgood subList.do 실패: {message or data!r}")

        rows = data.get("listJsonData") or []
        refs: list[ContestRef] = []
        for row in rows:
            pk = row.get("contest_pk")
            if pk in (None, ""):
                continue
            refs.append(
                ContestRef(
                    source=self.name,
                    source_id=str(pk),
                    url=VIEW_URL.format(pk=pk),
                    title=clean_text(row.get("program_nm")) or "",
                    payload=row,
                )
            )
        return refs

    def fetch_detail(self, ref: ContestRef) -> Contest:
        row: dict[str, Any] = ref.payload or {}
        if not row:  # 방어적 경로: payload 없이 들어온 ref
            raise RuntimeError(f"thinkgood ref에 payload가 없습니다: {ref.key}")
        return self._normalize(row, ref.url)

    # ------------------------------------------------------------------ #
    def _normalize(self, row: dict[str, Any], url: str) -> Contest:
        warnings: list[ParseWarning] = []

        def warn(field: str, reason: str) -> None:
            warnings.append(ParseWarning(self.name, url, field, reason))

        title = clean_text(row.get("program_nm"))
        if not title:
            warn("title", "program_nm 없음")
            title = f"(제목 없음) {row.get('contest_pk')}"

        organizer = clean_text(row.get("host_company")) or clean_text(
            row.get("supervises_company")
        )
        if not organizer:
            warn("organizer", "host_company/supervises_company 모두 비어 있음")

        start, deadline = parse_date_range(row.get("receive_period"))
        if start is None:
            start = parse_date(row.get("accept_dt"))
        if deadline is None:
            deadline = parse_date(row.get("finish_dt"))
        if deadline is None:
            warn("deadline", "receive_period/finish_dt에서 마감일을 찾지 못함")

        detail_text = strip_html(row.get("competition_syllabus"))
        if not detail_text:
            warn("detail_text", "competition_syllabus 비어 있음")

        prize_text = clean_text(row.get("prize_money"))
        top_prize = parse_krw(prize_text) or extract_top_prize(detail_text)
        if top_prize is None and prize_text:
            warn("top_prize_krw", f"금액 파싱 실패: {prize_text!r}")

        return Contest(
            source=self.name,
            source_id=str(row.get("contest_pk")),
            url=url,
            title=title,
            organizer=organizer,
            organizer_type=clean_text(row.get("host_organ_nm")),
            categories=split_list(row.get("contest_field_nm")),
            eligibility=split_list(row.get("enter_qualified_nm")),
            start_date=start,
            deadline=deadline,
            posted_at=None,
            prize_text=prize_text or clean_text(row.get("award_size_nm")),
            top_prize_krw=top_prize,
            total_prize_krw=parse_krw(row.get("award_size_nm")),
            benefits=split_list(row.get("award_type_nm")) + split_list(row.get("perks_nm")),
            homepage=clean_text(row.get("hompage_url")),
            keywords=split_keywords(row.get("keyword")),
            detail_text=detail_text or None,
            warnings=warnings,
        )
