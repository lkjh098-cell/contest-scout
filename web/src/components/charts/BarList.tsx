import { cn } from "@/lib/cn";

/** 막대 표. 카테고리 분포처럼 "순위 + 비중" 이 핵심인 데이터는 파이보다 이게 빠르다. */
export function BarList({
  items,
  total,
  valueFormat,
  className,
  tone = "ink",
}: {
  items: { name: string; count: number }[];
  total?: number;
  valueFormat?: (value: number) => string;
  className?: string;
  tone?: "ink" | "accent";
}) {
  const max = total ?? Math.max(1, ...items.map((item) => item.count));
  if (!items.length) {
    return <p className="py-8 text-center text-[13px] text-subtle">데이터가 아직 없습니다.</p>;
  }
  return (
    <ul className={cn("space-y-2.5", className)}>
      {items.map((item) => (
        <li key={item.name}>
          <div className="flex items-baseline justify-between gap-3">
            <span className="truncate text-[13px] text-ink">{item.name}</span>
            <span className="num shrink-0 text-[13px] font-medium text-muted">
              {valueFormat ? valueFormat(item.count) : item.count}
            </span>
          </div>
          <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-surface-3">
            <div
              className={cn(
                "h-full rounded-full transition-[width] duration-700 ease-out",
                tone === "ink" ? "bg-ink" : "bg-accent",
              )}
              style={{ width: `${Math.max(2, (item.count / max) * 100)}%` }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}

export function StatBlock({
  label,
  value,
  sub,
  tone,
  className,
}: {
  label: string;
  value: string | number;
  sub?: string;
  tone?: "up" | "down";
  className?: string;
}) {
  return (
    <div className={cn(className)}>
      <p className="label-xs">{label}</p>
      <p className="num mt-1.5 text-[26px] font-semibold leading-none tracking-[-0.03em] text-ink">
        {value}
      </p>
      {sub && (
        <p
          className={cn(
            "num mt-1.5 text-[12px]",
            tone === "up" && "text-success",
            tone === "down" && "text-danger",
            !tone && "text-subtle",
          )}
        >
          {sub}
        </p>
      )}
    </div>
  );
}
