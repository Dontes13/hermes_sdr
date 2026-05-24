"use client";

import { Loader2 } from "lucide-react";
import { useVariantStats } from "@/lib/hooks/useVariantStats";

function pct(rate: number): string {
  if (rate === 0) return "0%";
  return `${(rate * 100).toFixed(1)}%`;
}

export function VariantResultsTable() {
  const { data: stats, isLoading, error } = useVariantStats();

  if (isLoading && !stats) {
    return (
      <div className="flex items-center gap-2 text-text-mute text-sm py-8">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading stats…
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-sm text-red-500 py-4">
        Failed to load stats: {error instanceof Error ? error.message : String(error)}
      </div>
    );
  }

  if (!stats || stats.length === 0) {
    return (
      <div className="text-sm text-text-mute py-4">
        No variants found. Add variants in Settings → Subject line variants.
      </div>
    );
  }

  return (
    <div className="border border-border bg-surface">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border">
            <th className="px-4 py-2.5 text-left font-mono text-[11px] uppercase tracking-wider text-text-dim">
              Variant
            </th>
            <th className="px-4 py-2.5 text-right font-mono text-[11px] uppercase tracking-wider text-text-dim">
              Sends
            </th>
            <th className="px-4 py-2.5 text-right font-mono text-[11px] uppercase tracking-wider text-text-dim">
              Opens
            </th>
            <th className="px-4 py-2.5 text-right font-mono text-[11px] uppercase tracking-wider text-text-dim">
              Replies
            </th>
            <th className="px-4 py-2.5 text-right font-mono text-[11px] uppercase tracking-wider text-text-dim">
              Booked
            </th>
            <th className="px-4 py-2.5 text-right font-mono text-[11px] uppercase tracking-wider text-text-dim">
              Reply rate
            </th>
            <th className="px-4 py-2.5 text-right font-mono text-[11px] uppercase tracking-wider text-text-dim">
              Book rate
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {stats.map((row) => (
            <tr key={row.variant_id} className="hover:bg-surface-2 transition-colors">
              <td className="px-4 py-3">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-text">{row.name}</span>
                  {!row.is_active && (
                    <span className="text-[10px] font-mono uppercase tracking-wider text-text-mute border border-border px-1 py-0.5 rounded">
                      inactive
                    </span>
                  )}
                </div>
              </td>
              <td className="px-4 py-3 text-right tabular-nums text-text">
                {row.sends}
              </td>
              <td className="px-4 py-3 text-right tabular-nums text-text-mute">
                —
              </td>
              <td className="px-4 py-3 text-right tabular-nums text-text">
                {row.replies}
              </td>
              <td className="px-4 py-3 text-right tabular-nums text-text">
                {row.booked}
              </td>
              <td className="px-4 py-3 text-right tabular-nums text-text">
                {pct(row.reply_rate)}
              </td>
              <td className="px-4 py-3 text-right tabular-nums text-text">
                {pct(row.book_rate)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
