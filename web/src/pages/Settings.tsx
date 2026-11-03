import { useEffect, useMemo, useState } from "react";
import { AlertCircle, RotateCcw, Save } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Checkbox, Field, Input, Toggle } from "@/components/ui/Form";
import { Panel, SectionHeader } from "@/components/ui/Panel";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { cn } from "@/lib/cn";
import { useSaveSettings, useSettings } from "@/lib/queries";
import type { Settings } from "@/lib/types";

const SOURCE_LABEL: Record<string, string> = { thinkgood: "씽굿", linkareer: "링커리어" };

export function SettingsPage() {
  const { data, isLoading, error, refetch } = useSettings();

  if (error) return <ErrorState error={error} onRetry={() => void refetch()} />;
  if (isLoading || !data) {
    return (
      <div className="space-y-5">
        {Array.from({ length: 3 }).map((_, index) => (
          <div key={index} className="rounded-xl border border-line bg-surface p-5">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="mt-5 h-9 w-full" />
            <Skeleton className="mt-3 h-9 w-2/3" />
          </div>
        ))}
      </div>
    );
  }

  return <SettingsForm settings={data} />;
}

function SettingsForm({ settings }: { settings: Settings }) {
  const save = useSaveSettings();
  const toast = useToast();

  const [delay, setDelay] = useState(String(settings.crawl.delay));
  const [pages, setPages] = useState(String(settings.crawl.pages));
  const [timeout, setTimeoutValue] = useState(String(settings.crawl.timeout));
  const [respectRobots, setRespectRobots] = useState(settings.crawl.respect_robots);
  const [sources, setSources] = useState(settings.enabled_sources);
  const [scheduleOn, setScheduleOn] = useState(settings.schedule.enabled);
  const [scheduleTime, setScheduleTime] = useState(settings.schedule.time);
  const [weights, setWeights] = useState(settings.profile.weights);

  useEffect(() => {
    setWeights(settings.profile.weights);
  }, [settings.profile.weights]);

  const weightTotal = useMemo(
    () => Object.values(weights).reduce((sum, value) => sum + Number(value || 0), 0),
    [weights],
  );
  const weightsChanged = useMemo(
    () => JSON.stringify(weights) !== JSON.stringify(settings.profile.weights),
    [weights, settings.profile.weights],
  );

  const submit = () => {
    if (weightsChanged && weightTotal !== 100) {
      toast({ tone: "error", message: `배점 합계가 ${weightTotal}점입니다`, detail: "100점이 되어야 저장할 수 있습니다." });
      return;
    }
    save.mutate(
      {
        crawl: {
          delay: Number(delay),
          pages: Number(pages),
          timeout: Number(timeout),
          respect_robots: respectRobots,
        },
        schedule: { enabled: scheduleOn, time: scheduleTime },
        enabled_sources: sources,
        ...(weightsChanged ? { profile: { weights } } : {}),
      },
      {
        onSuccess: (next) =>
          toast({
            tone: "success",
            message: "설정을 저장했습니다",
            detail: next.rescored ? `공모전 ${next.rescored}건을 다시 채점했습니다.` : undefined,
          }),
        onError: (error) =>
          toast({ tone: "error", message: "저장하지 못했습니다", detail: String(error) }),
      },
    );
  };

  return (
    <div className="max-w-[860px] space-y-5">
      {/* 자동 실행 */}
      <Panel>
        <SectionHeader
          title="자동 Scout"
          description="정해진 시각에 수집을 자동으로 실행합니다."
        />
        <div className="mt-5 flex flex-wrap items-center gap-5">
          <label className="flex items-center gap-3">
            <Toggle checked={scheduleOn} onChange={setScheduleOn} />
            <span className="text-[13px] font-medium text-ink">
              {scheduleOn ? "켜짐" : "꺼짐"}
            </span>
          </label>
          <Field label="실행 시각" className="w-[132px]">
            <Input
              type="time"
              value={scheduleTime}
              onChange={(event) => setScheduleTime(event.target.value)}
              disabled={!scheduleOn}
            />
          </Field>
        </div>
        <div className="mt-4 flex gap-2.5 rounded-lg bg-surface-2 p-3">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-subtle" />
          <p className="text-[12.5px] leading-relaxed text-muted">
            스케줄러는 <strong className="font-medium text-ink">백엔드 서버가 켜져 있는 동안에만</strong>{" "}
            동작합니다. 맥을 껐다 켜면 <code className="rounded bg-surface-3 px-1">./start.sh</code> 를 다시
            실행해야 합니다. 서버와 무관하게 매일 돌리려면 launchd/cron에{" "}
            <code className="rounded bg-surface-3 px-1">contest-scout crawl</code> 을 걸어 두세요.
            {settings.scheduler.thread_alive ? " (현재 스케줄러 스레드 동작 중)" : ""}
          </p>
        </div>
      </Panel>

      {/* 수집 */}
      <Panel>
        <SectionHeader title="수집" description="사이트에 부담을 주지 않는 선에서 조정하세요." />
        <div className="mt-5 grid gap-4 sm:grid-cols-3">
          <Field label="요청 간격 (초)" hint="낮출수록 빠르지만 예의에 어긋납니다.">
            <Input
              type="number"
              min={0.5}
              max={30}
              step={0.5}
              value={delay}
              onChange={(event) => setDelay(event.target.value)}
            />
          </Field>
          <Field label="목록 페이지 수" hint="많이 볼수록 과거 공모전까지 훑습니다.">
            <Input
              type="number"
              min={1}
              max={10}
              value={pages}
              onChange={(event) => setPages(event.target.value)}
            />
          </Field>
          <Field label="타임아웃 (초)">
            <Input
              type="number"
              min={5}
              max={120}
              value={timeout}
              onChange={(event) => setTimeoutValue(event.target.value)}
            />
          </Field>
        </div>

        <div className="mt-5 space-y-3 border-t border-line pt-4">
          <label className="flex items-start gap-3">
            <Toggle checked={respectRobots} onChange={setRespectRobots} />
            <span>
              <span className="block text-[13px] font-medium text-ink">robots.txt 준수</span>
              <span className="mt-0.5 block text-[12.5px] text-muted">
                끄지 않는 것을 권합니다. 사이트 정책을 직접 확인한 경우에만 해제하세요.
              </span>
            </span>
          </label>

          <div className="flex items-start gap-3 opacity-70">
            <Toggle checked disabled onChange={() => {}} />
            <span>
              <span className="block text-[13px] font-medium text-ink">
                신규 공모전만 상세 조회
              </span>
              <span className="mt-0.5 block text-[12.5px] text-muted">
                엔진의 기본 동작이라 끌 수 없습니다. 이미 아는 공모전은 상세 요청을 보내지 않습니다.
              </span>
            </span>
          </div>
        </div>

        <div className="mt-5 border-t border-line pt-4">
          <p className="label-xs mb-2">수집 대상</p>
          <div className="-mx-1.5 max-w-[280px]">
            {settings.available_sources.map((source) => (
              <Checkbox
                key={source.name}
                checked={sources.includes(source.name)}
                onChange={(checked) =>
                  setSources((current) =>
                    checked
                      ? [...current, source.name]
                      : current.filter((name) => name !== source.name),
                  )
                }
                label={SOURCE_LABEL[source.name] ?? source.name}
              />
            ))}
          </div>
        </div>
      </Panel>

      {/* 추천 배점 */}
      <Panel>
        <SectionHeader
          title="추천 배점"
          description="합계가 100점이어야 저장됩니다. 저장하면 전체 공모전을 다시 채점합니다."
          action={
            weightsChanged ? (
              <Button size="sm" variant="ghost" onClick={() => setWeights(settings.profile.weights)}>
                <RotateCcw className="h-3.5 w-3.5" />
                되돌리기
              </Button>
            ) : undefined
          }
        />
        <div className="mt-5 space-y-3">
          {Object.entries(weights).map(([key, value]) => (
            <div key={key} className="flex items-center gap-4">
              <span className="w-[210px] shrink-0 text-[13px] text-ink">
                {settings.part_labels[key] ?? key}
              </span>
              <input
                type="range"
                min={0}
                max={30}
                value={value}
                onChange={(event) =>
                  setWeights((current) => ({ ...current, [key]: Number(event.target.value) }))
                }
                className="h-1 grow cursor-pointer appearance-none rounded-full bg-surface-3 accent-[var(--accent)]"
              />
              <input
                type="number"
                min={0}
                max={30}
                value={value}
                onChange={(event) =>
                  setWeights((current) => ({ ...current, [key]: Number(event.target.value) }))
                }
                className="num h-8 w-14 rounded-lg border border-line bg-surface px-2 text-right text-[13px] text-ink focus:border-accent focus:outline-none"
              />
            </div>
          ))}
        </div>
        <div
          className={cn(
            "mt-5 flex items-center justify-between border-t border-line pt-4 text-[13px]",
            weightTotal === 100 ? "text-muted" : "text-danger",
          )}
        >
          <span>배점 합계</span>
          <span className="num font-semibold">{weightTotal} / 100</span>
        </div>
      </Panel>

      {/* 선호 분야 */}
      <Panel>
        <SectionHeader
          title="선호 분야 키워드"
          description="점수 계산이 실제로 참고하는 값입니다. config/profile.json 에서 편집합니다."
        />
        <div className="mt-5 space-y-4">
          <KeywordRow label="핵심 강점" tone="accent" items={settings.profile.strong_keywords} />
          <KeywordRow label="관심 분야" items={settings.profile.preferred_keywords} />
          <KeywordRow label="관심 밖" tone="danger" items={settings.profile.negative_keywords} />
        </div>
        <p className="mt-5 border-t border-line pt-4 text-[12.5px] leading-relaxed text-subtle">
          키워드 편집 UI는 아직 없습니다. 지금은{" "}
          <code className="rounded bg-surface-3 px-1">{settings.paths.profile}</code> 파일을 직접
          고치면 CLI와 대시보드 양쪽에 바로 반영됩니다.
        </p>
      </Panel>

      {/* 저장 위치 */}
      <Panel>
        <SectionHeader title="파일 위치" />
        <dl className="mt-4 space-y-2 text-[12.5px]">
          {Object.entries(settings.paths).map(([key, value]) => (
            <div key={key} className="flex items-baseline justify-between gap-3">
              <dt className="shrink-0 text-subtle">{key}</dt>
              <dd className="truncate text-right">
                <code className="text-[11.5px] text-ink">{value}</code>
              </dd>
            </div>
          ))}
        </dl>
      </Panel>

      <div className="sticky bottom-4 flex items-center justify-end gap-3 rounded-xl border border-line bg-surface/90 px-4 py-3 shadow-pop backdrop-blur">
        {weightsChanged && weightTotal !== 100 && (
          <span className="text-[12.5px] text-danger">배점 합계를 100으로 맞춰 주세요.</span>
        )}
        <Button variant="primary" onClick={submit} loading={save.isPending}>
          <Save className="h-3.5 w-3.5" />
          설정 저장
        </Button>
      </div>
    </div>
  );
}

function KeywordRow({
  label,
  items,
  tone,
}: {
  label: string;
  items: string[];
  tone?: "accent" | "danger";
}) {
  return (
    <div>
      <p className="label-xs mb-2">{label}</p>
      <div className="flex flex-wrap gap-1.5">
        {items.map((item) => (
          <span
            key={item}
            className={cn(
              "rounded-md px-2 py-0.5 text-[12px]",
              tone === "accent" && "bg-accent-soft text-accent",
              tone === "danger" && "bg-danger-soft text-danger",
              !tone && "bg-surface-3 text-muted",
            )}
          >
            {item}
          </span>
        ))}
      </div>
    </div>
  );
}
