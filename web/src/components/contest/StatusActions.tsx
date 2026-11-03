import { Bookmark, BookmarkCheck, EyeOff, Rocket, RotateCcw } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/Toast";
import { STATUS_LABEL } from "@/lib/format";
import { useSetStatus, useStartProject } from "@/lib/queries";
import type { Contest, ContestStatus } from "@/lib/types";

const SHORTLISTED: ContestStatus[] = ["INTERESTED", "ENTERING", "SUBMITTED"];

export function StatusActions({
  contest,
  size = "sm",
  showEnter = true,
  fill,
}: {
  contest: Pick<Contest, "key" | "status" | "title">;
  size?: "sm" | "md";
  showEnter?: boolean;
  /** 남은 폭을 Shortlist 버튼이 채운다. 세로로 쌓이는 카드에서 쓴다. */
  fill?: boolean;
}) {
  const setStatus = useSetStatus();
  const startProject = useStartProject();
  const toast = useToast();

  const shortlisted = SHORTLISTED.includes(contest.status);
  const ignored = contest.status === "IGNORE";
  const entering = contest.status === "ENTERING" || contest.status === "SUBMITTED";

  const change = (status: ContestStatus, message: string) => {
    setStatus.mutate(
      { key: contest.key, status },
      {
        onSuccess: () => toast({ tone: "success", message, detail: contest.title }),
        onError: (error) =>
          toast({ tone: "error", message: "상태를 바꾸지 못했습니다", detail: String(error) }),
      },
    );
  };

  return (
    <div className="flex items-center gap-1.5">
      {ignored ? (
        <Button
          size={size}
          onClick={(event) => {
            event.stopPropagation();
            event.preventDefault();
            change("NEW", "무시를 해제했습니다");
          }}
          loading={setStatus.isPending}
        >
          <RotateCcw className="h-3.5 w-3.5" />
          되돌리기
        </Button>
      ) : (
        <>
          <Button
            size={size}
            variant={shortlisted ? "primary" : "secondary"}
            className={fill ? "grow justify-center" : undefined}
            loading={setStatus.isPending && !startProject.isPending}
            onClick={(event) => {
              event.stopPropagation();
              event.preventDefault();
              change(
                shortlisted ? "NEW" : "INTERESTED",
                shortlisted ? "Shortlist에서 제외했습니다" : "Shortlist에 담았습니다",
              );
            }}
          >
            {shortlisted ? (
              <BookmarkCheck className="h-3.5 w-3.5" />
            ) : (
              <Bookmark className="h-3.5 w-3.5" />
            )}
            {shortlisted ? "담김" : "Shortlist"}
          </Button>

          {showEnter && (
            <Button
              size={size}
              variant={entering ? "dark" : "secondary"}
              loading={startProject.isPending}
              onClick={(event) => {
                event.stopPropagation();
                event.preventDefault();
                if (entering) return;
                startProject.mutate(contest.key, {
                  onSuccess: () =>
                    toast({
                      tone: "success",
                      message: "참가 프로젝트를 만들었습니다",
                      detail: "‘참가 중’ 화면에서 진행 단계를 관리하세요.",
                    }),
                  onError: (error) =>
                    toast({
                      tone: "error",
                      message: "프로젝트 생성 실패",
                      detail: String(error),
                    }),
                });
              }}
            >
              <Rocket className="h-3.5 w-3.5" />
              {entering ? STATUS_LABEL[contest.status] : "참가하기"}
            </Button>
          )}

          <Button
            size={size}
            variant="ghost"
            title="추천 목록에서 숨기기"
            onClick={(event) => {
              event.stopPropagation();
              event.preventDefault();
              change("IGNORE", "추천 목록에서 숨겼습니다");
            }}
          >
            <EyeOff className="h-3.5 w-3.5" />
          </Button>
        </>
      )}
    </div>
  );
}
