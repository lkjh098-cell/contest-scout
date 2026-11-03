import { Link } from "react-router-dom";
import { ExternalLink, Rocket } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Form";
import { Panel, SectionHeader } from "@/components/ui/Panel";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { cn } from "@/lib/cn";
import { formatDate, formatDday, STAGE_LABEL } from "@/lib/format";
import { useProjects, useUpdateProject } from "@/lib/queries";
import type { Project } from "@/lib/types";

export function Entering() {
  const { data, isLoading, error, refetch } = useProjects();

  if (error) return <ErrorState error={error} onRetry={() => void refetch()} />;

  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 2 }).map((_, index) => (
          <div key={index} className="rounded-xl border border-line bg-surface p-5">
            <Skeleton className="h-4 w-1/2" />
            <Skeleton className="mt-3 h-2 w-full" />
          </div>
        ))}
      </div>
    );
  }

  if (!data?.items.length) {
    return (
      <Panel flush>
        <EmptyState
          icon={<Rocket className="h-5 w-5" />}
          title="참가 중인 공모전이 없습니다."
          description="공모전 상세 화면에서 ‘참가하기’ 를 누르면 여기에 프로젝트가 생깁니다."
          action={
            <Link to="/shortlist">
              <Button size="sm" variant="primary">
                Shortlist 보기
              </Button>
            </Link>
          }
        />
      </Panel>
    );
  }

  return (
    <div className="space-y-4">
      <SectionHeader
        title={`진행 중인 프로젝트 ${data.items.length}건`}
        description="단계를 바꾸면 진행률이 함께 움직입니다."
      />
      <div className="space-y-3">
        {data.items.map((project) => (
          <ProjectCard key={project.id} project={project} stages={data.stages} />
        ))}
      </div>

      <p className="text-[12.5px] leading-relaxed text-subtle">
        Contest Builder 연동은 다음 단계입니다. 지금은 이 프로젝트 레코드(제목·요강·마감·요구사항)를
        그대로 넘길 수 있도록 구조만 확정해 두었습니다.
      </p>
    </div>
  );
}

function ProjectCard({ project, stages }: { project: Project; stages: string[] }) {
  const update = useUpdateProject();
  const toast = useToast();
  const urgent = project.days_left !== null && project.days_left <= 7;

  return (
    <article className="rounded-xl border border-line bg-surface p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <Link
            to={`/contests/${encodeURIComponent(project.contest_key)}`}
            className="text-[15px] font-semibold leading-snug tracking-[-0.01em] text-ink decoration-line-strong underline-offset-4 hover:underline"
          >
            {project.title}
          </Link>
          <p className="mt-1 text-[12.5px] text-muted">
            마감 {formatDate(project.deadline)}
            {project.requirements && ` · ${project.requirements}`}
          </p>
        </div>
        <span
          className={cn(
            "num rounded-md px-2 py-1 text-[13px] font-bold",
            urgent ? "bg-danger-soft text-danger" : "bg-surface-3 text-muted",
          )}
        >
          {formatDday(project.days_left)}
        </span>
      </div>

      <div className="mt-5 flex flex-wrap items-end gap-4">
        <div className="min-w-[180px] grow">
          <div className="flex items-baseline justify-between">
            <span className="label-xs">진행 단계</span>
            <span className="num text-[12px] text-muted">
              {project.stage_index + 1} / {project.stage_count}
            </span>
          </div>
          <div className="mt-2 flex gap-1">
            {stages.map((stage, index) => (
              <span
                key={stage}
                title={STAGE_LABEL[stage] ?? stage}
                className={cn(
                  "h-1.5 flex-1 rounded-full transition-colors",
                  index <= project.stage_index ? "bg-ink" : "bg-surface-3",
                )}
              />
            ))}
          </div>
        </div>

        <Select
          value={project.stage}
          className="w-[168px]"
          disabled={update.isPending}
          onChange={(event) =>
            update.mutate(
              { contestKey: project.contest_key, stage: event.target.value },
              {
                onSuccess: () =>
                  toast({
                    tone: "success",
                    message: "진행 단계를 바꿨습니다",
                    detail: STAGE_LABEL[event.target.value],
                  }),
              },
            )
          }
        >
          {stages.map((stage) => (
            <option key={stage} value={stage}>
              {STAGE_LABEL[stage] ?? stage}
            </option>
          ))}
        </Select>

        <Link to={`/contests/${encodeURIComponent(project.contest_key)}`}>
          <Button size="md" variant="ghost">
            분석 보기
            <ExternalLink className="h-3.5 w-3.5" />
          </Button>
        </Link>
      </div>

      {project.next_action && (
        <p className="mt-4 border-t border-line pt-3.5 text-[13px] text-muted">
          <span className="label-xs mr-2">다음 할 일</span>
          {project.next_action}
        </p>
      )}
    </article>
  );
}
