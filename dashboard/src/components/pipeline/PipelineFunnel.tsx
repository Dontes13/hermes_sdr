"use client";

import Link from "next/link";
import type { LeadStatus } from "@/lib/types";

/**
 * Horizontal stacked-bar visualization of the pipeline. Each segment is
 * proportional to the status count; clicking jumps to /leads filtered to
 * that status.
 *
 * The "flow" order (new → enriched → drafted → sent → replied → booked)
 * is deliberate — reads left-to-right like the funnel it represents.
 * dead and unsubscribed are surfaced separately, below the main bar.
 */

const FLOW_ORDER: LeadStatus[] = [
  "new",
  "enriched",
  "drafted",
  "approved",
  "sent",
  "replied",
  "booked",
];
const EXIT_ORDER: LeadStatus[] = ["dead", "unsubscribed"];

const STATUS_COLOR: Record<LeadStatus, string> = {
  new: "var(--status-new)",
  enriched: "var(--status-enriched)",
  drafted: "var(--status-drafted)",
  approved: "var(--status-approved)",
  sent: "var(--status-sent)",
  replied: "var(--status-replied)",
  booked: "var(--status-booked)",
  dead: "var(--status-dead)",
  unsubscribed: "var(--status-unsubscribed)",
};

export function PipelineFunnel({
  counts,
}: {
  counts: Record<LeadStatus, number>;
}) {
  const flowTotal = FLOW_ORDER.reduce((s, k) => s + (counts[k] || 0), 0);
  const exitTotal = EXIT_ORDER.reduce((s, k) => s + (counts[k] || 0), 0);

  return (
    <div className="space-y-4">
      {/* Main flow bar */}
      <div>
        <div className="h-4 flex gap-px overflow-hidden rounded-full border border-border bg-surface-2">
          {flowTotal === 0 ? (
            <div className="flex-1 bg-surface-2" />
          ) : (
            FLOW_ORDER.map((s) => {
              const c = counts[s] || 0;
              if (c === 0) return null;
              const pct = (c / flowTotal) * 100;
              return (
                <Link
                  key={s}
                  href={`/leads?status=${s}`}
                  className="h-full hover:opacity-80 transition-opacity"
                  style={{ width: `${pct}%`, background: STATUS_COLOR[s] }}
                  title={`${s}: ${c}`}
                />
              );
            })
          )}
        </div>
        <div className="mt-3 grid grid-cols-7 gap-2">
          {FLOW_ORDER.map((s) => (
            <Link
              key={s}
              href={`/leads?status=${s}`}
              className="group block text-left"
            >
              <div className="flex items-center gap-1.5">
                <span
                  className="h-1.5 w-1.5 shrink-0"
                  style={{ background: STATUS_COLOR[s] }}
                />
                <span className="label-xs group-hover:text-text-dim transition-colors">
                  {s}
                </span>
              </div>
              <div className="metric-sm pl-3 pt-1 text-text">
                {counts[s] || 0}
              </div>
            </Link>
          ))}
        </div>
      </div>

      {/* Exit states — distinct from the flow, so they don't visually
          inflate the funnel's apparent throughput. */}
      {exitTotal > 0 && (
        <div className="flex items-center gap-4 border-t border-border pt-3">
          <span className="label-xs">Exits</span>
          {EXIT_ORDER.map((s) => (
            <Link
              key={s}
              href={`/leads?status=${s}`}
              className="flex items-baseline gap-1.5 group"
            >
              <span
                className="h-1.5 w-1.5 shrink-0 translate-y-[-1px]"
                style={{ background: STATUS_COLOR[s] }}
              />
              <span className="label-xs group-hover:text-text-dim transition-colors">
                {s}
              </span>
              <span className="metric-sm text-text">{counts[s] || 0}</span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
