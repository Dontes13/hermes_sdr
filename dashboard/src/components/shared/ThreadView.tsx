import type { Message } from "@/lib/types";
import { cn, formatShortDateTime } from "@/lib/utils";
import { HookTierBadge } from "./HookTierBadge";

interface ThreadViewProps {
  messages: Message[];
  /** An optional pending draft rendered at the end as a dashed-border bubble. */
  pendingDraft?: Message | null;
  className?: string;
}

export function ThreadView({ messages, pendingDraft, className }: ThreadViewProps) {
  return (
    <div className={cn("space-y-4", className)}>
      {messages.map((m, i) => (
        <MessageBubble
          key={m.id}
          message={m}
          showSubject={i === 0 || messages[i - 1]?.subject !== m.subject}
        />
      ))}
      {pendingDraft && <MessageBubble message={pendingDraft} isDraft showSubject />}
    </div>
  );
}

interface MessageBubbleProps {
  message: Message;
  isDraft?: boolean;
  showSubject?: boolean;
}

function MessageBubble({ message, isDraft, showSubject }: MessageBubbleProps) {
  const isOutbound = message.direction === "outbound";
  const timestamp = message.sent_at ?? message.created_at;
  const state = isDraft
    ? "DRAFT"
    : isOutbound
      ? message.sent_at
        ? "SENT"
        : "PENDING"
      : "RECEIVED";

  return (
    <div
      className={cn(
        "flex flex-col",
        isOutbound ? "items-end" : "items-start"
      )}
    >
      <div
        className={cn(
          "max-w-[78%] border",
          isOutbound
            ? "bg-surface-2 border-border"
            : "bg-surface border-border",
          isDraft && "border-dashed border-border-strong bg-transparent"
        )}
      >
        <div
          className={cn(
            "flex items-center justify-between gap-3 border-b border-border px-3 py-1.5 font-mono text-[10px] uppercase tracking-wider",
            isOutbound ? "text-text-mute" : "text-text-mute"
          )}
        >
          <span className="flex items-center gap-2">
            <span className="font-semibold" style={{ color: isDraft ? "var(--tier-4)" : undefined }}>
              {isOutbound ? (isDraft ? "DRAFT" : "HELIOS") : "BROKER"}
            </span>
            <span className="text-text-mute">·</span>
            <span>{state}</span>
            {message.channel && message.channel !== "email" && (
              <>
                <span className="text-text-mute">·</span>
                <span style={{ color: "var(--accent, #0a66c2)" }}>
                  {message.channel === "linkedin_invite" ? "LI INVITE" : "LI DM"}
                </span>
              </>
            )}
          </span>
          <span>{formatShortDateTime(timestamp)}</span>
        </div>
        <div className="px-4 py-3 space-y-2">
          {showSubject && message.subject && (
            <div className="font-mono text-xs text-text-dim">
              <span className="text-text-mute">Subject: </span>
              {message.subject}
            </div>
          )}
          <div className="whitespace-pre-wrap text-sm leading-relaxed text-text">
            {message.body}
          </div>
          {isOutbound && message.hook_tier_used != null && !isDraft && (
            <div className="pt-2 border-t border-border/60 flex items-center gap-3 flex-wrap">
              <HookTierBadge tier={message.hook_tier_used} />
              {message.hook_text && (
                <span className="font-mono text-[10px] text-text-mute">
                  Hook: <span className="text-text-dim normal-case">“{message.hook_text}”</span>
                </span>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
