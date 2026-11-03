import { Menu, Moon, Sun } from "lucide-react";
import type { ReactNode } from "react";

import { RunScoutButton } from "@/components/scout/RunScoutButton";
import { Button } from "@/components/ui/Button";
import { relativeTime } from "@/lib/format";

export function Topbar({
  title,
  subtitle,
  lastSync,
  dark,
  onToggleTheme,
  onOpenNav,
  action,
}: {
  title: string;
  subtitle?: ReactNode;
  lastSync?: string | null;
  dark: boolean;
  onToggleTheme: () => void;
  onOpenNav: () => void;
  action?: ReactNode;
}) {
  return (
    <header className="sticky top-0 z-20 border-b border-line bg-bg/85 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-[1440px] items-center gap-3 px-5 lg:px-8">
        <button
          type="button"
          onClick={onOpenNav}
          className="-ml-1 rounded-lg p-1.5 text-muted transition-colors hover:bg-surface-3 hover:text-ink lg:hidden"
        >
          <Menu className="h-4 w-4" />
        </button>

        <div className="min-w-0">
          <h1 className="truncate text-[15px] font-semibold tracking-[-0.015em] text-ink">
            {title}
          </h1>
          {subtitle && (
            <p className="truncate text-[12.5px] leading-tight text-muted">{subtitle}</p>
          )}
        </div>

        <div className="ml-auto flex items-center gap-2.5">
          {lastSync !== undefined && (
            <span className="hidden text-[12px] text-subtle sm:inline">
              마지막 수집 {relativeTime(lastSync)}
            </span>
          )}
          <Button
            variant="ghost"
            size="icon"
            onClick={onToggleTheme}
            title={dark ? "라이트 모드" : "다크 모드"}
          >
            {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </Button>
          {action ?? <RunScoutButton />}
        </div>
      </div>
    </header>
  );
}
