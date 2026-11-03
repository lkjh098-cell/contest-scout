import { Link } from "react-router-dom";
import { ArrowUpRight, CalendarClock, Radar, Sparkles } from "lucide-react";

import { OpportunityMatrix } from "@/components/charts/OpportunityMatrix";
import { ContestTable } from "@/components/contest/ContestTable";
import { OpportunityCard } from "@/components/contest/OpportunityCard";
import { Button } from "@/components/ui/Button";
import { Panel, SectionHeader } from "@/components/ui/Panel";
import { Skeleton, SkeletonRows } from "@/components/ui/Skeleton";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { cn } from "@/lib/cn";
import { greeting } from "@/lib/format";
import { useDashboard } from "@/lib/queries";
import type { Dashboard } from "@/lib/types";

export function Overview() {
  const { data, isLoading, error, refetch } = useDashboard();

  if (error) return <ErrorState error={error} onRetry={() => void refetch()} />;
  if (isLoading || !data) return <OverviewSkeleton />;

  if (!data.has_any_data) {
    return (
      <Panel flush>
        <EmptyState
          icon={<Radar className="h-5 w-5" />}
          title="아직 수집한 공모전이 없습니다."
          description={
            <>
              오른쪽 위 <strong className="font-medium text-ink">Scout 실행</strong> 을 누르면
              씽굿과 링커리어에서 새 공모전을 가져옵니다.
              <br />
              첫 실행은 20~40초쯤 걸립니다.
            </>
          }
        />
      </Panel>
    );
  }

  const strong = data.top_opportunities.filter(
    (item) => item.score?.tier === "S" || item.score?.tier === "A",
  );

  return (
    <div className="space-y-7">
      <Greeting data={data} strongCount={strong.length} />

      <KpiRow data={data} />

      <section className="space-y-3">
        <SectionHeader
          title="오늘의 추천"
          description="점수·마감·역량 적합도를 함께 보고 고른 상위 후보입니다."
          action={
            <Link to="/discover">
              <Button size="sm" variant="ghost">
                전체 탐색
                <ArrowUpRight className="h-3.5 w-3.5" />
              </Button>
            </Link>
          }
        />
        {data.top_opportunities.length ? (
          <div className="space-y-3">
            {data.top_opportunities.map((contest, index) => (
              <OpportunityCard key={contest.key} contest={contest} rank={index + 1} />
            ))}
          </div>
        ) : (
          <Panel flush>
            <EmptyState
              icon={<Sparkles className="h-5 w-5" />}
              title="지금 강하게 추천할 공모전이 없습니다."
              description="추천 기준을 조금 넓히거나, 전체 목록에서 직접 골라 보세요."
              action={
                <Link to="/contests">
                  <Button size="sm">전체 공모전 보기</Button>
                </Link>
              }
            />
          </Panel>
        )}
      </section>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <Panel>
          <SectionHeader
            title="기회 매트릭스"
            description="오른쪽 위로 갈수록 먼저 봐야 할 공모전입니다."
          />
          <div className="mt-4">
            {data.matrix.length ? (
              <OpportunityMatrix points={data.matrix} />
            ) : (
              <p className="py-16 text-center text-[13px] text-subtle">
                점수가 매겨진 공모전이 아직 없습니다.
              </p>
            )}
          </div>
        </Panel>

        <Panel className="flex flex-col">
          <SectionHeader title="마감 임박" description="7일 안에 접수가 끝납니다." />
          <EndingSoon items={data.matrix} />
        </Panel>
      </div>

      <Panel flush>
        <div className="px-5 pt-5">
          <SectionHeader
            title="오늘 새로 발견한 공모전"
            description={`${data.kpi.new_today}건을 새로 수집했습니다.`}
            action={
              <Link to="/discover?new=1">
                <Button size="sm" variant="ghost">
                  모두 보기
                  <ArrowUpRight className="h-3.5 w-3.5" />
                </Button>
              </Link>
            }
          />
        </div>
        <div className="mt-4">
          {data.new_contests.length ? (
            <ContestTable items={data.new_contests} />
          ) : (
            <EmptyState
              icon={<CalendarClock className="h-5 w-5" />}
              title="오늘 새로 올라온 공모전은 없습니다."
              description={
                data.schedule.enabled
                  ? `다음 자동 수집은 매일 ${data.schedule.time}에 실행됩니다.`
                  : "Scout 실행을 누르면 지금 바로 확인합니다."
              }
            />
          )}
        </div>
      </Panel>
    </div>
  );
}

function Greeting({ data, strongCount }: { data: Dashboard; strongCount: number }) {
  const { new_today: newToday } = data.kpi;
  return (
    <div className="fade-up">
      <p className="text-[13px] font-medium text-muted">{greeting()}</p>
      <h2 className="mt-1 text-[26px] font-semibold leading-tight tracking-[-0.025em] text-ink">
        {newToday > 0 ? (
          <>
            오늘 새 공모전 <span className="num">{newToday}</span>개를 발견했습니다.
            {strongCount > 0 && (
              <>
                {" "}
                그중 <span className="num">{strongCount}</span>개를 추천합니다.
              </>
            )}
          </>
        ) : (
          <>오늘 새로 올라온 공모전은 없습니다.</>
        )}
      </h2>
    </div>
  );
}

const KPIS: {
  key: keyof Dashboard["kpi"];
  label: string;
  to: string;
  accent?: boolean;
}[] = [
  { key: "new_today", label: "오늘 신규", to: "/discover?new=1", accent: true },
  { key: "s_tier", label: "S등급", to: "/discover?tier=S" },
  { key: "ending_soon", label: "마감 7일 이내", to: "/discover?deadline=7" },
  { key: "active_contests", label: "진행 중 공모전", to: "/contests" },
];

function KpiRow({ data }: { data: Dashboard }) {
  return (
    <div className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-line bg-line lg:grid-cols-4">
      {KPIS.map((kpi) => (
        <Link
          key={kpi.key}
          to={kpi.to}
          className="group bg-surface px-5 py-4 transition-colors hover:bg-surface-2"
        >
          <p className="label-xs">{kpi.label}</p>
          <p
            className={cn(
              "num mt-2 text-[30px] font-semibold leading-none tracking-[-0.035em]",
              kpi.accent && data.kpi[kpi.key] > 0 ? "text-ink" : "text-ink",
              data.kpi[kpi.key] === 0 && "text-subtle",
            )}
          >
            {data.kpi[kpi.key]}
          </p>
        </Link>
      ))}
    </div>
  );
}

function EndingSoon({ items }: { items: Dashboard["matrix"] }) {
  const soon = items
    .filter((item) => item.days_left !== null && item.days_left >= 0 && item.days_left <= 7)
    .sort((a, b) => (a.days_left ?? 0) - (b.days_left ?? 0))
    .slice(0, 7);

  if (!soon.length) {
    return (
      <p className="py-10 text-center text-[13px] text-subtle">
        일주일 안에 마감되는 공모전이 없습니다.
      </p>
    );
  }

  return (
    <ul className="mt-3 divide-y divide-line">
      {soon.map((item) => (
        <li key={item.key}>
          <Link
            to={`/contests/${encodeURIComponent(item.key)}`}
            className="flex items-center gap-3 py-2.5 transition-colors hover:text-ink"
          >
            <span
              className={cn(
                "num w-9 shrink-0 rounded px-1 py-0.5 text-center text-[11px] font-bold",
                (item.days_left ?? 0) <= 3
                  ? "bg-danger-soft text-danger"
                  : "bg-warn-soft text-warn",
              )}
            >
              D-{item.days_left}
            </span>
            <span className="line-clamp-1 grow text-[13px] text-ink">{item.title}</span>
            <span className="num shrink-0 text-[12px] font-medium text-muted">{item.total}</span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

function OverviewSkeleton() {
  return (
    <div className="space-y-7">
      <div className="space-y-2">
        <Skeleton className="h-3.5 w-24" />
        <Skeleton className="h-7 w-96 max-w-full" />
      </div>
      <div className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-line bg-line lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="bg-surface px-5 py-4">
            <Skeleton className="h-3 w-20" />
            <Skeleton className="mt-3 h-7 w-12" />
          </div>
        ))}
      </div>
      <div className="space-y-3">
        {Array.from({ length: 2 }).map((_, index) => (
          <div key={index} className="rounded-xl border border-line bg-surface p-5">
            <div className="flex gap-6">
              <Skeleton className="h-16 w-16" />
              <div className="grow space-y-3">
                <Skeleton className="h-4 w-2/3" />
                <Skeleton className="h-3 w-1/3" />
                <Skeleton className="h-3 w-1/2" />
              </div>
              <Skeleton className="h-16 w-40" />
            </div>
          </div>
        ))}
      </div>
      <div className="rounded-xl border border-line bg-surface">
        <SkeletonRows rows={5} />
      </div>
    </div>
  );
}
