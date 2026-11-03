import { BarList, StatBlock } from "@/components/charts/BarList";
import { DiscoveryChart } from "@/components/charts/DiscoveryChart";
import { Panel, SectionHeader } from "@/components/ui/Panel";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/States";
import { cn } from "@/lib/cn";
import { formatPrize } from "@/lib/format";
import { useAnalytics } from "@/lib/queries";

const SOURCE_LABEL: Record<string, string> = { thinkgood: "씽굿", linkareer: "링커리어" };

export function AnalyticsPage() {
  const { data, isLoading, error, refetch } = useAnalytics();

  if (error) return <ErrorState error={error} onRetry={() => void refetch()} />;
  if (isLoading || !data) return <AnalyticsSkeleton />;

  const { discovery, selection } = data;
  const totalTiers = data.tiers.reduce((sum, tier) => sum + tier.count, 0);

  return (
    <div className="space-y-5">
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_320px]">
        <Panel>
          <SectionHeader
            title="발견 추이"
            description="최근 30일간 새로 수집된 공모전 수입니다."
          />
          <div className="mt-5 flex flex-wrap items-end gap-8">
            <StatBlock label="이번 주" value={discovery.this_week} />
            <StatBlock label="지난 주" value={discovery.last_week} />
            <StatBlock
              label="증감"
              value={
                discovery.delta_pct === null
                  ? "—"
                  : `${discovery.delta_pct > 0 ? "+" : ""}${discovery.delta_pct}%`
              }
              tone={
                discovery.delta_pct === null
                  ? undefined
                  : discovery.delta_pct >= 0
                    ? "up"
                    : "down"
              }
              sub={discovery.delta_pct === null ? "비교할 지난주 데이터 없음" : undefined}
            />
          </div>
          <div className="mt-5">
            <DiscoveryChart data={discovery.daily} />
          </div>
        </Panel>

        <Panel>
          <SectionHeader title="등급 분포" description="규칙 기반 점수로 나눈 결과입니다." />
          <div className="mt-5 space-y-3">
            {data.tiers.map((tier) => (
              <div key={tier.name}>
                <div className="flex items-baseline justify-between">
                  <span className="text-[13px] font-medium text-ink">
                    {tier.name === "SKIP" ? "제외 대상" : `${tier.name} 등급`}
                  </span>
                  <span className="num text-[13px] text-muted">
                    {tier.count}
                    {totalTiers > 0 && (
                      <span className="ml-1.5 text-subtle">
                        {Math.round((tier.count / totalTiers) * 100)}%
                      </span>
                    )}
                  </span>
                </div>
                <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-surface-3">
                  <div
                    className={cn(
                      "h-full rounded-full",
                      tier.name === "S" && "bg-[var(--tier-s-fg)]",
                      tier.name === "A" && "bg-accent",
                      tier.name === "B" && "bg-muted",
                      tier.name === "SKIP" && "bg-line-strong",
                    )}
                    style={{
                      width: `${totalTiers ? Math.max(1, (tier.count / totalTiers) * 100) : 0}%`,
                    }}
                  />
                </div>
              </div>
            ))}
          </div>

          <div className="mt-6 grid grid-cols-2 gap-4 border-t border-line pt-4">
            <StatBlock label="추천됨" value={data.recommended_vs_ignored.recommended} />
            <StatBlock label="무시함" value={data.recommended_vs_ignored.ignored} />
          </div>
        </Panel>
      </div>

      <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
        <Panel>
          <SectionHeader title="분야 분포" description="상위 8개 분야" />
          <BarList items={data.categories} className="mt-4" />
        </Panel>

        <Panel>
          <SectionHeader title="상금 분포" description="1등 상금 기준" />
          <BarList items={data.prize_distribution} className="mt-4" tone="accent" />
        </Panel>

        <Panel>
          <SectionHeader title="마감 분포" description="진행 중인 공모전만" />
          <BarList items={data.deadline_distribution} className="mt-4" />
        </Panel>
      </div>

      <div className="grid gap-5 md:grid-cols-[320px_minmax(0,1fr)]">
        <Panel>
          <SectionHeader title="소스 분포" />
          <BarList
            items={data.sources.map((source) => ({
              name: SOURCE_LABEL[source.name] ?? source.name,
              count: source.count,
            }))}
            className="mt-4"
          />
        </Panel>

        <Panel>
          <SectionHeader
            title="선택 패턴"
            description="내가 실제로 고른 공모전에서 뽑은 값입니다. 앞으로 추천 기준을 다듬는 근거가 됩니다."
          />
          <div className="mt-5 grid gap-6 sm:grid-cols-3">
            <StatBlock
              label="S등급 중 선택 비율"
              value={
                selection.s_tier_shortlist_rate === null
                  ? "—"
                  : `${selection.s_tier_shortlist_rate}%`
              }
              sub={
                selection.s_tier_total
                  ? `S등급 ${selection.s_tier_total}건 기준`
                  : "S등급 공모전이 아직 없습니다"
              }
            />
            <StatBlock
              label="영상 공모전 선택률"
              value={
                selection.video_selection_rate === null ? "—" : `${selection.video_selection_rate}%`
              }
              sub={
                selection.video_total
                  ? `영상 분야 ${selection.video_total}건 기준`
                  : "영상 분야 데이터 없음"
              }
            />
            <StatBlock
              label="평균 선택 상금"
              value={
                selection.avg_selected_prize ? formatPrize(selection.avg_selected_prize) : "—"
              }
              sub={
                selection.selected_count
                  ? `선택한 ${selection.selected_count}건 기준`
                  : "아직 고른 공모전이 없습니다"
              }
            />
          </div>
          {selection.selected_count === 0 && (
            <p className="mt-5 border-t border-line pt-4 text-[12.5px] leading-relaxed text-subtle">
              Shortlist나 참가하기를 몇 번 눌러 두면 여기에 실제 선택 패턴이 쌓입니다. 값을 지어내지
              않기 때문에, 데이터가 없으면 비워 둡니다.
            </p>
          )}
        </Panel>
      </div>
    </div>
  );
}

function AnalyticsSkeleton() {
  return (
    <div className="space-y-5">
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="rounded-xl border border-line bg-surface p-5">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="mt-6 h-8 w-48" />
          <Skeleton className="mt-6 h-[180px] w-full" />
        </div>
        <div className="rounded-xl border border-line bg-surface p-5">
          <Skeleton className="h-4 w-20" />
          <div className="mt-6 space-y-4">
            {Array.from({ length: 4 }).map((_, index) => (
              <Skeleton key={index} className="h-3 w-full" />
            ))}
          </div>
        </div>
      </div>
      <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 3 }).map((_, index) => (
          <div key={index} className="rounded-xl border border-line bg-surface p-5">
            <Skeleton className="h-4 w-20" />
            <div className="mt-5 space-y-3">
              {Array.from({ length: 5 }).map((__, row) => (
                <Skeleton key={row} className="h-3 w-full" />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
