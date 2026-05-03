"use client";

import type { Lead } from "@/lib/types";
import { HookTierBadge } from "@/components/shared/HookTierBadge";
import { cn, formatRelative, truncate } from "@/lib/utils";
import { Star } from "lucide-react";

interface ApprovalCardProps {
  lead: Lead;
  subject?: string | null;
  selected?: boolean;
  onClick: () => void;
}

export function ApprovalCard({
  lead,
  subject,
  selected,
  onClick,
}: ApprovalCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "w-full text-left border-l-2 px-4 py-3 transition-colors",
        "border-b border-b-border",
        selected
          ? "bg-surface-2 border-l-[color:var(--accent)]"
          : "border-l-transparent hover:bg-surface-2/50"
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <HookTierBadge tier={lead.latest_hook_tier} />
        </div>
        <span className="font-mono text-[10px] uppercase tracking-wider text-text-mute">
          {formatRelative(lead.updated_at)}
        </span>
      </div>

      <div className="pt-1.5 font-semibold text-text text-[14px] truncate">
        {lead.company}
      </div>

      {lead.owner_name || lead.email ? (
        <div className="pt-0.5 text-xs text-text-dim truncate">
          {lead.owner_name && <span>{lead.owner_name} </span>}
          {lead.email && (
            <span className="text-text-mute font-mono">&lt;{lead.email}&gt;</span>
          )}
        </div>
      ) : null}

      <div className="pt-1.5 flex items-center gap-3 font-mono text-[10px] uppercase tracking-wider text-text-mute">
        {lead.google_rating != null && (
          <span className="inline-flex items-center gap-1">
            <Star className="h-2.5 w-2.5 fill-current" />
            <span className="tabular">
              {lead.google_rating.toFixed(1)}
              {lead.google_reviews != null && (
                <span className="text-text-mute/70"> · {lead.google_reviews}</span>
              )}
            </span>
          </span>
        )}
        <span>{lead.city}</span>
      </div>

      {subject && (
        <div className="pt-2 text-xs text-text-dim truncate italic">
          {truncate(subject, 72)}
        </div>
      )}
    </button>
  );
}
