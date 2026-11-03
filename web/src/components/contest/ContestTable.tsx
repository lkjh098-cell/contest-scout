import { Link, useNavigate } from "react-router-dom";
import { ArrowDown, ArrowUp } from "lucide-react";

import { cn } from "@/lib/cn";
import { STATUS_LABEL } from "@/lib/format";
import type { Contest } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";
import { DeadlinePill, PrizeText, SourceMark, TagList } from "./Bits";
import { ScoreValue, TierBadge } from "./TierBadge";

export interface SortState {
  sort: string;
  order: "asc" | "desc";
}

const COLUMNS: {
  key: string;
  label: string;
  sortable?: boolean;
  className?: string;
  align?: "right";
}[] = [
  { key: "tier", label: "등급", className: "w-[62px]" },
  { key: "title", label: "공모전", sortable: true },
  { key: "tags", label: "분야", className: "hidden w-[190px] xl:table-cell" },
  { key: "prize", label: "상금", sortable: true, className: "w-[104px]", align: "right" },
  { key: "deadline", label: "마감", sortable: true, className: "w-[86px]", align: "right" },
  { key: "score", label: "점수", sortable: true, className: "w-[68px]", align: "right" },
];

export function ContestTable({
  items,
  sortState,
  onSortChange,
  showStatus,
  emptyLabel = "조건에 맞는 공모전이 없습니다.",
}: {
  items: Contest[];
  sortState?: SortState;
  onSortChange?: (next: SortState) => void;
  showStatus?: boolean;
  emptyLabel?: string;
}) {
  const navigate = useNavigate();

  const toggle = (key: string) => {
    if (!onSortChange || !sortState) return;
    if (sortState.sort === key) {
      onSortChange({ sort: key, order: sortState.order === "desc" ? "asc" : "desc" });
    } else {
      onSortChange({ sort: key, order: key === "deadline" || key === "title" ? "asc" : "desc" });
    }
  };

  if (!items.length) {
    return <p className="px-4 py-12 text-center text-sm text-muted">{emptyLabel}</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] border-collapse text-left">
        <thead>
          <tr className="border-b border-line">
            {COLUMNS.map((column) => {
              const active = sortState?.sort === column.key;
              return (
                <th
                  key={column.key}
                  className={cn(
                    "label-xs px-3 py-2.5 font-semibold",
                    column.align === "right" && "text-right",
                    column.className,
                  )}
                >
                  {column.sortable && onSortChange ? (
                    <button
                      type="button"
                      onClick={() => toggle(column.key)}
                      className={cn(
                        "inline-flex items-center gap-1 transition-colors hover:text-ink",
                        active && "text-ink",
                      )}
                    >
                      {column.label}
                      {active &&
                        (sortState.order === "desc" ? (
                          <ArrowDown className="h-3 w-3" />
                        ) : (
                          <ArrowUp className="h-3 w-3" />
                        ))}
                    </button>
                  ) : (
                    column.label
                  )}
                </th>
              );
            })}
            {showStatus && <th className="label-xs w-[92px] px-3 py-2.5 text-right">상태</th>}
          </tr>
        </thead>
        <tbody>
          {items.map((contest) => (
            <tr
              key={contest.key}
              onClick={() => navigate(`/contests/${encodeURIComponent(contest.key)}`)}
              className="group cursor-pointer border-b border-line/70 transition-colors last:border-0 hover:bg-surface-2"
            >
              <td className="px-3 py-3">
                <TierBadge tier={contest.score?.tier} size="sm" />
              </td>
              <td className="px-3 py-3">
                <div className="flex items-center gap-2">
                  {contest.is_new_today && (
                    <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-accent" title="오늘 발견" />
                  )}
                  <Link
                    to={`/contests/${encodeURIComponent(contest.key)}`}
                    onClick={(event) => event.stopPropagation()}
                    className="line-clamp-1 text-[13.5px] font-medium text-ink decoration-line-strong underline-offset-2 group-hover:underline"
                  >
                    {contest.title}
                  </Link>
                </div>
                <div className="mt-1 flex items-center gap-2 text-[12px] text-subtle">
                  <span className="line-clamp-1 max-w-[280px]">{contest.organizer ?? "주최 미확인"}</span>
                  <span className="text-line-strong">·</span>
                  <SourceMark source={contest.source} sources={contest.duplicate_sources} />
                </div>
              </td>
              <td className="hidden px-3 py-3 xl:table-cell">
                <TagList tags={contest.tags} max={2} />
              </td>
              <td className="px-3 py-3 text-right">
                <PrizeText value={contest.best_prize_krw} />
              </td>
              <td className="px-3 py-3 text-right">
                <DeadlinePill days={contest.days_left} />
              </td>
              <td className="px-3 py-3 text-right">
                <ScoreValue score={contest.score?.total} />
              </td>
              {showStatus && (
                <td className="px-3 py-3 text-right">
                  <Badge
                    tone={
                      contest.status === "IGNORE" || contest.status === "EXPIRED"
                        ? "neutral"
                        : contest.status === "ENTERING" || contest.status === "SUBMITTED"
                          ? "success"
                          : contest.status === "INTERESTED"
                            ? "accent"
                            : "outline"
                    }
                  >
                    {STATUS_LABEL[contest.status] ?? contest.status}
                  </Badge>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
