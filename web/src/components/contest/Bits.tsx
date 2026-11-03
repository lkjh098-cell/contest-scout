import { Link } from "react-router-dom";

import { cn } from "@/lib/cn";
import { deadlineTone, formatDday, formatPrize } from "@/lib/format";

export function DeadlinePill({
  days,
  className,
  showLabel = true,
}: {
  days: number | null | undefined;
  className?: string;
  showLabel?: boolean;
}) {
  const tone = deadlineTone(days);
  return (
    <span
      className={cn(
        "num inline-flex items-center rounded-md px-1.5 py-0.5 text-[12px] font-semibold",
        tone === "danger" && "bg-danger-soft text-danger",
        tone === "warn" && "bg-warn-soft text-warn",
        tone === "normal" && "text-muted",
        tone === "none" && "text-subtle",
        className,
      )}
    >
      {showLabel ? formatDday(days) : days}
    </span>
  );
}

export function PrizeText({
  value,
  className,
}: {
  value: number | null | undefined;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "num text-[13px]",
        value ? "font-medium text-ink" : "text-subtle",
        className,
      )}
    >
      {formatPrize(value)}
    </span>
  );
}

export function TagList({
  tags,
  max = 3,
  className,
}: {
  tags: string[];
  max?: number;
  className?: string;
}) {
  if (!tags.length) return null;
  const shown = tags.slice(0, max);
  const rest = tags.length - shown.length;
  return (
    <div className={cn("flex flex-wrap items-center gap-1", className)}>
      {shown.map((tag) => (
        <Link
          key={tag}
          to={`/discover?tag=${encodeURIComponent(tag)}`}
          onClick={(event) => event.stopPropagation()}
          className="rounded border border-line px-1.5 py-px text-[11px] text-muted transition-colors hover:border-line-strong hover:text-ink"
        >
          {tag}
        </Link>
      ))}
      {rest > 0 && <span className="num text-[11px] text-subtle">+{rest}</span>}
    </div>
  );
}

const SOURCE_LABEL: Record<string, string> = {
  thinkgood: "씽굿",
  linkareer: "링커리어",
};

/** 같은 공모전이 두 사이트에 올라온 경우 소스를 함께 적는다. 목록에서는 한 줄로
 *  접어 보여 주므로, 어디서 왔는지는 여기서 알린다. */
export function SourceMark({
  source,
  sources,
  className,
}: {
  source: string;
  sources?: string[];
  className?: string;
}) {
  const list = sources && sources.length > 1 ? sources : [source];
  return (
    <span
      className={cn("text-[11px] tracking-wide text-subtle", className)}
      title={list.length > 1 ? "여러 사이트에 올라온 같은 공모전입니다" : undefined}
    >
      {list.map((name) => SOURCE_LABEL[name] ?? name).join(" · ")}
    </span>
  );
}
