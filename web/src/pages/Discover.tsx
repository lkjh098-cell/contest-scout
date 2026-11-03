import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { Filter, LayoutGrid, List, Search, SlidersHorizontal, X } from "lucide-react";

import { ContestCard } from "@/components/contest/ContestCard";
import { ContestTable, type SortState } from "@/components/contest/ContestTable";
import { Button } from "@/components/ui/Button";
import { Checkbox, Input, RadioGroup, Segmented, Select } from "@/components/ui/Form";
import { Panel } from "@/components/ui/Panel";
import { Skeleton, SkeletonRows } from "@/components/ui/Skeleton";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { cn } from "@/lib/cn";
import { useContests, useFacets } from "@/lib/queries";

const TIERS = ["S", "A", "B", "SKIP"] as const;
const SOURCE_LABEL: Record<string, string> = { thinkgood: "씽굿", linkareer: "링커리어" };

const PRIZE_OPTIONS = [
  { value: 0, label: "전체" },
  { value: 1_000_000, label: "100만원 이상" },
  { value: 3_000_000, label: "300만원 이상" },
  { value: 5_000_000, label: "500만원 이상" },
  { value: 10_000_000, label: "1,000만원 이상" },
];

const DEADLINE_OPTIONS = [
  { value: 0, label: "전체" },
  { value: 7, label: "7일 이내" },
  { value: 14, label: "14일 이내" },
  { value: 30, label: "30일 이내" },
];

const SORT_OPTIONS = [
  { value: "score", label: "추천 점수순" },
  { value: "deadline", label: "마감 임박순" },
  { value: "prize", label: "상금 높은순" },
  { value: "discovered", label: "최근 발견순" },
];

export function Discover() {
  const [params, setParams] = useSearchParams();
  const { data: facets } = useFacets();

  const [search, setSearch] = useState(params.get("q") ?? "");
  const [debounced, setDebounced] = useState(search);
  const [tiers, setTiers] = useState<string[]>(params.getAll("tier"));
  const [tags, setTags] = useState<string[]>(params.getAll("tag"));
  const [sources, setSources] = useState<string[]>(params.getAll("source"));
  const [minPrize, setMinPrize] = useState(Number(params.get("prize") ?? 0));
  const [deadline, setDeadline] = useState(Number(params.get("deadline") ?? 0));
  const [onlyNew, setOnlyNew] = useState(params.get("new") === "1");
  const [sortState, setSortState] = useState<SortState>({ sort: "score", order: "desc" });
  const [view, setView] = useState<"card" | "table">("card");
  const [page, setPage] = useState(1);
  const [filtersOpen, setFiltersOpen] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(search), 260);
    return () => window.clearTimeout(timer);
  }, [search]);

  // 필터를 URL에 남긴다. 새로고침해도, 링크를 공유해도 같은 화면이 열린다.
  useEffect(() => {
    const next = new URLSearchParams();
    if (debounced) next.set("q", debounced);
    tiers.forEach((tier) => next.append("tier", tier));
    tags.forEach((tag) => next.append("tag", tag));
    sources.forEach((source) => next.append("source", source));
    if (minPrize) next.set("prize", String(minPrize));
    if (deadline) next.set("deadline", String(deadline));
    if (onlyNew) next.set("new", "1");
    setParams(next, { replace: true });
    setPage(1);
  }, [debounced, tiers, tags, sources, minPrize, deadline, onlyNew, setParams]);

  const filters = useMemo(
    () => ({
      q: debounced || undefined,
      tier: tiers.length ? tiers : undefined,
      tag: tags.length ? tags : undefined,
      source: sources.length ? sources : undefined,
      min_prize: minPrize || undefined,
      deadline_within: deadline || undefined,
      only_new_today: onlyNew || undefined,
      sort: sortState.sort,
      order: sortState.order,
      page,
      page_size: 24,
    }),
    [debounced, tiers, tags, sources, minPrize, deadline, onlyNew, sortState, page],
  );

  const { data, isLoading, isFetching, error, refetch } = useContests(filters);

  const activeCount =
    tiers.length + tags.length + sources.length + (minPrize ? 1 : 0) + (deadline ? 1 : 0) + (onlyNew ? 1 : 0);

  const reset = () => {
    setTiers([]);
    setTags([]);
    setSources([]);
    setMinPrize(0);
    setDeadline(0);
    setOnlyNew(false);
    setSearch("");
  };

  const toggle = (list: string[], setList: (next: string[]) => void, value: string) =>
    setList(list.includes(value) ? list.filter((item) => item !== value) : [...list, value]);

  return (
    <div className="flex gap-6">
      <aside
        className={cn(
          "w-[224px] shrink-0",
          filtersOpen
            ? "fixed inset-y-0 right-0 z-40 w-[280px] overflow-y-auto border-l border-line bg-surface p-5 shadow-float lg:static lg:z-auto lg:w-[224px] lg:border-0 lg:bg-transparent lg:p-0 lg:shadow-none"
            : "hidden lg:block",
        )}
      >
        <div className="mb-4 flex items-center justify-between lg:hidden">
          <span className="text-[14px] font-semibold text-ink">필터</span>
          <button type="button" onClick={() => setFiltersOpen(false)} className="text-subtle">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="sticky top-[76px] space-y-6">
          <FilterGroup label="등급">
            {TIERS.map((tier) => (
              <Checkbox
                key={tier}
                checked={tiers.includes(tier)}
                onChange={() => toggle(tiers, setTiers, tier)}
                label={tier === "SKIP" ? "제외 대상" : `${tier} 등급`}
                count={facets?.tiers?.[tier]}
              />
            ))}
          </FilterGroup>

          <FilterGroup label="분야">
            <div className="max-h-[248px] overflow-y-auto pr-1">
              {(facets?.tags ?? []).map((tag) => (
                <Checkbox
                  key={tag.tag}
                  checked={tags.includes(tag.tag)}
                  onChange={() => toggle(tags, setTags, tag.tag)}
                  label={tag.tag}
                  count={tag.count}
                />
              ))}
            </div>
          </FilterGroup>

          <FilterGroup label="상금">
            <RadioGroup value={minPrize} onChange={setMinPrize} options={PRIZE_OPTIONS} />
          </FilterGroup>

          <FilterGroup label="마감">
            <RadioGroup value={deadline} onChange={setDeadline} options={DEADLINE_OPTIONS} />
          </FilterGroup>

          <FilterGroup label="소스">
            {(facets?.sources ?? []).map((source) => (
              <Checkbox
                key={source.source}
                checked={sources.includes(source.source)}
                onChange={() => toggle(sources, setSources, source.source)}
                label={SOURCE_LABEL[source.source] ?? source.source}
                count={source.count}
              />
            ))}
          </FilterGroup>

          <FilterGroup label="기타">
            <Checkbox checked={onlyNew} onChange={setOnlyNew} label="오늘 발견한 것만" />
          </FilterGroup>

          {activeCount > 0 && (
            <Button size="sm" variant="ghost" onClick={reset} className="w-full">
              필터 초기화 ({activeCount})
            </Button>
          )}
        </div>
      </aside>

      <div className="min-w-0 grow space-y-4">
        <div className="flex flex-wrap items-center gap-2.5">
          <div className="relative min-w-[200px] grow">
            <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-subtle" />
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="공모전 · 주최기관 검색"
              className="pl-9"
            />
          </div>

          <Select
            value={sortState.sort}
            onChange={(event) =>
              setSortState({
                sort: event.target.value,
                order: event.target.value === "deadline" ? "asc" : "desc",
              })
            }
            className="w-[148px]"
          >
            {SORT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>

          <Segmented
            value={view}
            onChange={setView}
            options={[
              { value: "card", label: <LayoutGrid className="h-3.5 w-3.5" /> },
              { value: "table", label: <List className="h-3.5 w-3.5" /> },
            ]}
          />

          <Button
            size="md"
            className="lg:hidden"
            onClick={() => setFiltersOpen(true)}
          >
            <SlidersHorizontal className="h-3.5 w-3.5" />
            필터{activeCount > 0 && ` ${activeCount}`}
          </Button>
        </div>

        <div className="flex items-center justify-between text-[12.5px] text-muted">
          <span className="num">
            {data ? `${data.total.toLocaleString("ko-KR")}건` : "불러오는 중"}
            {isFetching && !isLoading && <span className="ml-2 text-subtle">갱신 중…</span>}
          </span>
        </div>

        {error ? (
          <ErrorState error={error} onRetry={() => void refetch()} />
        ) : isLoading ? (
          view === "card" ? (
            <div className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-3">
              {Array.from({ length: 6 }).map((_, index) => (
                <div key={index} className="rounded-xl border border-line bg-surface p-4">
                  <Skeleton className="h-5 w-20" />
                  <Skeleton className="mt-4 h-4 w-full" />
                  <Skeleton className="mt-2 h-4 w-2/3" />
                  <Skeleton className="mt-5 h-3 w-1/2" />
                </div>
              ))}
            </div>
          ) : (
            <Panel flush>
              <SkeletonRows />
            </Panel>
          )
        ) : !data || data.items.length === 0 ? (
          <Panel flush>
            <EmptyState
              icon={<Filter className="h-5 w-5" />}
              title="조건에 맞는 공모전이 없습니다."
              description="필터를 조금 넓혀 보세요. 등급 제한을 풀면 후보가 크게 늘어납니다."
              action={
                activeCount > 0 ? (
                  <Button size="sm" onClick={reset}>
                    필터 초기화
                  </Button>
                ) : undefined
              }
            />
          </Panel>
        ) : view === "card" ? (
          <div className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-3">
            {data.items.map((contest) => (
              <ContestCard key={contest.key} contest={contest} />
            ))}
          </div>
        ) : (
          <Panel flush>
            <ContestTable items={data.items} sortState={sortState} onSortChange={setSortState} />
          </Panel>
        )}

        {data && data.total > data.page_size && (
          <Pager
            page={data.page}
            pageSize={data.page_size}
            total={data.total}
            onChange={setPage}
          />
        )}
      </div>
    </div>
  );
}

function FilterGroup({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <p className="label-xs mb-1.5 px-1.5">{label}</p>
      <div className="-mx-1.5">{children}</div>
    </div>
  );
}

export function Pager({
  page,
  pageSize,
  total,
  onChange,
}: {
  page: number;
  pageSize: number;
  total: number;
  onChange: (page: number) => void;
}) {
  const pages = Math.ceil(total / pageSize);
  return (
    <div className="flex items-center justify-between border-t border-line pt-4">
      <span className="num text-[12.5px] text-subtle">
        {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)} / {total.toLocaleString("ko-KR")}
      </span>
      <div className="flex items-center gap-1.5">
        <Button size="sm" disabled={page <= 1} onClick={() => onChange(page - 1)}>
          이전
        </Button>
        <span className="num px-2 text-[12.5px] text-muted">
          {page} / {pages}
        </span>
        <Button size="sm" disabled={page >= pages} onClick={() => onChange(page + 1)}>
          다음
        </Button>
      </div>
    </div>
  );
}
