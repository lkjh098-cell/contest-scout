import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/cn";
import { formatPrizeFull, VERDICT } from "@/lib/format";
import type { Contest } from "@/lib/types";
import { DeadlinePill, SourceMark, TagList } from "./Bits";
import { StatusActions } from "./StatusActions";
import { TierBadge } from "./TierBadge";

const HIGHLIGHT_PARTS: { key: string; label: string; max: number }[] = [
  { key: "skill_fit", label: "역량 적합도", max: 20 },
  { key: "award_value", label: "수상 가치", max: 20 },
  { key: "win_probability", label: "수상 가능성", max: 15 },
];

/** 오늘의 추천. 일반 목록보다 훨씬 강하게 강조하는 단 하나의 카드 형식이다. */
export function OpportunityCard({ contest, rank }: { contest: Contest; rank: number }) {
  const score = contest.score;
  const tier = score?.tier ?? "SKIP";
  const verdict = VERDICT[tier];
  const why = score?.reasons?.[0];

  return (
    <article
      className={cn(
        "group relative overflow-hidden rounded-xl border bg-surface transition-colors",
        tier === "S" ? "border-line-strong" : "border-line",
        "hover:border-line-strong",
      )}
    >
      {tier === "S" && (
        <span className="absolute inset-x-0 top-0 h-[2px] bg-[var(--tier-s-fg)]" />
      )}
      <div className="flex flex-col gap-5 p-5 lg:flex-row lg:items-stretch lg:gap-7">
        {/* 등급 · 점수 */}
        <div className="flex shrink-0 items-center gap-3 lg:w-[92px] lg:flex-col lg:items-start lg:gap-1.5">
          <TierBadge tier={tier} size="lg" />
          <div className="flex items-baseline gap-1.5 lg:mt-1 lg:flex-col lg:gap-0">
            <span className="num text-[34px] font-semibold leading-none tracking-[-0.03em] text-ink">
              {score?.total ?? "—"}
            </span>
            <span className="label-xs lg:mt-1">/ 100점</span>
          </div>
          <span className="num ml-auto text-[11px] text-subtle lg:ml-0 lg:mt-auto">
            {String(rank).padStart(2, "0")}
          </span>
        </div>

        {/* 본문 */}
        <div className="min-w-0 grow">
          <Link
            to={`/contests/${encodeURIComponent(contest.key)}`}
            className="block text-[17px] font-semibold leading-snug tracking-[-0.015em] text-ink decoration-line-strong underline-offset-4 hover:underline"
          >
            {contest.title}
          </Link>
          <div className="mt-1.5 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[13px] text-muted">
            <span>{contest.organizer ?? "주최 미확인"}</span>
            <span className="text-line-strong">·</span>
            <SourceMark source={contest.source} sources={contest.duplicate_sources} />
          </div>

          <div className="mt-3.5 flex flex-wrap items-center gap-x-5 gap-y-2">
            <div>
              <span className="label-xs block">최고 상금</span>
              <span className="num mt-0.5 block text-[15px] font-semibold text-ink">
                {formatPrizeFull(contest.best_prize_krw)}
              </span>
            </div>
            <div>
              <span className="label-xs block">접수 마감</span>
              <DeadlinePill days={contest.days_left} className="mt-0.5 -ml-1.5 text-[15px]" />
            </div>
            <div className="min-w-0">
              <span className="label-xs block">분야</span>
              <TagList tags={contest.tags} max={3} className="mt-1" />
            </div>
          </div>

          {(why || verdict) && (
            <div className="mt-4 border-l-2 border-line pl-3">
              <p className="text-[13px] font-medium text-ink">{verdict?.title}</p>
              <p className="mt-0.5 text-[13px] leading-relaxed text-muted">
                {why ?? verdict?.note}
              </p>
            </div>
          )}
        </div>

        {/* 점수 구성 */}
        <div className="shrink-0 lg:w-[204px]">
          <div className="space-y-2.5">
            {HIGHLIGHT_PARTS.map((part) => {
              const value = score?.parts?.[part.key] ?? 0;
              return (
                <div key={part.key}>
                  <div className="flex items-baseline justify-between">
                    <span className="text-[12px] text-muted">{part.label}</span>
                    <span className="num text-[12px] font-semibold text-ink">
                      {value}
                      <span className="text-subtle">/{part.max}</span>
                    </span>
                  </div>
                  <div className="mt-1 h-1 overflow-hidden rounded-full bg-surface-3">
                    <div
                      className="h-full rounded-full bg-ink transition-[width] duration-500"
                      style={{ width: `${(value / part.max) * 100}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>

          <div className="mt-5 space-y-1.5">
            <Link to={`/contests/${encodeURIComponent(contest.key)}`} className="block">
              <Button size="sm" variant="primary" className="w-full justify-center">
                분석 보기
                <ArrowRight className="h-3.5 w-3.5" />
              </Button>
            </Link>
            <StatusActions contest={contest} showEnter={false} fill />
          </div>
        </div>
      </div>
    </article>
  );
}
