"""평가기 공통 인터페이스.

Phase 1은 규칙 기반(:class:`~contest_scout.evaluators.rules.RuleEvaluator`)만
쓴다. Phase 2에서 LLM 평가기를 붙일 때는 같은 :class:`Evaluator` 프로토콜을
구현하기만 하면 CLI/DB/리포트를 손대지 않아도 된다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from contest_scout.models import Contest

#: 100점 배점 항목의 표시 이름.
PART_LABELS: dict[str, str] = {
    "award_value": "상금·수상가치",
    "skill_fit": "현재 제작역량 적합성",
    "feasibility": "남은 기간 대비 제작 가능성",
    "win_probability": "예상 경쟁강도 대비 수상 가능성",
    "idea_headroom": "아이디어 차별화 여지",
    "workflow_reuse": "AI 활용 / workflow 재활용성",
    "solo_friendly": "혼자 제작 가능 여부",
    "portfolio_value": "포트폴리오 가치",
    "organizer_trust": "주최기관·공모전 신뢰도",
}


@dataclass(slots=True)
class Evaluation:
    """공모전 1건의 평가 결과."""

    contest_key: str
    evaluator: str
    total: int
    tier: str
    parts: dict[str, int]
    reasons: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    estimated_workdays: str | None = None
    idea_seeds: list[str] = field(default_factory=list)

    @property
    def stars(self) -> str:
        return {"S": "★★★★★", "A": "★★★★☆", "B": "★★★☆☆"}.get(self.tier, "★★☆☆☆")


@runtime_checkable
class Evaluator(Protocol):
    name: str

    def evaluate(self, contest: Contest) -> Evaluation: ...
