"""규칙 기반 평가기 (Phase 1).

배점은 확정된 100점 기준을 그대로 따른다. 이 평가기는 **1차 필터**이며, Phase 2의
AI 평가기가 최종 판단을 맡는다.

매칭 원칙:

* 분야 판정(긍정/부정 키워드)은 **제목·분야·키워드**에서만 한다. 본문까지 뒤지면
  "청소년 불법도박 예방" 같은 주제어 때문에 멀쩡한 영상 공모전이 '청소년 전용'으로
  오판된다.
* 참가자격은 키워드가 아니라 **구조적으로** 본다. 씽굿은 `enter_qualified_nm` 에
  ``"어린이, 초등학생, …, 일반인, 제한 없음"`` 처럼 전 연령을 나열하므로,
  '초등학생'이 들어 있다는 이유만으로 감점하면 안 된다.
* 팀 구성 강제처럼 본문에만 적히는 조건은 본문까지 본다.
"""

from __future__ import annotations

from datetime import date

from contest_scout.config import Profile
from contest_scout.evaluators.base import Evaluation
from contest_scout.models import Contest


class RuleEvaluator:
    name = "rules"

    def __init__(self, profile: Profile, today: date | None = None) -> None:
        self.profile = profile
        self.today = today or date.today()

    # ------------------------------------------------------------------ #
    def evaluate(self, contest: Contest) -> Evaluation:
        p = self.profile
        topic = contest.topic_haystack()
        full = contest.full_haystack()

        strong_hits = [k for k in p.strong_keywords if k.lower() in topic]
        preferred_hits = [k for k in p.preferred_keywords if k.lower() in topic]
        negative_hits = [k for k in p.negative_keywords if k.lower() in topic]
        solo_blockers = [k for k in p.solo_blocker_keywords if k.lower() in full]

        openness, eligibility_note = self._eligibility(contest)

        parts: dict[str, int] = {}
        reasons: list[str] = []
        risks: list[str] = []

        # --- 상금·수상가치 20 ------------------------------------------ #
        prize = contest.best_prize_krw or 0
        if prize >= p.strong_prize_krw:
            award = 19
            reasons.append(f"상금 규모 상위권({prize:,}원)")
        elif prize >= p.good_prize_krw:
            award = 15
            reasons.append(f"상금 {prize:,}원으로 투입 대비 회수 양호")
        elif prize >= 1_000_000:
            award = 10
        elif prize > 0:
            award = 6
        else:
            award = 4
            risks.append("상금 정보를 확인하지 못했습니다")
        if self._trusted_organizer(contest):
            award += 1
        parts["award_value"] = _clamp(award, 0, 20)

        # --- 현재 제작역량 적합성 20 ------------------------------------ #
        skill = 4 + len(strong_hits) * 5 + len(preferred_hits) * 2
        if negative_hits:
            skill -= 7 * len(negative_hits)
            risks.append("관심 밖 분야 신호: " + ", ".join(negative_hits[:3]))
        if openness == "youth_only":
            skill -= 10
        parts["skill_fit"] = _clamp(skill, 0, 20)
        if strong_hits:
            reasons.append("핵심 관심 분야와 직결: " + ", ".join(strong_hits[:3]))
        elif preferred_hits:
            reasons.append("관심 분야 키워드 일치: " + ", ".join(preferred_hits[:4]))

        # --- 남은 기간 대비 제작 가능성 15 ------------------------------ #
        days = contest.days_left
        if days is None:
            parts["feasibility"] = 8
            risks.append("마감일을 확인하지 못했습니다")
        elif days < 0:
            parts["feasibility"] = 0
            risks.append("이미 마감된 공모전입니다")
        elif days < p.min_days_left:
            parts["feasibility"] = 2
            risks.append(f"마감까지 {days}일 — 사실상 착수 불가")
        elif days < 7:
            parts["feasibility"] = 8
            risks.append(f"마감까지 {days}일로 일정이 촉박합니다")
        elif days < 14:
            parts["feasibility"] = 12
        elif days <= 60:
            parts["feasibility"] = 15
        else:
            parts["feasibility"] = 13  # 너무 멀면 지금 붙잡을 이유가 약하다

        # --- 예상 경쟁강도 대비 수상 가능성 15 -------------------------- #
        win = 8 + len(strong_hits) * 2 - len(negative_hits) * 3
        if prize >= 30_000_000:
            win -= 3
            risks.append("상금 규모가 커 경쟁 강도가 높을 가능성")
        if openness == "region_restricted":
            win += 1  # 모집단이 작아 경쟁은 덜하다
        if openness == "youth_only":
            win -= 8
        parts["win_probability"] = _clamp(win, 0, 15)

        # --- 아이디어 차별화 여지 10 ------------------------------------ #
        idea = 5 + len(strong_hits) + len(preferred_hits) // 3
        if any(k in topic for k in ("자유주제", "자유 주제", "아이디어")):
            idea += 2
        if negative_hits:
            idea -= 3
        parts["idea_headroom"] = _clamp(idea, 0, 10)

        # --- AI 활용 / workflow 재활용성 5 ------------------------------ #
        reuse_signals = ("ai", "영상", "숏폼", "포스터", "디자인", "광고", "콘텐츠", "ucc")
        matched_reuse = [k for k in reuse_signals if k in topic]
        parts["workflow_reuse"] = _clamp(len(matched_reuse), 0, 5)
        if len(matched_reuse) >= 3:
            reasons.append("기존 AI 영상·디자인 workflow를 그대로 재활용 가능")

        # --- 혼자 제작 가능 여부 5 -------------------------------------- #
        if solo_blockers:
            parts["solo_friendly"] = 1
            risks.append("팀 구성 요구: " + ", ".join(solo_blockers[:2]))
        else:
            parts["solo_friendly"] = 5
            reasons.append("단독 제작으로 완주 가능한 형식")

        # --- 포트폴리오 가치 5 ------------------------------------------ #
        portfolio = 1 + len(strong_hits)
        if prize >= p.strong_prize_krw:
            portfolio += 1
        if self._trusted_organizer(contest):
            portfolio += 1
        if negative_hits:
            portfolio -= 2
        parts["portfolio_value"] = _clamp(portfolio, 0, 5)

        # --- 주최기관·공모전 신뢰도 5 ----------------------------------- #
        trust = 2
        if self._trusted_organizer(contest):
            trust += 2
        if contest.homepage:
            trust += 1
        if not contest.organizer:
            trust -= 1
            risks.append("주최기관 정보가 비어 있습니다")
        parts["organizer_trust"] = _clamp(trust, 0, 5)

        if eligibility_note:
            (risks if openness != "open" else reasons).append(eligibility_note)

        # 배점 상한 강제 (프로필에서 가중치를 바꿔도 안전)
        parts = {k: min(v, p.weights.get(k, v)) for k, v in parts.items()}
        total = sum(parts.values())

        return Evaluation(
            contest_key=contest.key,
            evaluator=self.name,
            total=total,
            tier=p.tier_for(total),
            parts=parts,
            reasons=reasons[:5],
            risks=risks[:5],
            estimated_workdays=_estimate_workdays(parts, days),
        )

    # ------------------------------------------------------------------ #
    def _trusted_organizer(self, contest: Contest) -> bool:
        blob = f"{contest.organizer or ''} {contest.organizer_type or ''}"
        return any(k in blob for k in self.profile.trusted_organizer_keywords)

    def _eligibility(self, contest: Contest) -> tuple[str, str | None]:
        """참가자격을 open / region_restricted / youth_only / unknown 으로 분류."""
        p = self.profile
        text = contest.eligibility_text()
        if not text:
            return "unknown", None

        is_open = any(term.lower() in text for term in p.open_eligibility_terms)
        has_youth = any(term.lower() in text for term in p.youth_only_terms)
        is_region = any(term.lower() in text for term in p.region_restricted_terms)

        if is_open and not is_region:
            return "open", "참가 자격이 넓어 바로 응모 가능"
        if is_region:
            return "region_restricted", "참가 자격에 지역·소속 제한이 있어 확인 필요"
        if has_youth:
            return "youth_only", "청소년·학생 전용으로 보입니다"
        return "unknown", None


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, int(value)))


def _estimate_workdays(parts: dict[str, int], days_left: int | None) -> str:
    """제작 난이도 대략치. 정밀한 추정은 AI 평가기 몫."""
    base = 5 if parts.get("workflow_reuse", 0) >= 4 else 8
    if parts.get("solo_friendly", 0) <= 1:
        base += 3
    upper = base + 3
    if days_left is not None and days_left < upper:
        return f"{base}~{max(base, days_left)}일 (마감까지 {days_left}일)"
    return f"{base}~{upper}일"
