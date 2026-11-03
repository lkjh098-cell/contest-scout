"""날짜·금액·텍스트 정규화 유틸리티 (외부 의존성 없음)."""

from __future__ import annotations

import html
import re
from datetime import date, datetime

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t 　]+")


def strip_html(raw: str | None) -> str:
    """에디터가 만든 HTML 본문을 읽을 수 있는 평문으로."""
    if not raw:
        return ""
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|li|tr|h[1-6])>", "\n", text)
    text = _TAG.sub(" ", text)
    text = html.unescape(text)
    text = _WS.sub(" ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip()


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    s = _WS.sub(" ", html.unescape(str(value))).strip()
    return s or None


def split_list(value: str | None, seps: str = ",|") -> list[str]:
    """``"광고/마케팅, 디자인, 영상/UCC"`` → 3개 항목.

    기본 구분자에 ``/`` 는 넣지 않는다. 씽굿/링커리어의 분야명은 ``영상/UCC``,
    ``광고/마케팅`` 처럼 슬래시를 이름 안에 포함하기 때문이다.
    """
    if not value:
        return []
    pattern = "[" + re.escape(seps) + "]"
    out: list[str] = []
    for chunk in re.split(pattern, str(value)):
        item = clean_text(chunk)
        if item and item not in out:
            out.append(item)
    return out


def split_keywords(value: str | None) -> list[str]:
    if not value:
        return []
    out: list[str] = []
    for token in re.findall(r"#\s*([^\s#]+)", str(value)):
        token = token.strip()
        if token and token not in out:
            out.append(token)
    if not out:
        return split_list(value)
    return out


_DATE_PATTERNS = (
    re.compile(r"(?P<y>\d{4})[-./년]\s*(?P<m>\d{1,2})[-./월]\s*(?P<d>\d{1,2})"),
    re.compile(r"(?P<y>\d{4})(?P<m>\d{2})(?P<d>\d{2})(?!\d)"),
)


def parse_date(value: str | None) -> date | None:
    """``2026-09-30 23:59:00.0`` / ``2026.09.30`` / ``2026년 9월 30일`` 모두 허용."""
    if not value:
        return None
    text = str(value).strip()
    for pattern in _DATE_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        try:
            return date(int(m["y"]), int(m["m"]), int(m["d"]))
        except ValueError:
            return None
    return None


def parse_epoch_ms(value: object) -> datetime | None:
    """Linkareer가 쓰는 epoch milliseconds → datetime."""
    if value in (None, "", 0):
        return None
    try:
        ms = int(value)
    except (TypeError, ValueError):
        return None
    if ms <= 0:
        return None
    try:
        return datetime.fromtimestamp(ms / 1000)
    except (OverflowError, OSError, ValueError):
        return None


def date_from_epoch_ms(value: object) -> date | None:
    dt = parse_epoch_ms(value)
    return dt.date() if dt else None


def parse_date_range(value: str | None) -> tuple[date | None, date | None]:
    """``2026-08-26 ~ 2026-09-23`` 형태의 접수기간."""
    if not value:
        return None, None
    # 날짜 안의 하이픈(2026-08-26)과 구분자를 혼동하지 않도록 공백을 요구한다.
    parts = re.split(r"\s+[~〜–—]\s*|\s*[~〜–—]\s+|\s+-\s+", str(value))
    if len(parts) >= 2:
        return parse_date(parts[0]), parse_date(parts[-1])
    return parse_date(value), None


_UNITS: tuple[tuple[str, int], ...] = (
    ("억", 100_000_000),
    ("천만", 10_000_000),
    ("백만", 1_000_000),
    ("만", 10_000),
)

# 상금 표기 앞에 붙는 순위 라벨. 앞쪽일수록 '1등 상금'에 가깝다.
_RANK_LABELS = ("대상", "최우수", "금상", "우수", "1등", "1위", "은상", "동상", "장려")

#: 사람이 잘못 입력한 값(만원 단위에 100만 = 100억원)을 걸러내기 위한 상한.
MAX_SANE_PRIZE_KRW = 5_000_000_000


def parse_krw(text: str | None) -> int | None:
    """한국어 금액 표기를 원 단위 정수로. 가장 큰 금액을 돌려준다."""
    if not text:
        return None
    s = str(text).replace(",", "").replace(" ", "")
    best: int | None = None
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(억|천만|백만|만)?\s*원", s):
        amount = float(m.group(1))
        unit = m.group(2)
        multiplier = dict(_UNITS).get(unit, 1) if unit else 1
        value = int(amount * multiplier)
        if best is None or value > best:
            best = value
    if best is None:
        # '총상금 3000만' 처럼 '원'이 빠진 표기.
        m = re.search(r"(\d+(?:\.\d+)?)\s*(억|천만|백만|만)", s)
        if m:
            best = int(float(m.group(1)) * dict(_UNITS)[m.group(2)])
    if best is not None and best > MAX_SANE_PRIZE_KRW:
        return None
    return best


def parse_man_won(value: object) -> int | None:
    """만원 단위 정수(Linkareer ``tenThousandUnitOfReward``) → 원 단위."""
    if value in (None, ""):
        return None
    try:
        won = int(float(value)) * 10_000
    except (TypeError, ValueError):
        return None
    if won <= 0 or won > MAX_SANE_PRIZE_KRW:
        return None
    return won


def extract_top_prize(detail_text: str | None) -> int | None:
    """상세요강 본문에서 '대상/최우수상' 등 1등 상금을 추정한다."""
    if not detail_text:
        return None
    text = detail_text.replace(",", "")
    for label in _RANK_LABELS:
        for m in re.finditer(re.escape(label), text):
            window = text[m.end() : m.end() + 60]
            value = parse_krw(window)
            if value:
                return value
    return None


def token_set(text: str) -> set[str]:
    return {t for t in re.split(r"\s+", text) if len(t) > 1}


def similarity(a: str, b: str) -> float:
    """토큰 집합 Jaccard 유사도 (0.0 ~ 1.0)."""
    ta, tb = token_set(a), token_set(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)
