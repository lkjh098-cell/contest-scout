import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  CartesianGrid,
  Cell,
  ReferenceArea,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";

import { formatDday, formatPrize } from "@/lib/format";
import type { MatrixPoint } from "@/lib/types";

const TIER_FILL: Record<string, string> = {
  S: "var(--tier-s-fg)",
  A: "var(--accent)",
  B: "var(--text-subtle)",
  SKIP: "var(--line-strong)",
};

function PointTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { payload: MatrixPoint }[];
}) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;
  return (
    <div className="max-w-[260px] rounded-lg border border-line bg-surface p-2.5 shadow-float">
      <p className="line-clamp-2 text-[13px] font-semibold text-ink">{point.title}</p>
      <p className="mt-0.5 line-clamp-1 text-[12px] text-muted">
        {point.organizer ?? "주최 미확인"}
      </p>
      <div className="num mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-[12px] text-muted">
        <span>점수</span>
        <span className="text-right font-semibold text-ink">{point.total}</span>
        <span>상금</span>
        <span className="text-right text-ink">{formatPrize(point.prize)}</span>
        <span>마감</span>
        <span className="text-right text-ink">{formatDday(point.days_left)}</span>
      </div>
    </div>
  );
}

/** 가로축 수상 가능성, 세로축 수상·포트폴리오 가치. 우상단이 곧 우선순위다.
 *
 * 축 이름은 Recharts의 `label` 대신 차트 밖 텍스트로 뺐다. 눈금 숫자와 겹치면
 * 정보량이 늘어난 게 아니라 읽기만 어려워진다.
 */
export function OpportunityMatrix({ points }: { points: MatrixPoint[] }) {
  const navigate = useNavigate();
  const data = useMemo(
    () =>
      points.map((point) => ({
        ...point,
        size: point.prize ? Math.min(point.prize, 30_000_000) : 400_000,
      })),
    [points],
  );

  return (
    <div>
      <div className="flex items-center justify-between pb-1">
        <span className="label-xs">가치 ↑</span>
        <span className="label-xs text-[var(--accent)]">우선 검토 구간</span>
      </div>

      <ResponsiveContainer width="100%" height={286}>
        <ScatterChart margin={{ top: 8, right: 10, bottom: 4, left: -14 }}>
          <CartesianGrid strokeDasharray="2 4" />
          <ReferenceArea
            x1={55}
            x2={100}
            y1={55}
            y2={100}
            fill="var(--accent)"
            fillOpacity={0.05}
            stroke="var(--accent-line)"
            strokeDasharray="3 3"
          />
          <XAxis
            type="number"
            dataKey="win"
            domain={[0, 100]}
            tickLine={false}
            axisLine={{ stroke: "var(--line)" }}
            ticks={[0, 25, 50, 75, 100]}
          />
          <YAxis
            type="number"
            dataKey="value"
            domain={[0, 100]}
            tickLine={false}
            axisLine={{ stroke: "var(--line)" }}
            ticks={[0, 25, 50, 75, 100]}
            width={44}
          />
          <ZAxis type="number" dataKey="size" range={[60, 420]} />
          <Tooltip
            content={<PointTooltip />}
            cursor={{ strokeDasharray: "3 3", stroke: "var(--line-strong)" }}
          />
          <Scatter
            data={data}
            onClick={(point: unknown) => {
              const key = (point as MatrixPoint | undefined)?.key;
              if (key) navigate(`/contests/${encodeURIComponent(key)}`);
            }}
            className="cursor-pointer"
          >
            {data.map((point) => (
              <Cell
                key={point.key}
                fill={TIER_FILL[point.tier] ?? TIER_FILL.SKIP}
                fillOpacity={point.tier === "SKIP" ? 0.28 : 0.6}
                stroke={TIER_FILL[point.tier] ?? TIER_FILL.SKIP}
                strokeOpacity={point.tier === "SKIP" ? 0.4 : 0.95}
              />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>

      <p className="label-xs -mt-1 text-right">수상 가능성 →</p>

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 border-t border-line pt-3 text-[11px] text-subtle">
        {(["S", "A", "B", "SKIP"] as const).map((tier) => (
          <span key={tier} className="inline-flex items-center gap-1.5">
            <span
              className="h-2 w-2 rounded-full"
              style={{ background: TIER_FILL[tier], opacity: tier === "SKIP" ? 0.45 : 0.8 }}
            />
            {tier === "SKIP" ? "제외" : `${tier}등급`}
          </span>
        ))}
        <span className="ml-auto">원 크기 = 상금 규모</span>
      </div>
    </div>
  );
}
