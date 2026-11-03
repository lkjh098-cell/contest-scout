"""일일 Markdown 리포트.

전부 나열하지 않는다. 상위 후보(S/A/B)를 카드 형태로 보여주고, SKIP은 접힌
목록으로만 남긴다.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Iterable, Sequence

from contest_scout.crawl import CrawlResult
from contest_scout.evaluators.base import PART_LABELS, Evaluation
from contest_scout.models import Contest

TIER_ORDER = {"S": 0, "A": 1, "B": 2, "SKIP": 3}
TIER_NOTE = {
    "S": "일정 조정해서라도 반드시 검토",
    "A": "적극 추천",
    "B": "시간 여유가 있다면 검토",
    "SKIP": "투입시간 대비 가치 낮음",
}


def _deadline_label(contest: Contest) -> str:
    if contest.deadline is None:
        return "마감일 미확인"
    days = contest.days_left
    if days is None:
        return contest.deadline.isoformat()
    if days < 0:
        return f"{contest.deadline.isoformat()} (마감)"
    return f"{contest.deadline.isoformat()} (D-{days})"


def _prize_label(contest: Contest) -> str:
    if contest.best_prize_krw:
        return f"{contest.best_prize_krw:,}원"
    return contest.prize_text or "미확인"


def render_markdown(
    result: CrawlResult,
    path: str | Path,
    *,
    today: date | None = None,
    max_cards: int = 8,
) -> Path:
    today = today or date.today()
    pairs = _sorted_pairs(result.new_contests, result.evaluations)

    counts = {tier: 0 for tier in TIER_ORDER}
    for _, evaluation in pairs:
        counts[evaluation.tier] = counts.get(evaluation.tier, 0) + 1

    lines: list[str] = [
        f"# Contest Scout — {today.isoformat()}",
        "",
        f"오늘 신규 공모전 **{len(pairs)}개** 발견",
        "",
        f"- S급 {counts.get('S', 0)}개 · A급 {counts.get('A', 0)}개 "
        f"· B급 {counts.get('B', 0)}개 · SKIP {counts.get('SKIP', 0)}개",
        "",
    ]

    lines += _run_summary_block(result)

    top = [pair for pair in pairs if pair[1].tier != "SKIP"][:max_cards]
    if top:
        lines += ["## 🔥 오늘의 추천", ""]
        for index, (contest, evaluation) in enumerate(top, start=1):
            lines += _card(index, contest, evaluation)
    else:
        lines += ["## 🔥 오늘의 추천", "", "추천 등급(S/A/B)에 오른 신규 공모전이 없습니다.", ""]

    skipped = [pair for pair in pairs if pair[1].tier == "SKIP"]
    if skipped:
        lines += ["<details>", f"<summary>SKIP {len(skipped)}건</summary>", ""]
        lines += _table(skipped)
        lines += ["", "</details>", ""]

    if result.warnings:
        lines += ["<details>", f"<summary>파싱 경고 {len(result.warnings)}건</summary>", "", "```"]
        lines += [str(w) for w in result.warnings[:50]]
        lines += ["```", "", "</details>", ""]

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return output


def _sorted_pairs(
    contests: Sequence[Contest], evaluations: dict[str, Evaluation]
) -> list[tuple[Contest, Evaluation]]:
    pairs = [(c, evaluations[c.key]) for c in contests if c.key in evaluations]
    pairs.sort(key=lambda p: (TIER_ORDER.get(p[1].tier, 9), -p[1].total))
    return pairs


def _run_summary_block(result: CrawlResult) -> list[str]:
    lines = ["## 수집 요약", "", "|소스|robots|발견|신규|기존|상세요청|HTTP|오류|", "|---|---|---:|---:|---:|---:|---:|---:|"]
    for s in result.stats:
        if s.skipped_reason:
            lines.append(f"|{s.source}|{s.robots}|-|-|-|-|{s.requests}|SKIP|")
            continue
        lines.append(
            f"|{s.source}|{s.robots}|{s.discovered}|{s.new}|{s.existing}|"
            f"{s.details_fetched}|{s.requests}|{s.errors}|"
        )
    lines.append("")
    return lines


def _card(index: int, contest: Contest, evaluation: Evaluation) -> list[str]:
    lines = [
        f"### {index}. [{contest.title}]({contest.url})",
        "",
        f"**종합점수 {evaluation.total}/100 · 등급 {evaluation.tier}** "
        f"— {TIER_NOTE.get(evaluation.tier, '')}",
        "",
        "|항목|점수|",
        "|---|---:|",
    ]
    for key, value in evaluation.parts.items():
        lines.append(f"|{PART_LABELS.get(key, key)}|{value}|")
    lines += [
        "",
        f"- 주최: {contest.organizer or '미확인'}"
        + (f" ({contest.organizer_type})" if contest.organizer_type else ""),
        f"- 상금: {_prize_label(contest)}",
        f"- 마감: {_deadline_label(contest)}",
        f"- 분야: {', '.join(contest.categories) or '미확인'}",
        f"- 대상: {', '.join(contest.eligibility) or '미확인'}",
    ]
    if contest.homepage:
        lines.append(f"- 공식 홈페이지: {contest.homepage}")
    lines.append("")

    if evaluation.reasons:
        lines += ["**추천 이유**", ""]
        lines += [f"- {r}" for r in evaluation.reasons]
        lines.append("")
    if evaluation.risks:
        lines += ["**리스크**", ""]
        lines += [f"- {r}" for r in evaluation.risks]
        lines.append("")
    if evaluation.estimated_workdays:
        lines += [f"**예상 작업기간** {evaluation.estimated_workdays}", ""]
    if evaluation.idea_seeds:
        lines += ["**초기 아이디어 방향**", ""]
        lines += [f"{i}. {seed}" for i, seed in enumerate(evaluation.idea_seeds, 1)]
        lines.append("")

    lines += [f"결론: {evaluation.stars} ({contest.key})", "", "---", ""]
    return lines


def _table(pairs: Iterable[tuple[Contest, Evaluation]]) -> list[str]:
    lines = ["|등급|점수|공모전|주최|마감|상금|소스|", "|---|---:|---|---|---|---:|---|"]
    for contest, evaluation in pairs:
        lines.append(
            f"|{evaluation.tier}|{evaluation.total}|[{contest.title}]({contest.url})|"
            f"{contest.organizer or '-'}|{_deadline_label(contest)}|"
            f"{_prize_label(contest)}|{contest.source}|"
        )
    return lines
