import { Link } from "react-router-dom";
import { CircleCheck, CircleSlash, TriangleAlert, Waypoints } from "lucide-react";
import type { ReactNode } from "react";

import { TierBadge } from "@/components/contest/TierBadge";
import { Panel } from "@/components/ui/Panel";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { cn } from "@/lib/cn";
import { formatDateTime, RUN_STATUS_LABEL } from "@/lib/format";
import { useRuns } from "@/lib/queries";
import type { ScoutRun } from "@/lib/types";

const SOURCE_LABEL: Record<string, string> = { thinkgood: "씽굿", linkareer: "링커리어" };

const STATUS_STYLE: Record<string, { className: string; icon: ReactNode }> = {
  SUCCESS: { className: "text-success", icon: <CircleCheck className="h-3.5 w-3.5" /> },
  PARTIAL: { className: "text-warn", icon: <TriangleAlert className="h-3.5 w-3.5" /> },
  FAILED: { className: "text-danger", icon: <CircleSlash className="h-3.5 w-3.5" /> },
  RUNNING: { className: "text-accent", icon: <span className="h-1.5 w-1.5 rounded-full bg-accent dot-live" /> },
};

export function Runs() {
  const { data, isLoading, error, refetch } = useRuns();

  if (error) return <ErrorState error={error} onRetry={() => void refetch()} />;

  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 3 }).map((_, index) => (
          <div key={index} className="rounded-xl border border-line bg-surface p-5">
            <Skeleton className="h-4 w-40" />
            <Skeleton className="mt-4 h-3 w-full" />
          </div>
        ))}
      </div>
    );
  }

  if (!data?.length) {
    return (
      <Panel flush>
        <EmptyState
          icon={<Waypoints className="h-5 w-5" />}
          title="아직 실행 기록이 없습니다."
          description="Scout을 한 번 실행하면 언제 무엇을 수집했는지 여기에 남습니다."
        />
      </Panel>
    );
  }

  return (
    <div className="space-y-3">
      {data.map((run) => (
        <RunCard key={run.id} run={run} />
      ))}
    </div>
  );
}

function RunCard({ run }: { run: ScoutRun }) {
  const style = STATUS_STYLE[run.status] ?? STATUS_STYLE.SUCCESS;
  const sources = Object.entries(run.stats);

  return (
    <article className="rounded-xl border border-line bg-surface">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-line px-5 py-3.5">
        <span className="num text-[13px] font-medium text-ink">
          {formatDateTime(run.started_at)}
        </span>
        <span className={cn("inline-flex items-center gap-1.5 text-[12px] font-semibold", style.className)}>
          {style.icon}
          {RUN_STATUS_LABEL[run.status] ?? run.status}
        </span>
        <span className="text-[12px] text-subtle">
          {run.trigger === "schedule" ? "자동 실행" : run.trigger === "cli" ? "터미널" : "수동 실행"}
        </span>
        <div className="num ml-auto flex items-center gap-4 text-[12px] text-muted">
          <span>
            신규 <span className="font-semibold text-ink">{run.total_new}</span>
          </span>
          <span>확인 {run.total_seen}</span>
          <span>요청 {run.requests}</span>
          {run.duration_sec !== null && <span>{run.duration_sec}초</span>}
        </div>
      </div>

      <div className="grid gap-px bg-line sm:grid-cols-2">
        {sources.length === 0 && (
          <p className="bg-surface px-5 py-4 text-[13px] text-subtle">
            소스별 통계가 기록되지 않았습니다.
          </p>
        )}
        {sources.map(([name, stats]) => (
          <div key={name} className="bg-surface px-5 py-4">
            <div className="flex items-center gap-2">
              <span className="text-[13px] font-medium text-ink">
                {SOURCE_LABEL[name] ?? name}
              </span>
              <span
                className={cn(
                  "text-[11px] font-semibold",
                  stats.skipped_reason || stats.errors ? "text-danger" : "text-success",
                )}
              >
                {stats.skipped_reason ? "건너뜀" : stats.errors ? `오류 ${stats.errors}` : "정상"}
              </span>
              <span className="num ml-auto text-[11px] text-subtle">robots {stats.robots}</span>
            </div>
            <div className="num mt-2.5 grid grid-cols-3 gap-x-6 gap-y-1.5 text-[12px]">
              <Metric label="발견" value={stats.discovered} />
              <Metric label="신규" value={stats.new} strong={stats.new > 0} />
              <Metric label="기존" value={stats.existing} />
              <Metric label="상세 조회" value={stats.details_fetched} />
              <Metric label="HTTP 요청" value={stats.requests} />
              <Metric label="페이지" value={stats.list_pages} />
            </div>
            {stats.skipped_reason && (
              <p className="mt-3 rounded-lg bg-danger-soft px-2.5 py-2 text-[12px] leading-relaxed text-danger">
                {stats.skipped_reason}
              </p>
            )}
          </div>
        ))}
      </div>

      {run.errors.length > 0 && (
        <div className="space-y-1 border-t border-line px-5 py-3">
          {run.errors.map((error) => (
            <p key={error.source} className="text-[12px] leading-relaxed text-danger">
              <span className="font-semibold">{SOURCE_LABEL[error.source] ?? error.source}</span> —{" "}
              {error.reason}
            </p>
          ))}
        </div>
      )}

      {run.new_titles.length > 0 && (
        <ul className="border-t border-line px-5 py-3">
          {run.new_titles.slice(0, 5).map((item) => (
            <li key={item.key} className="flex items-center gap-2.5 py-1">
              <TierBadge tier={item.tier} size="sm" />
              <Link
                to={`/contests/${encodeURIComponent(item.key)}`}
                className="line-clamp-1 grow text-[12.5px] text-muted transition-colors hover:text-ink"
              >
                {item.title}
              </Link>
              <span className="num shrink-0 text-[12px] font-medium text-muted">{item.total}</span>
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}

function Metric({ label, value, strong }: { label: string; value: number; strong?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-2">
      <span className="text-subtle">{label}</span>
      <span className={cn(strong ? "font-semibold text-ink" : "text-muted")}>{value}</span>
    </div>
  );
}
