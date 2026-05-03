import type { LeadStatus } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Star } from "lucide-react";

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
  new: "NEW",
  enriched: "ENRICHED",
  drafted: "DRAFTED",
  approved: "APPROVED",
  sent: "SENT",
  replied: "REPLIED",
  booked: "BOOKED",
  dead: "DEAD",
  unsubscribed: "UNSUB",
};

interface StatusBadgeProps {
  status: LeadStatus;
  className?: string;
  size?: "sm" | "md";
}

export function StatusBadge({ status, className, size = "sm" }: StatusBadgeProps) {
  const color = STATUS_VAR[status];
  const dim = status === "dead" || status === "unsubscribed";

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 font-mono uppercase tracking-wider",
        size === "sm" ? "text-[10px]" : "text-xs",
        dim && "opacity-60",
        className
      )}
      style={{ color }}
    >
      <span
        aria-hidden
        className="h-[6px] w-[6px] rounded-full"
        style={{ backgroundColor: color }}
      />
      <span className="font-semibold">{LABEL[status]}</span>
      {status === "booked" && (
        <Star
          aria-hidden
          className="h-3 w-3"
          style={{ color, fill: color }}
          strokeWidth={1.5}
        />
      )}
    </span>
  );
}
