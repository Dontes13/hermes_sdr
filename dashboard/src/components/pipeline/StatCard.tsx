"use client";

import Link from "next/link";
import type { LeadStatus } from "@/lib/types";
import { cn, padCount } from "@/lib/utils";

const STATUS_VAR: Record<LeadStatus, string> = {
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

const LABEL: Record<LeadStatus, string> = {
  new: "new",
  enriched: "enriched",
  drafted: "drafted",
  approved: "approved",
  sent: "sent",
  replied: "replied",
  booked: "booked",
  dead: "dead",
  unsubscribed: "unsub",
};

interface StatCardProps {
  status: LeadStatus;
  count: number;
  loading?: boolean;
}

export function StatCard({ status, count, loading }: StatCardProps) {
  const color = STATUS_VAR[status];
  const dim = count === 0;

  return (
    <Link
      href={`/leads?status=${status}`}
      className={cn(
        "group block border border-border bg-surface px-4 py-3 transition-colors",
        "hover:border-border-strong hover:bg-surface-2",
        dim && "opacity-70"
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.18em] text-text-mute">
          <span
            aria-hidden
            className="h-[6px] w-[6px] rounded-full"
            style={{ backgroundColor: color }}
          />
          <span>{LABEL[status]}</span>
        </div>
      </div>
      <div className="pt-2 flex items-end justify-between gap-1">
        <span
          className={cn(
            "metric text-3xl leading-none font-semibold text-text",
            loading && "opacity-40"
          )}
          style={{ color: count > 0 ? undefined : "var(--text-mute)" }}
        >
          {padCount(count, 2)}
        </span>
        <span className="font-mono text-[10px] uppercase tracking-wider text-text-mute opacity-0 group-hover:opacity-100 transition-opacity">
          view →
        </span>
      </div>
    </Link>
  );
}
