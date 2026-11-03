import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { CheckCircle2, Loader2, Radar, X, XCircle } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/Toast";
import { cn } from "@/lib/cn";
import { keys, useRunScout, useScoutStatus } from "@/lib/queries";
import type { ScoutState } from "@/lib/types";

const SOURCE_LABEL: Record<string, string> = {
  thinkgood: "씽굿",
  linkareer: "링커리어",
};

const PHASE_DOT: Record<string, string> = {
  pending: "bg-line-strong",
  scanning: "bg-accent dot-live",
  done: "bg-success",
  failed: "bg-danger",
};

const PHASE_TEXT: Record<string, string> = {
  pending: "대기",
  scanning: "수집 중",
  done: "완료",
  failed: "실패",
};

/** 이 버튼은 실제 Python 크롤러를 돌린다. 상태는 서버 폴링으로 받아 그대로 표시한다. */
export function RunScoutButton() {
  const { data: state } = useScoutStatus();
  const runScout = useRunScout();
  const toast = useToast();
  const client = useQueryClient();
  const [open, setOpen] = useState(false);
  const previousPhase = useRef<string | undefined>(undefined);
  const panelRef = useRef<HTMLDivElement>(null);

  const running = state?.phase === "running";

  // 실행이 끝나면 화면 데이터를 새로 읽는다.
  useEffect(() => {
    if (previousPhase.current === "running" && state && state.phase !== "running") {
      void client.invalidateQueries({ queryKey: keys.dashboard });
      void client.invalidateQueries({ queryKey: ["contests"] });
      void client.invalidateQueries({ queryKey: keys.runs });
      void client.invalidateQueries({ queryKey: keys.sources });
      void client.invalidateQueries({ queryKey: keys.analytics });
      void client.invalidateQueries({ queryKey: keys.facets });
      toast({
        tone: state.phase === "failed" ? "error" : "success",
        message: state.phase === "failed" ? "Scout 실행 실패" : "Scout 완료",
        detail: state.message ?? undefined,
      });
    }
    previousPhase.current = state?.phase;
  }, [state, client, toast]);

  useEffect(() => {
    if (running) setOpen(true);
  }, [running]);

  useEffect(() => {
    if (!open) return;
    const onClick = (event: MouseEvent) => {
      if (!panelRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className="relative" ref={panelRef}>
      <Button
        variant="primary"
        onClick={() => {
          if (running) {
            setOpen((value) => !value);
            return;
          }
          runScout.mutate(undefined, {
            onError: (error) =>
              toast({ tone: "error", message: "Scout을 시작하지 못했습니다", detail: String(error) }),
          });
        }}
        loading={runScout.isPending}
      >
        {running ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : (
          <Radar className="h-3.5 w-3.5" />
        )}
        {running ? "수집 중" : "Scout 실행"}
      </Button>

      {open && state && state.phase !== "idle" && (
        <ScoutPanel state={state} onClose={() => setOpen(false)} />
      )}
    </div>
  );
}

function ScoutPanel({ state, onClose }: { state: ScoutState; onClose: () => void }) {
  const sources = Object.entries(state.sources);
  const totalNew = state.new_contests.length;
  const sTier = state.new_contests.filter((item) => item.tier === "S").length;

  return (
    <div className="fade-up absolute right-0 top-11 z-40 w-[334px] rounded-xl border border-line bg-surface p-4 shadow-float">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-[13px] font-semibold text-ink">
            {state.phase === "running"
              ? "Scout 실행 중"
              : state.phase === "failed"
                ? "Scout 실행 실패"
                : "Scout 완료"}
          </p>
          <p className="mt-0.5 text-[12px] text-muted">{state.message ?? "진행 상황을 확인합니다"}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="-mr-1 -mt-1 rounded p-1 text-subtle transition-colors hover:bg-surface-3 hover:text-ink"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      <ul className="mt-3.5 space-y-2 border-t border-line pt-3.5">
        {sources.map(([name, phase]) => {
          const stats = state.source_stats[name];
          return (
            <li key={name} className="flex items-center gap-2.5">
              <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", PHASE_DOT[phase])} />
              <span className="text-[13px] text-ink">{SOURCE_LABEL[name] ?? name}</span>
              <span className="num ml-auto text-[12px] text-subtle">
                {stats
                  ? stats.skipped_reason
                    ? "건너뜀"
                    : `${stats.discovered}건 확인 · 신규 ${stats.new}`
                  : PHASE_TEXT[phase]}
              </span>
            </li>
          );
        })}
      </ul>

      {state.errors.length > 0 && (
        <div className="mt-3 space-y-1.5 rounded-lg bg-danger-soft p-2.5">
          {state.errors.map((error) => (
            <p key={error.source} className="text-[12px] leading-relaxed text-danger">
              <span className="font-semibold">{SOURCE_LABEL[error.source] ?? error.source}</span>{" "}
              — {error.reason}
            </p>
          ))}
        </div>
      )}

      {state.phase !== "running" && (
        <div className="mt-3.5 flex items-center gap-2 border-t border-line pt-3.5">
          {state.phase === "failed" ? (
            <XCircle className="h-4 w-4 shrink-0 text-danger" />
          ) : (
            <CheckCircle2 className="h-4 w-4 shrink-0 text-success" />
          )}
          <p className="num text-[12px] text-muted">
            신규 {totalNew}건 · S등급 {sTier}건
          </p>
          <Link to="/runs" onClick={onClose} className="ml-auto">
            <Button size="sm" variant="ghost">
              실행 기록
            </Button>
          </Link>
        </div>
      )}

      {state.phase === "running" && state.new_contests.length > 0 && (
        <ul className="mt-3 max-h-32 space-y-1 overflow-auto border-t border-line pt-3">
          {state.new_contests.slice(-6).reverse().map((item, index) => (
            <li key={`${item.title}-${index}`} className="flex items-center gap-2">
              <span className="num w-6 shrink-0 text-[11px] font-semibold text-subtle">
                {item.tier}
              </span>
              <span className="line-clamp-1 text-[12px] text-muted">{item.title}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
