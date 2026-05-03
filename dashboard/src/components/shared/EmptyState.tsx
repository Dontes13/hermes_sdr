import type { LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: { label: string; onClick: () => void };
  /** Visual weight. "sm" fits card bodies, "md" fills the right pane. */
  size?: "sm" | "md";
  className?: string;
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  size = "md",
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 text-center",
        size === "md" ? "py-16 px-6" : "py-10 px-4",
        className
      )}
    >
      {Icon && (
        <div
          className={cn(
            "flex items-center justify-center border border-border bg-surface-2/60 text-text-mute",
            size === "md" ? "h-11 w-11" : "h-9 w-9"
          )}
        >
          <Icon
            className={size === "md" ? "h-5 w-5" : "h-4 w-4"}
            strokeWidth={1.4}
            aria-hidden
          />
        </div>
      )}
      <div className="space-y-1 max-w-sm">
        <div className="font-mono text-xs uppercase tracking-wider text-text-dim">
          {title}
        </div>
        {description && (
          <p className="text-sm text-text-mute leading-relaxed">{description}</p>
        )}
      </div>
      {action && (
        <Button size="sm" variant="outline" onClick={action.onClick}>
          {action.label}
        </Button>
      )}
    </div>
  );
}
