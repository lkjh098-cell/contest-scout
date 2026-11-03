import { cn } from "@/lib/cn";
import type { Tier } from "@/lib/types";

const STYLES: Record<Tier, string> = {
  S: "bg-[var(--tier-s-bg)] text-[var(--tier-s-fg)]",
  A: "bg-[var(--tier-a-bg)] text-[var(--tier-a-fg)] border border-[var(--tier-a-line)]",
  B: "bg-[var(--tier-b-bg)] text-[var(--tier-b-fg)] border border-[var(--tier-b-line)]",
  SKIP: "bg-transparent text-subtle border border-line",
};

const SIZES = {
  sm: "h-[18px] min-w-[18px] px-1 text-[10px] rounded-[4px]",
  md: "h-6 min-w-[24px] px-1.5 text-[11px] rounded-[5px]",
  lg: "h-7 min-w-[28px] px-2 text-[12px] rounded-md",
};

export function TierBadge({
  tier,
  size = "md",
  className,
}: {
  tier: Tier | null | undefined;
  size?: keyof typeof SIZES;
  className?: string;
}) {
  const value = tier ?? "SKIP";
  return (
    <span
      className={cn(
        "inline-flex items-center justify-center font-bold tracking-wide",
        STYLES[value],
        SIZES[size],
        className,
      )}
      title={`${value} 등급`}
    >
      {value === "SKIP" ? "—" : value}
    </span>
  );
}

export function ScoreValue({
  score,
  className,
  size = "md",
}: {
  score: number | null | undefined;
  className?: string;
  size?: "sm" | "md" | "lg";
}) {
  if (score === null || score === undefined) {
    return <span className={cn("num text-subtle", className)}>—</span>;
  }
  return (
    <span
      className={cn(
        "num font-semibold tabular-nums text-ink",
        size === "sm" && "text-[13px]",
        size === "md" && "text-sm",
        size === "lg" && "text-[28px] leading-none tracking-[-0.02em]",
        className,
      )}
    >
      {score}
    </span>
  );
}
