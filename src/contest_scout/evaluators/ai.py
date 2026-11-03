"""AI 평가기 자리(Phase 2).

지금은 **구조만** 잡아 둔다. 규칙 평가기가 hard filter를 통과시킨 공모전만
LLM에 넘겨 100점 평가 + 추천 이유 + 리스크 + 아이디어 씨앗을 받는 것이 목표다.

    Crawler → Normalizer → DB → 신규만 → Hard Filter → AIEvaluator → S/A/B/SKIP

붙이는 방법:

1. :func:`build_prompt` 로 만든 프롬프트를 원하는 LLM API에 보낸다.
2. 응답 JSON을 :func:`parse_response` 로 :class:`Evaluation` 에 매핑한다.
3. ``cli.py`` 의 evaluator 선택 지점에서 ``AIEvaluator`` 를 쓰도록 바꾼다.

CLI/DB/리포트는 :class:`~contest_scout.evaluators.base.Evaluator` 프로토콜만
알기 때문에 다른 코드는 수정할 필요가 없다.
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable

from contest_scout.config import Profile
from contest_scout.evaluators.base import PART_LABELS, Evaluation
from contest_scout.models import Contest

SYSTEM_PROMPT = """\
당신은 개인 공모전 스카우트다. 주어진 공모전이 이 사용자에게 실제로 참가할 가치가
있는지 100점 기준으로 평가한다. 배점을 반드시 지키고, 근거 없이 후하게 주지 않는다.
결과는 JSON 하나로만 답한다.
"""

RESPONSE_SCHEMA = {
    "parts": {key: "0~배점 사이 정수" for key in PART_LABELS},
    "reasons": ["추천 이유 문자열"],
    "risks": ["리스크 문자열"],
    "estimated_workdays": "예: 5~8일",
    "idea_seeds": ["초기 아이디어 방향 2~3개"],
}


def build_prompt(contest: Contest, profile: Profile) -> str:
    """LLM에 넘길 사용자 메시지."""
    weights = "\n".join(
        f"- {PART_LABELS[key]}: {profile.weights[key]}점" for key in profile.weights
    )
    payload = {
        "title": contest.title,
        "organizer": contest.organizer,
        "organizer_type": contest.organizer_type,
        "categories": contest.categories,
        "eligibility": contest.eligibility,
        "deadline": contest.deadline.isoformat() if contest.deadline else None,
        "days_left": contest.days_left,
        "prize_text": contest.prize_text,
        "top_prize_krw": contest.top_prize_krw,
        "benefits": contest.benefits,
        "url": contest.url,
        "detail_text": (contest.detail_text or "")[:6000],
    }
    return (
        f"[배점]\n{weights}\n\n"
        f"[사용자 강점]\nAI 이미지·AI 영상·기획안·PPT·광고 캠페인·브랜드 전략을 "
        f"단독으로 제작한다. 문학/사진전/건축설계/논문/순수 개발 해커톤은 제외한다.\n\n"
        f"[공모전]\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
        f"[응답 형식]\n{json.dumps(RESPONSE_SCHEMA, ensure_ascii=False, indent=2)}"
    )


def parse_response(contest: Contest, profile: Profile, raw: dict[str, Any]) -> Evaluation:
    """LLM JSON 응답 → :class:`Evaluation`."""
    parts: dict[str, int] = {}
    for key, weight in profile.weights.items():
        try:
            value = int((raw.get("parts") or {}).get(key, 0))
        except (TypeError, ValueError):
            value = 0
        parts[key] = max(0, min(weight, value))
    total = sum(parts.values())
    return Evaluation(
        contest_key=contest.key,
        evaluator="ai",
        total=total,
        tier=profile.tier_for(total),
        parts=parts,
        reasons=[str(x) for x in (raw.get("reasons") or [])][:6],
        risks=[str(x) for x in (raw.get("risks") or [])][:6],
        estimated_workdays=raw.get("estimated_workdays"),
        idea_seeds=[str(x) for x in (raw.get("idea_seeds") or [])][:3],
    )


class AIEvaluatorNotConfigured(RuntimeError):
    pass


class AIEvaluator:
    """LLM 호출 함수만 주입하면 바로 동작하는 얇은 래퍼."""

    name = "ai"

    def __init__(
        self,
        profile: Profile,
        complete: Callable[[str, str], str] | None = None,
    ) -> None:
        self.profile = profile
        self._complete = complete

    def available(self) -> bool:
        return self._complete is not None or bool(os.environ.get("CONTEST_SCOUT_LLM_API_KEY"))

    def evaluate(self, contest: Contest) -> Evaluation:
        if self._complete is None:
            raise AIEvaluatorNotConfigured(
                "AI 평가기는 아직 LLM 호출 함수가 연결되지 않았습니다. "
                "AIEvaluator(profile, complete=...) 형태로 주입하세요."
            )
        raw_text = self._complete(SYSTEM_PROMPT, build_prompt(contest, self.profile))
        return parse_response(contest, self.profile, json.loads(raw_text))
