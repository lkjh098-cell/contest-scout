import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { Outlet, useLocation } from "react-router-dom";

import { useTheme } from "@/components/ui/Toast";
import { useDashboard, useFacets } from "@/lib/queries";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

interface PageMeta {
  title: string;
  subtitle?: ReactNode;
}

const ROUTE_META: Record<string, PageMeta> = {
  "/": { title: "Contest Scout", subtitle: "오늘 시간을 쓸 공모전을 골라 드립니다." },
  "/discover": { title: "공모전 탐색", subtitle: "조건을 좁혀 가며 후보를 찾습니다." },
  "/contests": { title: "전체 공모전", subtitle: "수집된 모든 공모전을 한 표에서 봅니다." },
  "/shortlist": { title: "Shortlist", subtitle: "담아 둔 공모전입니다." },
  "/entering": { title: "참가 중", subtitle: "실제로 준비하고 있는 프로젝트입니다." },
  "/analytics": { title: "Analytics", subtitle: "수집·추천·선택 패턴을 봅니다." },
  "/runs": { title: "Scout 실행 기록", subtitle: "자동 수집이 언제 무엇을 했는지 남깁니다." },
  "/sources": { title: "소스", subtitle: "수집 대상 사이트 상태입니다." },
  "/settings": { title: "설정", subtitle: "수집 방식과 추천 기준을 조정합니다." },
};

const MetaContext = createContext<(meta: PageMeta | null) => void>(() => {});

/** 상세 화면처럼 제목이 데이터에 따라 달라지는 곳에서 쓴다. */
export function usePageMeta(meta: PageMeta | null) {
  const setMeta = useContext(MetaContext);
  const title = meta?.title;
  const subtitle = meta?.subtitle;
  useEffect(() => {
    setMeta(title ? { title, subtitle } : null);
    return () => setMeta(null);
  }, [setMeta, title, subtitle]);
}

export function AppShell() {
  const location = useLocation();
  const { dark, toggle } = useTheme();
  const [navOpen, setNavOpen] = useState(false);
  const [override, setOverride] = useState<PageMeta | null>(null);
  const { data: dashboard } = useDashboard();
  const { data: facets } = useFacets();

  useEffect(() => {
    setNavOpen(false);
  }, [location.pathname]);

  const meta =
    override ??
    ROUTE_META[location.pathname] ??
    (location.pathname.startsWith("/contests/")
      ? { title: "공모전 분석" }
      : { title: "Contest Scout" });

  useEffect(() => {
    document.title = meta.title === "Contest Scout" ? "Contest Scout" : `${meta.title} · Contest Scout`;
  }, [meta.title]);

  const counts = useMemo(
    () => ({
      shortlist: facets?.statuses?.INTERESTED ?? 0,
      entering:
        (facets?.statuses?.ENTERING ?? 0) + (facets?.statuses?.SUBMITTED ?? 0),
      new: dashboard?.kpi.new_today ?? 0,
    }),
    [facets, dashboard],
  );

  return (
    <MetaContext.Provider value={setOverride}>
      <div className="min-h-full">
        <Sidebar counts={counts} open={navOpen} onClose={() => setNavOpen(false)} />
        <div className="lg:pl-[232px]">
          <Topbar
            title={meta.title}
            subtitle={meta.subtitle}
            lastSync={dashboard?.last_run?.finished_at ?? null}
            dark={dark}
            onToggleTheme={toggle}
            onOpenNav={() => setNavOpen(true)}
          />
          <main className="mx-auto max-w-[1440px] px-5 py-6 lg:px-8 lg:py-7">
            <Outlet />
          </main>
        </div>
      </div>
    </MetaContext.Provider>
  );
}
