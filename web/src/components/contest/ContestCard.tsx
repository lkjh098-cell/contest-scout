import { Link } from "react-router-dom";

import { cn } from "@/lib/cn";
import { formatPrize } from "@/lib/format";
import type { Contest } from "@/lib/types";
import { DeadlinePill, SourceMark, TagList } from "./Bits";
import { StatusActions } from "./StatusActions";
import { ScoreValue, TierBadge } from "./TierBadge";

/** 카드에는 정보 우선순위 상위 항목만 담는다. 상세 분석은 detail 화면에서. */
export function ContestCard({ contest }: { contest: Contest }) {
  return (
    <article
      className={cn(
        "group relative flex flex-col rounded-xl border border-line bg-surface p-4",
        "transition-colors hover:border-line-strong",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <TierBadge tier={contest.score?.tier} />
          <ScoreValue score={contest.score?.total} className="text-[15px]" />
          {contest.is_new_today && (
            <span className="rounded bg-accent-soft px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-accent">
              New
            </span>
          )}
        </div>
        <DeadlinePill days={contest.days_left} />
      </div>

      <Link
        to={`/contests/${encodeURIComponent(contest.key)}`}
        className="mt-3 line-clamp-2 text-[14.5px] font-semibold leading-snug tracking-[-0.01em] text-ink decoration-line-strong underline-offset-2 hover:underline"
      >
        {contest.title}
      </Link>

      <p className="mt-1.5 line-clamp-1 text-[12.5px] text-muted">
        {contest.organizer ?? "주최 미확인"}
      </p>

      <div className="mt-3">
        <TagList tags={contest.tags} max={3} />
      </div>

      <div className="mt-auto flex items-center justify-between gap-2 pt-4">
        <div>
          <span className="label-xs block">상금</span>
          <span
            className={cn(
              "num text-[13.5px] font-semibold",
              contest.best_prize_krw ? "text-ink" : "text-subtle",
            )}
          >
            {formatPrize(contest.best_prize_krw)}
          </span>
        </div>
        <SourceMark source={contest.source} sources={contest.duplicate_sources} />
      </div>

      <div className="mt-3 border-t border-line pt-3">
        <StatusActions contest={contest} />
      </div>
    </article>
  );
}
