import { ExternalLink, Plus } from "lucide-react";

import { Panel, SectionHeader } from "@/components/ui/Panel";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/States";
import { cn } from "@/lib/cn";
import { relativeTime } from "@/lib/format";
import { useSources } from "@/lib/queries";

const SOURCE_META: Record<string, { label: string; note: string }> = {
  thinkgood: {
    label: "씽굿",
    note: "목록 JSON 응답에 상세 요강까지 들어 있어, 하루 요청 1회로 신규 공모전을 전부 확보합니다.",
  },
  linkareer: {
    label: "링커리어",
    note: "목록에서 신규 건만 골라 상세 페이지를 따로 읽습니다. 이미 아는 공모전은 요청하지 않습니다.",
  },
};

const PLANNED = ["위비티 (Wevity)", "콘테스트코리아", "올콘"];

export function SourcesPage() {
  const { data, isLoading, error, refetch } = useSources();

  if (error) return <ErrorState error={error} onRetry={() => void refetch()} />;

  return (
    <div className="space-y-5">
      <div className="grid gap-4 md:grid-cols-2">
        {isLoading
          ? Array.from({ length: 2 }).map((_, index) => (
              <div key={index} className="rounded-xl border border-line bg-surface p-5">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="mt-4 h-3 w-full" />
                <Skeleton className="mt-2 h-3 w-2/3" />
              </div>
            ))
          : data?.map((source) => {
              const meta = SOURCE_META[source.name];
              const healthy = source.robots === "ALLOW" && !source.skipped_reason && !source.errors;
              return (
                <Panel key={source.name}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span
                          className={cn(
                            "h-1.5 w-1.5 rounded-full",
                            source.last_checked
                              ? healthy
                                ? "bg-success"
                                : "bg-danger"
                              : "bg-line-strong",
                          )}
                        />
                        <h3 className="text-[15px] font-semibold tracking-[-0.01em] text-ink">
                          {meta?.label ?? source.name}
                        </h3>
                        <span className="text-[12px] text-muted">
                          {source.last_checked ? (healthy ? "정상" : "확인 필요") : "미확인"}
                        </span>
                      </div>
                      <p className="mt-2 text-[12.5px] leading-relaxed text-muted">
                        {meta?.note}
                      </p>
                    </div>
                    <a
                      href={source.entry_url}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="shrink-0 rounded-lg p-1.5 text-subtle transition-colors hover:bg-surface-3 hover:text-ink"
                      title="사이트 열기"
                    >
                      <ExternalLink className="h-3.5 w-3.5" />
                    </a>
                  </div>

                  <dl className="num mt-5 grid grid-cols-2 gap-x-5 gap-y-3 border-t border-line pt-4 text-[12.5px]">
                    <Row label="마지막 확인" value={relativeTime(source.last_checked)} />
                    <Row label="robots.txt" value={source.robots ?? "미확인"} />
                    <Row label="저장된 공모전" value={`${source.stored_contests}건`} />
                    <Row
                      label="최근 실행"
                      value={
                        source.last_discovered !== null
                          ? `${source.last_discovered}건 확인 · 신규 ${source.last_new ?? 0}`
                          : "기록 없음"
                      }
                    />
                  </dl>

                  {source.skipped_reason && (
                    <p className="mt-4 rounded-lg bg-danger-soft px-3 py-2.5 text-[12px] leading-relaxed text-danger">
                      {source.skipped_reason}
                    </p>
                  )}
                </Panel>
              );
            })}
      </div>

      <Panel>
        <SectionHeader
          title="추가 예정 소스"
          description="소스 어댑터 하나만 구현하면 목록·필터·통계에 자동으로 반영됩니다."
        />
        <ul className="mt-4 space-y-2">
          {PLANNED.map((name) => (
            <li
              key={name}
              className="flex items-center gap-2.5 rounded-lg border border-dashed border-line px-3 py-2.5"
            >
              <Plus className="h-3.5 w-3.5 text-subtle" />
              <span className="text-[13px] text-muted">{name}</span>
              <span className="ml-auto text-[11px] uppercase tracking-wide text-subtle">예정</span>
            </li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-2">
      <dt className="shrink-0 text-subtle">{label}</dt>
      <dd className="truncate text-right text-ink">{value}</dd>
    </div>
  );
}
