import type { ReplyIntent } from "@/lib/types";
import { cn } from "@/lib/utils";

const INTENT_VAR: Record<ReplyIntent, string> = {
  interested: "var(--intent-interested)",
  question: "var(--intent-question)",
  objection: "var(--intent-objection)",
  booking: "var(--intent-booking)",
  negative: "var(--intent-negative)",
  other: "var(--intent-other)",
};

const LABEL: Record<ReplyIntent, string> = {
  interested: "INTERESTED",
  question: "QUESTION",
  objection: "OBJECTION",
  booking: "BOOKING",
  negative: "NEGATIVE",
  other: "OTHER",
};

interface IntentBadgeProps {
  intent: ReplyIntent;
  className?: string;
}

export function IntentBadge({ intent, className }: IntentBadgeProps) {
  const color = INTENT_VAR[intent];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider",
        className
      )}
      style={{ color }}
    >
      <span
        aria-hidden
        className="h-[6px] w-[6px] rounded-full"
        style={{ backgroundColor: color }}
      />
      <span className="font-semibold">{LABEL[intent]}</span>
    </span>
  );
}
