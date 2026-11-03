import type { ReactNode } from "react";
import { useState } from "react";
import { AlertTriangle, ChevronDown } from "lucide-react";

import { ApiError } from "@/lib/api";
import { cn } from "@/lib/cn";
import { Button } from "./Button";

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: {
  icon?: ReactNode;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center px-6 py-16 text-center",
        className,
      )}
    >
      {icon && (
        <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-surface-3 text-subtle">
          {icon}
        </div>
      )}
      <p className="text-[15px] font-semibold text-ink">{title}</p>
      {description && (
        <div className="mt-1.5 max-w-md text-sm leading-relaxed text-muted">{description}</div>
      )}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

/** 실패 원인을 사람 말로 먼저 보여주고, traceback은 접어 둔다. */
export function ErrorState({
  error,
  onRetry,
  className,
}: {
  error: unknown;
  onRetry?: () => void;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const apiError = error instanceof ApiError ? error : null;
  const message =
    apiError?.message ??
    (error instanceof Error ? error.message : "알 수 없는 오류가 발생했습니다.");
  const technical = apiError?.technical;

  return (
    <div
      className={cn(
        "rounded-xl border border-line bg-surface p-5",
        className,
      )}
    >
      <div className="flex gap-3">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-danger" />
        <div className="min-w-0 grow">
          <p className="text-sm font-semibold text-ink">{message}</p>
          {apiError?.status === 0 && (
            <p className="mt-1 text-[13px] text-muted">
              터미널에서 <code className="rounded bg-surface-3 px-1 py-0.5">./start.sh</code> 가
              실행 중인지 확인해 주세요.
            </p>
          )}
          <div className="mt-3 flex items-center gap-2">
            {onRetry && (
              <Button size="sm" onClick={onRetry}>
                다시 시도
              </Button>
            )}
            {technical && (
              <button
                type="button"
                onClick={() => setOpen((value) => !value)}
                className="inline-flex items-center gap-1 text-[13px] text-subtle transition-colors hover:text-muted"
              >
                기술 정보 보기
                <ChevronDown
                  className={cn("h-3 w-3 transition-transform", open && "rotate-180")}
                />
              </button>
            )}
          </div>
          {open && technical && (
            <pre className="mt-3 max-h-48 overflow-auto rounded-lg bg-surface-3 p-3 text-[11px] leading-relaxed text-muted">
              {technical}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}
