import { useEffect, useMemo, useState } from "react";
import { Search } from "lucide-react";

import { ContestTable, type SortState } from "@/components/contest/ContestTable";
import { Input } from "@/components/ui/Form";
import { Panel } from "@/components/ui/Panel";
import { SkeletonRows } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/States";
import { cn } from "@/lib/cn";
import { STATUS_LABEL } from "@/lib/format";
import { useContests, useFacets } from "@/lib/queries";
import { Pager } from "./Discover";

const STATUS_TABS: { value: string | null; label: string }[] = [
  { value: null, label: "진행 중" },
  { value: "NEW", label: STATUS_LABEL.NEW },
  { value: "RECOMMENDED", label: STATUS_LABEL.RECOMMENDED },
  { value: "INTERESTED", label: STATUS_LABEL.INTERESTED },
  { value: "ENTERING", label: STATUS_LABEL.ENTERING },
  { value: "SUBMITTED", label: STATUS_LABEL.SUBMITTED },
  { value: "IGNORE", label: STATUS_LABEL.IGNORE },
  { value: "EXPIRED", label: STATUS_LABEL.EXPIRED },
];

export function AllContests() {
  const [status, setStatus] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [sortState, setSortState] = useState<SortState>({ sort: "score", order: "desc" });
  const [page, setPage] = useState(1);
  const { data: facets } = useFacets();

  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(search), 260);
    return () => window.clearTimeout(timer);
  }, [search]);

  useEffect(() => setPage(1), [status, debounced, sortState]);

  const filters = useMemo(
    () => ({
      q: debounced || undefined,
      status: status ? [status] : undefined,
      sort: sortState.sort,
      order: sortState.order,
      page,
      page_size: 40,
    }),
    [debounced, status, sortState, page],
  );

  const { data, isLoading, error, refetch } = useContests(filters);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2.5">
        <div className="relative min-w-[220px] grow sm:max-w-[320px]">
          <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-subtle" />
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="공모전 · 주최기관 검색"
            className="pl-9"
          />
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-1 border-b border-line pb-px">
        {STATUS_TABS.map((tab) => {
          const active = tab.value === status;
          const count = tab.value ? facets?.statuses?.[tab.value] : undefined;
          return (
            <button
              key={tab.label}
              type="button"
              onClick={() => setStatus(tab.value)}
              className={cn(
                "relative px-2.5 py-2 text-[13px] transition-colors",
                active ? "font-medium text-ink" : "text-muted hover:text-ink",
              )}
            >
              {tab.label}
              {count !== undefined && count > 0 && (
                <span className="num ml-1.5 text-[11px] text-subtle">{count}</span>
              )}
              {active && <span className="absolute inset-x-1.5 -bottom-px h-0.5 rounded-full bg-ink" />}
            </button>
          );
        })}
      </div>

      {error ? (
        <ErrorState error={error} onRetry={() => void refetch()} />
      ) : (
        <Panel flush>
          {isLoading ? (
            <SkeletonRows rows={10} />
          ) : (
            <ContestTable
              items={data?.items ?? []}
              sortState={sortState}
              onSortChange={setSortState}
              showStatus
              emptyLabel={
                status ? `‘${STATUS_LABEL[status]}’ 상태인 공모전이 없습니다.` : "표시할 공모전이 없습니다."
              }
            />
          )}
        </Panel>
      )}

      {data && data.total > data.page_size && (
        <Pager page={data.page} pageSize={data.page_size} total={data.total} onChange={setPage} />
      )}
    </div>
  );
}
