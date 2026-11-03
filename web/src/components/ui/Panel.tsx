import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

/** 화면의 기본 구획.
 *
 * 모든 것을 둥근 카드에 넣지 않는다. 표·차트처럼 "한 덩어리"인 것만 감싸고,
 * 나머지는 제목 + 여백으로 구분한다.
 */
export function Panel({
  children,
  className,
  flush,
}: {
  children: ReactNode;
  className?: string;
  flush?: boolean;
}) {
  return (
    <section
      className={cn(
        "rounded-xl border border-line bg-surface shadow-card",
        !flush && "p-5",
        className,
      )}
    >
      {children}
    </section>
  );
}

export function SectionHeader({
  title,
  description,
  action,
  className,
}: {
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex items-end justify-between gap-4", className)}>
      <div className="min-w-0">
        <h2 className="text-[15px] font-semibold tracking-[-0.01em] text-ink">{title}</h2>
        {description && <p className="mt-1 text-[13px] text-muted">{description}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}
