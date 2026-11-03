import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { formatDate } from "@/lib/format";

export function DiscoveryChart({ data }: { data: { date: string; count: number }[] }) {
  if (data.length < 2) {
    return (
      <p className="flex h-[180px] items-center justify-center text-[13px] text-subtle">
        추이를 그리려면 최소 이틀치 수집 기록이 필요합니다.
      </p>
    );
  }
  return (
    <ResponsiveContainer width="100%" height={180}>
      <AreaChart data={data} margin={{ top: 8, right: 4, bottom: 0, left: -22 }}>
        <defs>
          <linearGradient id="discovery" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.22} />
            <stop offset="100%" stopColor="var(--accent)" stopOpacity={0} />
          </linearGradient>
        </defs>
        <XAxis
          dataKey="date"
          tickLine={false}
          axisLine={false}
          tickFormatter={(value: string) => value.slice(5).replace("-", "/")}
          minTickGap={24}
        />
        <YAxis tickLine={false} axisLine={false} allowDecimals={false} width={44} />
        <Tooltip
          cursor={{ stroke: "var(--line-strong)" }}
          content={({ active, payload, label }) =>
            active && payload?.length ? (
              <div className="rounded-lg border border-line bg-surface px-2.5 py-1.5 shadow-float">
                <p className="text-[12px] text-muted">{formatDate(String(label))}</p>
                <p className="num text-[13px] font-semibold text-ink">
                  {payload[0].value}건 발견
                </p>
              </div>
            ) : null
          }
        />
        <Area
          type="monotone"
          dataKey="count"
          stroke="var(--accent)"
          strokeWidth={1.6}
          fill="url(#discovery)"
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
