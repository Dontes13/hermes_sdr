"use client";

import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { HOOK_TIER_NAMES, type HookTier } from "@/lib/types";
import { EmptyState } from "@/components/shared/EmptyState";
import { BarChart3 } from "lucide-react";

interface HookTierChartProps {
  tiersSent: Record<string, number>;
}

const TIER_COLORS: Record<HookTier, string> = {
  1: "var(--tier-1)",
  2: "var(--tier-2)",
  3: "var(--tier-3)",
  4: "var(--tier-4)",
  5: "var(--tier-5)",
};

export function HookTierChart({ tiersSent }: HookTierChartProps) {
  const total = Object.values(tiersSent).reduce((a, b) => a + b, 0);

  if (total === 0) {
    return (
      <EmptyState
        icon={BarChart3}
        title="No hooks sent yet"
        description="Hook tier distribution will appear here once you've sent drafts."
        size="sm"
      />
    );
  }

  const data: { tier: HookTier; label: string; name: string; value: number }[] = [];
  for (let t = 1 as HookTier; t <= 5; t = (t + 1) as HookTier) {
    data.push({
      tier: t,
      label: `T${t}`,
      name: HOOK_TIER_NAMES[t],
      value: tiersSent[String(t)] ?? 0,
    });
  }

  return (
    <div className="h-56">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 8, right: 28, bottom: 8, left: 8 }}
          barCategoryGap={10}
        >
          <XAxis
            type="number"
            tick={{ fill: "var(--text-mute)", fontSize: 11, fontFamily: "var(--font-sans)" }}
            axisLine={{ stroke: "var(--border)" }}
            tickLine={false}
            allowDecimals={false}
          />
          <YAxis
            type="category"
            dataKey="label"
            tick={{ fill: "var(--text-dim)", fontSize: 11, fontFamily: "var(--font-sans)" }}
            axisLine={{ stroke: "var(--border)" }}
            tickLine={false}
            width={34}
          />
          <Tooltip
            cursor={{ fill: "var(--surface-2)" }}
            contentStyle={{
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              fontFamily: "var(--font-sans)",
              fontSize: 11,
              color: "var(--text)",
              boxShadow: "var(--shadow-md)",
            }}
            labelFormatter={(label, payload) => {
              const entry = payload?.[0]?.payload as (typeof data)[number] | undefined;
              return entry ? `${entry.label} · ${entry.name}` : String(label);
            }}
            formatter={(value: number) => [value, "sent"]}
          />
          <Bar dataKey="value" radius={[0, 4, 4, 0]} isAnimationActive={false}>
            {data.map((entry) => (
              <Cell key={entry.tier} fill={TIER_COLORS[entry.tier]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
