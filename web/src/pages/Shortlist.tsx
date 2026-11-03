import { Link } from "react-router-dom";
import { Bookmark } from "lucide-react";

import { ContestCard } from "@/components/contest/ContestCard";
import { Button } from "@/components/ui/Button";
import { Panel, SectionHeader } from "@/components/ui/Panel";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { useContests } from "@/lib/queries";

export function Shortlist() {
  const { data, isLoading, error, refetch } = useContests({
    status: ["INTERESTED"],
    sort: "deadline",
    order: "asc",
    page_size: 60,
  });

  if (error) return <ErrorState error={error} onRetry={() => void refetch()} />;

  if (isLoading) {
    return (
      <div className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-3">
        {Array.from({ length: 3 }).map((_, index) => (
          <div key={index} className="rounded-xl border border-line bg-surface p-4">
            <Skeleton className="h-5 w-20" />
            <Skeleton className="mt-4 h-4 w-full" />
            <Skeleton className="mt-2 h-4 w-1/2" />
          </div>
        ))}
      </div>
    );
  }

  if (!data?.items.length) {
    return (
      <Panel flush>
        <EmptyState
          icon={<Bookmark className="h-5 w-5" />}
          title="담아 둔 공모전이 없습니다."
          description="추천 카드나 목록에서 Shortlist를 누르면 여기에 모입니다."
          action={
            <Link to="/discover">
              <Button size="sm" variant="primary">
                공모전 탐색하기
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
        title={`${data.total}건을 담아 두었습니다`}
        description="마감이 가까운 순서로 보여 드립니다."
      />
      <div className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-3">
        {data.items.map((contest) => (
          <ContestCard key={contest.key} contest={contest} />
        ))}
      </div>
    </div>
  );
}
