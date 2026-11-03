import { useState, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  ChevronDown,
  Clock3,
  ExternalLink,
  Lightbulb,
  Sparkles,
  TriangleAlert,
} from "lucide-react";

import { DeadlinePill, SourceMark } from "@/components/contest/Bits";
import { StatusActions } from "@/components/contest/StatusActions";
import { TierBadge } from "@/components/contest/TierBadge";
import { usePageMeta } from "@/components/layout/AppShell";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Panel, SectionHeader } from "@/components/ui/Panel";
import { Skeleton, SkeletonText } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/States";
import { cn } from "@/lib/cn";
import { formatDate, formatPrizeFull, relativeTime, STATUS_LABEL, VERDICT } from "@/lib/format";
import { useContest, useSettings } from "@/lib/queries";

const FALLBACK_LABELS: Record<string, string> = {
  award_value: "상금·수상가치",
  skill_fit: "현재 제작역량 적합성",
  feasibility: "남은 기간 대비 제작 가능성",
  win_probability: "예상 경쟁강도 대비 수상 가능성",
  idea_headroom: "아이디어 차별화 여지",
  workflow_reuse: "AI 활용 / workflow 재활용성",
  solo_friendly: "혼자 제작 가능 여부",
  portfolio_value: "포트폴리오 가치",
  organizer_trust: "주최기관·공모전 신뢰도",
};

const FALLBACK_WEIGHTS: Record<string, number> = {
  award_value: 20,
  skill_fit: 20,
  feasibility: 15,
  win_probability: 15,
  idea_headroom: 10,
  workflow_reuse: 5,
  solo_friendly: 5,
  portfolio_value: 5,
  organizer_trust: 5,
};

export function ContestDetail() {
  const { key } = useParams();
  const navigate = useNavigate();
  const { data, isLoading, error, refetch } = useContest(key);
  const { data: settings } = useSettings();
  const [showRaw, setShowRaw] = useState(false);

  usePageMeta(data ? { title: data.title } : null);

  if (error) return <ErrorState error={error} onRetry={() => void refetch()} />;
  if (isLoading || !data) return <DetailSkeleton />;

  const score = data.score;
  const tier = score?.tier ?? "SKIP";
  const verdict = VERDICT[tier];
  const labels = settings?.part_labels ?? FALLBACK_LABELS;
  const weights = settings?.profile.weights ?? FALLBACK_WEIGHTS;
  const partOrder = Object.keys(weights);

  return (
    <div className="space-y-6">
      <button
        type="button"
        onClick={() => navigate(-1)}
        className="inline-flex items-center gap-1.5 text-[13px] text-muted transition-colors hover:text-ink"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        뒤로
      </button>

      {/* 헤더 */}
      <header className="border-b border-line pb-6">
        <div className="flex flex-wrap items-center gap-2.5">
          <TierBadge tier={tier} size="lg" />
          <span className="num text-[13px] font-medium text-muted">
            점수 <span className="text-ink">{score?.total ?? "—"}</span> / 100
          </span>
          <Badge tone="outline">{STATUS_LABEL[data.status] ?? data.status}</Badge>
          {data.is_new_today && <Badge tone="accent">오늘 발견</Badge>}
        </div>

        <h1 className="mt-3 text-[27px] font-semibold leading-[1.25] tracking-[-0.025em] text-ink">
          {data.title}
        </h1>

        <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[13.5px] text-muted">
          <span className="font-medium text-ink">{data.organizer ?? "주최기관 미확인"}</span>
          {data.organizer_type && <span>{data.organizer_type}</span>}
          <span className="text-line-strong">·</span>
          <SourceMark source={data.source} sources={data.duplicate_sources} />
        </div>

        {(data.tags.length > 0 || data.categories.length > 0) && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {data.tags.map((tag) => (
              <Link
                key={tag}
                to={`/discover?tag=${encodeURIComponent(tag)}`}
                className="rounded-md border border-line px-2 py-0.5 text-[12px] text-muted transition-colors hover:border-line-strong hover:text-ink"
              >
                {tag}
              </Link>
            ))}
          </div>
        )}

        <dl className="mt-6 grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4">
          <div>
            <dt className="label-xs">최고 상금</dt>
            <dd className="num mt-1 text-[17px] font-semibold tracking-[-0.015em] text-ink">
              {formatPrizeFull(data.best_prize_krw)}
            </dd>
          </div>
          <div>
            <dt className="label-xs">접수 마감</dt>
            <dd className="mt-1 flex items-baseline gap-2">
              <span className="text-[17px] font-semibold tracking-[-0.015em] text-ink">
                {formatDate(data.deadline)}
              </span>
              <DeadlinePill days={data.days_left} />
            </dd>
          </div>
          <div>
            <dt className="label-xs">참가 자격</dt>
            <dd className="mt-1 line-clamp-2 text-[13.5px] text-ink">
              {data.eligibility.length ? data.eligibility.join(", ") : "공고 확인 필요"}
            </dd>
          </div>
          <div>
            <dt className="label-xs">예상 작업량</dt>
            <dd className="mt-1 text-[13.5px] text-ink">
              {score?.estimated_workdays ?? "산정 불가"}
            </dd>
          </div>
        </dl>

        <div className="mt-6 flex flex-wrap items-center gap-2">
          <a href={data.url} target="_blank" rel="noreferrer noopener">
            <Button variant="secondary">
              공식 공고
              <ExternalLink className="h-3.5 w-3.5" />
            </Button>
          </a>
          {data.homepage && data.homepage !== data.url && (
            <a href={data.homepage} target="_blank" rel="noreferrer noopener">
              <Button variant="ghost">주최 홈페이지</Button>
            </a>
          )}
          <div className="ml-auto">
            <StatusActions contest={data} size="md" />
          </div>
        </div>
      </header>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-5">
          {/* 점수 구성 */}
          <Panel>
            <SectionHeader
              title="점수 구성"
              description={`규칙 기반 평가 · ${
                score?.updated_at ? relativeTime(score.updated_at) + " 채점" : "채점 기록 없음"
              }`}
            />
            {score ? (
              <div className="mt-5 space-y-3.5">
                {partOrder.map((partKey) => {
                  const value = score.parts[partKey] ?? 0;
                  const max = weights[partKey] ?? 0;
                  if (!max) return null;
                  const ratio = value / max;
                  return (
                    <div key={partKey}>
                      <div className="flex items-baseline justify-between gap-3">
                        <span className="text-[13px] text-ink">{labels[partKey] ?? partKey}</span>
                        <span className="num shrink-0 text-[13px] font-semibold text-ink">
                          {value}
                          <span className="font-normal text-subtle"> / {max}</span>
                        </span>
                      </div>
                      <div className="mt-1.5 h-[5px] overflow-hidden rounded-full bg-surface-3">
                        <div
                          className={cn(
                            "h-full rounded-full transition-[width] duration-700 ease-out",
                            ratio >= 0.85 ? "bg-ink" : ratio >= 0.5 ? "bg-muted" : "bg-line-strong",
                          )}
                          style={{ width: `${Math.max(2, ratio * 100)}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="mt-4 text-[13px] text-subtle">
                아직 채점되지 않았습니다. Scout을 한 번 실행하면 점수가 매겨집니다.
              </p>
            )}
          </Panel>

          {/* 공고 원문 */}
          {data.detail_text && (
            <Panel>
              <button
                type="button"
                onClick={() => setShowRaw((value) => !value)}
                className="flex w-full items-center justify-between gap-3 text-left"
              >
                <SectionHeader title="공고 원문" description="수집한 요강을 그대로 보여 줍니다." />
                <ChevronDown
                  className={cn(
                    "h-4 w-4 shrink-0 text-subtle transition-transform",
                    showRaw && "rotate-180",
                  )}
                />
              </button>
              {showRaw && (
                <pre className="mt-4 max-h-[420px] overflow-auto whitespace-pre-wrap border-t border-line pt-4 text-[13px] leading-[1.75] text-muted">
                  {data.detail_text}
                </pre>
              )}
            </Panel>
          )}
        </div>

        <div className="space-y-5">
          {/* Scout 판단 */}
          <Panel>
            <SectionHeader title="Scout 판단" />
            <p className="mt-3 text-[15px] font-semibold tracking-[-0.01em] text-ink">
              {verdict.title}
            </p>
            <p className="mt-1 text-[13px] leading-relaxed text-muted">{verdict.note}</p>

            {score?.reasons.length ? (
              <div className="mt-5">
                <p className="label-xs mb-2 flex items-center gap-1.5">
                  <Sparkles className="h-3 w-3" />왜 나갈 만한가
                </p>
                <ul className="space-y-1.5">
                  {score.reasons.map((reason) => (
                    <li key={reason} className="flex gap-2 text-[13px] leading-relaxed text-ink">
                      <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-success" />
                      {reason}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {score?.risks.length ? (
              <div className="mt-5">
                <p className="label-xs mb-2 flex items-center gap-1.5">
                  <TriangleAlert className="h-3 w-3" />확인할 점
                </p>
                <ul className="space-y-1.5">
                  {score.risks.map((risk) => (
                    <li key={risk} className="flex gap-2 text-[13px] leading-relaxed text-ink">
                      <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-warn" />
                      {risk}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            <div className="mt-5 flex items-center gap-2 border-t border-line pt-4 text-[13px] text-muted">
              <Clock3 className="h-3.5 w-3.5 shrink-0" />
              예상 작업량 {score?.estimated_workdays ?? "산정 불가"}
            </div>
          </Panel>

          {/* 아이디어 방향 — 아직 AI 평가기가 없으므로 상태를 있는 그대로 알린다 */}
          <Panel>
            <SectionHeader title="초기 아이디어 방향" />
            {score?.idea_seeds.length ? (
              <ol className="mt-4 space-y-3">
                {score.idea_seeds.map((seed, index) => (
                  <li key={seed} className="flex gap-3">
                    <span className="num text-[12px] font-semibold text-subtle">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <span className="text-[13px] leading-relaxed text-ink">{seed}</span>
                  </li>
                ))}
              </ol>
            ) : (
              <div className="mt-3 flex gap-2.5 rounded-lg bg-surface-2 p-3">
                <Lightbulb className="mt-0.5 h-4 w-4 shrink-0 text-subtle" />
                <p className="text-[12.5px] leading-relaxed text-muted">
                  분석 준비 중입니다. 아이디어 방향 제시는 AI 평가기(Phase 2)가 붙은 뒤에
                  제공됩니다. 지금은 규칙 기반 점수만 신뢰할 수 있습니다.
                </p>
              </div>
            )}
          </Panel>

          {/* 수집 정보 */}
          <Panel>
            <SectionHeader title="수집 정보" />
            <dl className="mt-3 space-y-2.5 text-[12.5px]">
              <Row label="공모전 키" value={<code className="text-[11.5px]">{data.key}</code>} />
              <Row label="처음 발견" value={relativeTime(data.first_seen)} />
              <Row label="마지막 확인" value={relativeTime(data.last_seen)} />
              <Row label="접수 시작" value={formatDate(data.start_date)} />
              {data.prize_text && <Row label="상금 원문" value={data.prize_text} />}
            </dl>
            {data.history.length > 0 && (
              <div className="mt-4 border-t border-line pt-3">
                <p className="label-xs mb-2">상태 변경 이력</p>
                <ul className="space-y-1.5">
                  {data.history.slice(0, 5).map((event, index) => (
                    <li key={index} className="flex items-center gap-2 text-[12px] text-muted">
                      <span className="num text-subtle">{relativeTime(event.created_at)}</span>
                      <span>
                        {STATUS_LABEL[event.from_status ?? ""] ?? event.from_status ?? "—"} →{" "}
                        <span className="text-ink">
                          {STATUS_LABEL[event.to_status] ?? event.to_status}
                        </span>
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="shrink-0 text-subtle">{label}</dt>
      <dd className="min-w-0 truncate text-right text-ink">{value}</dd>
    </div>
  );
}

function DetailSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-3.5 w-12" />
      <div className="border-b border-line pb-6">
        <Skeleton className="h-6 w-24" />
        <Skeleton className="mt-4 h-7 w-3/4" />
        <Skeleton className="mt-3 h-4 w-1/3" />
        <div className="mt-6 grid grid-cols-2 gap-6 sm:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={index}>
              <Skeleton className="h-3 w-16" />
              <Skeleton className="mt-2 h-5 w-24" />
            </div>
          ))}
        </div>
      </div>
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="rounded-xl border border-line bg-surface p-5">
          <SkeletonText lines={8} />
        </div>
        <div className="rounded-xl border border-line bg-surface p-5">
          <SkeletonText lines={5} />
        </div>
      </div>
    </div>
  );
}
