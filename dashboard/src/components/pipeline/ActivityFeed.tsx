"use client";

import Link from "next/link";
import { ArrowDownLeft, ArrowUpRight } from "lucide-react";
import type { RecentInbound, RecentOutbound } from "@/lib/types";
import { formatRelative } from "@/lib/utils";

interface ActivityItem {
  id: string;
  kind: "outbound" | "inbound";
  lead_id: string;
  subject: string | null;
  at: string;
}

export function ActivityFeed({
  recentOutbound,
  recentInbound,
  limit = 8,
}: {
  recentOutbound: RecentOutbound[];
  recentInbound: RecentInbound[];
  limit?: number;
}) {
  const items: ActivityItem[] = [
    ...recentOutbound.map((m) => ({
      id: m.id,
      kind: "outbound" as const,
      lead_id: m.lead_id,
      subject: m.subject,
      at: m.sent_at,
    })),
    ...recentInbound.map((m) => ({
      id: m.id,
      kind: "inbound" as const,
      lead_id: m.lead_id,
      subject: m.subject,
      at: m.created_at,
    })),
  ]
    .sort((a, b) => (a.at < b.at ? 1 : -1))
    .slice(0, limit);

  if (items.length === 0) {
    return (
      <div className="py-8 text-center text-sm text-text-mute">
        No activity yet
      </div>
    );
  }

  return (
    <ul className="stagger divide-y divide-border">
      {items.map((item, i) => (
        <li key={item.id} style={{ ["--i" as string]: i } as React.CSSProperties}>
          <Link
            href={`/leads/${item.lead_id}`}
            className="flex items-center gap-3 px-1 py-2 group"
          >
            <ActivityIcon kind={item.kind} />
            <div className="flex-1 min-w-0">
              <div className="text-sm text-text truncate group-hover:text-[color:var(--accent)] transition-colors">
                {item.subject || (item.kind === "outbound" ? "(sent draft)" : "(inbound reply)")}
              </div>
              <div className="text-[11px] text-text-mute">
                {item.kind === "outbound" ? "sent" : "received"} ·{" "}
                {formatRelative(item.at)}
              </div>
            </div>
          </Link>
        </li>
      ))}
    </ul>
  );
}

function ActivityIcon({ kind }: { kind: "outbound" | "inbound" }) {
  const Icon = kind === "outbound" ? ArrowUpRight : ArrowDownLeft;
  const color = kind === "outbound" ? "var(--text-dim)" : "var(--accent)";
  return (
    <div
      className="h-6 w-6 shrink-0 border border-border rounded-lg flex items-center justify-center bg-surface-2"
      style={{ color }}
    >
      <Icon className="h-3 w-3" strokeWidth={1.8} />
    </div>
  );
}
