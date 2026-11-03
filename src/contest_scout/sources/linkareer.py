"""링커리어(Linkareer) 어댑터.

링커리어는 Next.js SSR이라 목록/상세 HTML 안에 구조화 데이터가 들어 있다.
CSS selector 하나에 의존하지 않도록 다음 순서로 시도한다.

목록:
    1. ``<script type="application/ld+json">`` 의 ``ItemList`` (JSON-LD)
    2. ``__NEXT_DATA__.props.pageProps.activityItems``
    3. ``a[href^="/activity/"]`` 정규식 fallback

상세:
    1. ``__NEXT_DATA__.props.pageProps.__APOLLO_STATE__`` 의 ``Activity:<id>``
       (제목·주최·마감일·상금·분야·대상까지 전부 정형 필드)
    2. HTML ``<h1>`` / meta 태그 fallback

robots.txt는 ``/list/`` 와 ``/activity/`` 를 금지하지 않는다(금지 대상은
``/stem/learn/*`` 계열).
"""

from __future__ import annotations

import html
import json
import logging
import re
from typing import Any

from contest_scout.models import Contest, ContestRef, ParseWarning
from contest_scout.normalize import (
    clean_text,
    date_from_epoch_ms,
    extract_top_prize,
    parse_epoch_ms,
    parse_man_won,
    strip_html,
)
from contest_scout.sources.base import BaseSource

log = logging.getLogger(__name__)

BASE = "https://linkareer.com"
LIST_URL = f"{BASE}/list/contest"
ACTIVITY_URL = f"{BASE}/activity/{{id}}"

_NEXT_DATA = re.compile(
    r'<script id="__NEXT_DATA__"[^>]*>(?P<json>.*?)</script>', re.DOTALL
)
_LD_JSON = re.compile(
    r'<script type="application/ld\+json"[^>]*>(?P<json>.*?)</script>', re.DOTALL
)
_ACTIVITY_PATH = re.compile(r"/activity/(\d+)")


def _load_next_data(html_text: str) -> dict[str, Any] | None:
    match = _NEXT_DATA.search(html_text)
    if not match:
        return None
    try:
        return json.loads(match.group("json"))
    except json.JSONDecodeError:
        return None


def _iter_ld_json(html_text: str) -> list[Any]:
    out: list[Any] = []
    for match in _LD_JSON.finditer(html_text):
        try:
            out.append(json.loads(match.group("json")))
        except json.JSONDecodeError:
            continue
    return out


class LinkareerSource(BaseSource):
    name = "linkareer"
    entry_url = LIST_URL
    needs_detail_request = True

    def discover(self, page: int = 1) -> list[ContestRef]:
        url = LIST_URL if page <= 1 else f"{LIST_URL}?page={page}"
        html_text = self.http.get_text(url)
        refs = self._parse_list(html_text)
        if not refs:
            log.warning("linkareer 목록에서 공모전을 찾지 못했습니다: %s", url)
        return refs

    # --- 목록 파싱 (테스트에서 직접 호출) ------------------------------- #
    def _parse_list(self, html_text: str) -> list[ContestRef]:
        seen: dict[str, ContestRef] = {}

        def add(activity_url: str, title: str) -> None:
            m = _ACTIVITY_PATH.search(activity_url)
            if not m:
                return
            activity_id = m.group(1)
            if activity_id in seen:
                return
            seen[activity_id] = ContestRef(
                source=self.name,
                source_id=activity_id,
                url=ACTIVITY_URL.format(id=activity_id),
                title=html.unescape(title or "").strip(),
            )

        # 1) JSON-LD ItemList
        for block in _iter_ld_json(html_text):
            if not isinstance(block, dict) or block.get("@type") != "ItemList":
                continue
            for item in block.get("itemListElement") or []:
                if isinstance(item, dict):
                    add(str(item.get("url") or ""), str(item.get("name") or ""))

        # 2) __NEXT_DATA__ activityItems
        if not seen:
            data = _load_next_data(html_text) or {}
            items = (data.get("props", {}).get("pageProps", {}) or {}).get("activityItems")
            for item in items or []:
                if isinstance(item, dict):
                    add(str(item.get("url") or ""), str(item.get("name") or ""))

        # 3) 마지막 fallback: 링크만이라도
        if not seen:
            for activity_id in dict.fromkeys(_ACTIVITY_PATH.findall(html_text)):
                add(f"/activity/{activity_id}", "")

        return list(seen.values())

    # --- 상세 파싱 ------------------------------------------------------ #
    def fetch_detail(self, ref: ContestRef) -> Contest:
        html_text = self.http.get_text(ref.url)
        return self.parse_detail(html_text, ref.url, fallback_title=ref.title)

    def parse_detail(
        self, html_text: str, url: str, fallback_title: str = ""
    ) -> Contest:
        warnings: list[ParseWarning] = []

        def warn(field: str, reason: str) -> None:
            warnings.append(ParseWarning(self.name, url, field, reason))

        m = _ACTIVITY_PATH.search(url)
        source_id = m.group(1) if m else url

        state = self._apollo_state(html_text)
        activity = state.get(f"Activity:{source_id}") if state else None
        if activity is None and state:
            activity = next(
                (v for k, v in state.items() if k.startswith("Activity:")), None
            )

        if activity is None:
            warn("__APOLLO_STATE__", "Activity 노드를 찾지 못해 HTML fallback 사용")
            return self._fallback_contest(html_text, url, source_id, fallback_title, warnings)

        def refs(field: str) -> list[str]:
            names: list[str] = []
            for item in activity.get(field) or []:
                node = state.get(item.get("__ref")) if isinstance(item, dict) else None
                name = clean_text((node or {}).get("name"))
                if name and name not in names:
                    names.append(name)
            return names

        title = clean_text(activity.get("title")) or fallback_title
        if not title:
            warn("title", "Activity.title 비어 있음")
            title = f"(제목 없음) {source_id}"

        organizer = clean_text(activity.get("organizationName"))
        if not organizer:
            warn("organizer", "organizationName 비어 있음")

        deadline = date_from_epoch_ms(activity.get("recruitCloseAt"))
        if deadline is None:
            warn("deadline", "recruitCloseAt 없음")

        detail_ref = activity.get("detailText")
        detail_node = (
            state.get(detail_ref.get("__ref")) if isinstance(detail_ref, dict) else None
        )
        detail_text = strip_html((detail_node or {}).get("text"))

        total_prize = parse_man_won(activity.get("tenThousandUnitOfReward"))
        top_prize = extract_top_prize(detail_text) or total_prize
        if total_prize is None and activity.get("tenThousandUnitOfReward"):
            warn(
                "total_prize_krw",
                f"시상 규모 값이 비정상: {activity.get('tenThousandUnitOfReward')!r}",
            )

        prize_text = f"{total_prize:,}원" if total_prize else None

        return Contest(
            source=self.name,
            source_id=source_id,
            url=url,
            title=title,
            organizer=organizer,
            organizer_type=clean_text(activity.get("organizationType")),
            categories=refs("categories") or refs("rootCategories"),
            eligibility=refs("targets"),
            start_date=date_from_epoch_ms(activity.get("recruitStartAt")),
            deadline=deadline,
            posted_at=parse_epoch_ms(activity.get("createdAt")),
            prize_text=prize_text,
            top_prize_krw=top_prize,
            total_prize_krw=total_prize,
            benefits=refs("benefits"),
            homepage=clean_text(activity.get("homepageURL"))
            or clean_text(activity.get("applyDetail")),
            keywords=refs("interests"),
            detail_text=detail_text or None,
            warnings=warnings,
        )

    @staticmethod
    def _apollo_state(html_text: str) -> dict[str, Any]:
        data = _load_next_data(html_text)
        if not data:
            return {}
        page_props = data.get("props", {}).get("pageProps", {}) or {}
        state = page_props.get("__APOLLO_STATE__") or page_props.get("apolloState")
        return state if isinstance(state, dict) else {}

    def _fallback_contest(
        self,
        html_text: str,
        url: str,
        source_id: str,
        fallback_title: str,
        warnings: list[ParseWarning],
    ) -> Contest:
        title = fallback_title
        if not title:
            m = re.search(r"<h1[^>]*>(.*?)</h1>", html_text, re.DOTALL)
            if m:
                title = strip_html(m.group(1))
        if not title:
            m = re.search(r'<meta property="og:title" content="([^"]+)"', html_text)
            if m:
                title = html.unescape(m.group(1))
        if not title:
            warnings.append(
                ParseWarning(self.name, url, "title", "h1/og:title 모두 실패")
            )
            title = f"(제목 없음) {source_id}"

        return Contest(
            source=self.name,
            source_id=source_id,
            url=url,
            title=title,
            warnings=warnings,
        )
