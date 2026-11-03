import { NavLink } from "react-router-dom";
import {
  BarChart3,
  Bookmark,
  Compass,
  LayoutGrid,
  ListFilter,
  Radio,
  Rocket,
  Settings,
  Waypoints,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/cn";

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  countKey?: "shortlist" | "entering" | "new";
}

const PRIMARY: NavItem[] = [
  { to: "/", label: "오늘의 브리핑", icon: LayoutGrid },
  { to: "/discover", label: "공모전 탐색", icon: Compass, countKey: "new" },
  { to: "/contests", label: "전체 공모전", icon: ListFilter },
  { to: "/shortlist", label: "Shortlist", icon: Bookmark, countKey: "shortlist" },
  { to: "/entering", label: "참가 중", icon: Rocket, countKey: "entering" },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
];

const SECONDARY: NavItem[] = [
  { to: "/runs", label: "Scout 실행 기록", icon: Waypoints },
  { to: "/sources", label: "소스", icon: Radio },
  { to: "/settings", label: "설정", icon: Settings },
];

export function Sidebar({
  counts,
  open,
  onClose,
}: {
  counts: Partial<Record<"shortlist" | "entering" | "new", number>>;
  open: boolean;
  onClose: () => void;
}) {
  return (
    <>
      {open && (
        <div
          className="fixed inset-0 z-30 bg-black/30 backdrop-blur-[1px] lg:hidden"
          onClick={onClose}
        />
      )}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-[232px] flex-col border-r border-line bg-rail",
          "transition-transform duration-200 lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex h-14 items-center gap-2.5 px-5">
          <BrandMark />
          <div className="min-w-0">
            <p className="truncate text-[13.5px] font-semibold tracking-[-0.01em] text-ink">
              Contest Scout
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="ml-auto rounded p-1 text-subtle hover:text-ink lg:hidden"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <nav className="flex grow flex-col gap-0.5 overflow-y-auto px-3 pb-4">
          {PRIMARY.map((item) => (
            <SidebarLink key={item.to} item={item} counts={counts} onNavigate={onClose} />
          ))}

          <div className="my-3 border-t border-line" />

          {SECONDARY.map((item) => (
            <SidebarLink key={item.to} item={item} counts={counts} onNavigate={onClose} />
          ))}
        </nav>

        <div className="border-t border-line px-5 py-3">
          <p className="text-[11px] leading-relaxed text-subtle">
            내 시간을 쓸 가치가 있는
            <br />
            공모전만 골라 드립니다.
          </p>
        </div>
      </aside>
    </>
  );
}

function SidebarLink({
  item,
  counts,
  onNavigate,
}: {
  item: NavItem;
  counts: Partial<Record<string, number>>;
  onNavigate: () => void;
}) {
  const count = item.countKey ? counts[item.countKey] : undefined;
  return (
    <NavLink
      to={item.to}
      // 상세 화면(/contests/:key)에서 목록 메뉴가 켜지지 않도록 정확히 일치할 때만.
      end
      onClick={onNavigate}
      className={({ isActive }) =>
        cn(
          "group flex items-center gap-2.5 rounded-lg px-2.5 py-[7px] text-[13px] transition-colors",
          isActive
            ? "bg-surface text-ink shadow-card font-medium"
            : "text-muted hover:bg-surface/60 hover:text-ink",
        )
      }
    >
      <item.icon className="h-[15px] w-[15px] shrink-0" strokeWidth={1.8} />
      <span className="truncate">{item.label}</span>
      {count !== undefined && count > 0 && (
        <span className="num ml-auto rounded bg-surface-3 px-1.5 py-px text-[11px] font-medium text-muted">
          {count}
        </span>
      )}
    </NavLink>
  );
}

function BrandMark() {
  return (
    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-[7px] bg-ink">
      <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none">
        <path
          d="M6 17V7h3.7c2.2 0 3.6 1.2 3.6 3.1 0 1.4-.7 2.4-2 2.8l2.4 4.1h-2.2l-2.1-3.7H8V17H6zm2-5.3h1.6c1 0 1.6-.5 1.6-1.4S10.6 8.9 9.6 8.9H8v2.8z"
          fill="var(--tier-s-fg)"
        />
        <circle cx="17" cy="15.5" r="3" stroke="var(--tier-s-fg)" strokeWidth="1.5" />
      </svg>
    </span>
  );
}
