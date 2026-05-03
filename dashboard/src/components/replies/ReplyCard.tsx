"use client";

import type { ReplyEntry } from "@/lib/types";
import { IntentBadge } from "@/components/shared/IntentBadge";
import { cn, formatRelative, parseReplyIntent, truncate } from "@/lib/utils";

interface ReplyCardProps {
  entry: ReplyEntry;
  selected?: boolean;
  onClick: () => void;
}

export function ReplyCard({ entry, selected, onClick }: ReplyCardProps) {
  const intent = parseReplyIntent(entry.pending_reply_draft?.hook_rationale);
  const inbound = entry.latest_inbound;
  const draft = entry.pending_reply_draft;

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
        <div className="flex items-center gap-1.5">
          {intent ? (
            <IntentBadge intent={intent} />
          ) : (
            <span className="font-mono text-[10px] uppercase tracking-wider text-text-mute">
              no intent
            </span>
          )}
          {entry.is_test && (
            <span
              className="font-mono text-[9px] uppercase tracking-wider px-1.5 py-0.5 border"
              style={{
                color: "var(--warn)",
                borderColor: "var(--warn)",
              }}
            >
              test
            </span>
          )}
        </div>
        <span className="font-mono text-[10px] uppercase tracking-wider text-text-mute">
          {formatRelative(inbound?.created_at ?? entry.lead.updated_at)}
        </span>
      </div>

      <div className="pt-1.5 font-semibold text-text truncate text-[14px]">
        {entry.lead.company}
      </div>

      {(entry.lead.owner_name || entry.lead.email) && (
        <div className="pt-0.5 text-xs text-text-dim truncate">
          {entry.lead.owner_name && <span>{entry.lead.owner_name} </span>}
          {entry.lead.email && (
            <span className="text-text-mute font-mono">&lt;{entry.lead.email}&gt;</span>
          )}
        </div>
      )}

      {inbound && (
        <div className="pt-2 text-xs text-text-dim italic line-clamp-2">
          {truncate(inbound.body.replace(/\s+/g, " "), 160)}
        </div>
      )}

      <div className="pt-2 border-t border-border mt-2 pt-2">
        {draft ? (
          <div className="text-[11px] text-text-mute flex gap-1.5 items-start">
            <span className="font-mono uppercase tracking-wider text-[9px] mt-0.5 shrink-0">
              draft
            </span>
            <span className="text-text-dim line-clamp-1">
              {truncate(draft.body.replace(/\s+/g, " "), 110)}
            </span>
          </div>
        ) : (
          <div className="text-[11px] text-text-mute font-mono uppercase tracking-wider">
            no reply drafted yet
          </div>
        )}
      </div>
    </button>
  );
}
