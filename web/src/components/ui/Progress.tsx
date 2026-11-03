import { cn } from "@/lib/cn";

export function Progress({
  value,
  max = 100,
  className,
  tone = "accent",
}: {
  value: number;
  max?: number;
  className?: string;
  tone?: "accent" | "ink" | "success";
}) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div className={cn("h-1.5 w-full overflow-hidden rounded-full bg-surface-3", className)}>
      <div
        className={cn(
          "h-full rounded-full transition-[width] duration-500 ease-out",
          tone === "accent" && "bg-accent",
          tone === "ink" && "bg-ink",
          tone === "success" && "bg-success",
        )}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

/** 점수 항목용 눈금 막대. 20칸을 채우는 방식이라 값을 세지 않고도 비교된다. */
export function ScoreMeter({
  value,
  max,
  className,
}: {
  value: number;
  max: number;
  className?: string;
}) {
  const cells = 20;
  const filled = Math.round((value / max) * cells);
  return (
    <div className={cn("flex gap-[3px]", className)} aria-hidden>
      {Array.from({ length: cells }).map((_, index) => (
        <span
          key={index}
          className={cn(
            "h-2 flex-1 rounded-[1px] transition-colors",
            index < filled ? "bg-ink" : "bg-surface-3",
          )}
        />
      ))}
    </div>
  );
}
