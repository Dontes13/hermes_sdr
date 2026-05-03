import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * Bento-style grid primitive. 12-column CSS grid at ≥md breakpoints;
 * collapses to single-column on mobile. Children declare `span` (1-12) on
 * `BentoCard` to place themselves.
 */
export function BentoGrid({
  children,
  className,
  gap = 4,
}: {
  children: React.ReactNode;
  className?: string;
  /** Tailwind gap scale (1 = 4px). Default 4 → 16px. */
  gap?: 2 | 3 | 4 | 5 | 6;
}) {
  return (
    <div
      className={cn(
        "grid grid-cols-1 md:grid-cols-12",
        `gap-${gap}`,
        className
      )}
    >
      {children}
    </div>
  );
}

type BentoSpan = 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12;

// Tailwind can't infer a dynamic `col-span-${n}` class, so we keep a static
// lookup. This ensures the utilities are present in the generated CSS.
const SPAN_MD: Record<BentoSpan, string> = {
  1: "md:col-span-1",
  2: "md:col-span-2",
  3: "md:col-span-3",
  4: "md:col-span-4",
  5: "md:col-span-5",
  6: "md:col-span-6",
  7: "md:col-span-7",
  8: "md:col-span-8",
  9: "md:col-span-9",
  10: "md:col-span-10",
  11: "md:col-span-11",
  12: "md:col-span-12",
};

const ROW_SPAN: Record<BentoSpan, string> = {
  1: "md:row-span-1",
  2: "md:row-span-2",
  3: "md:row-span-3",
  4: "md:row-span-4",
  5: "md:row-span-5",
  6: "md:row-span-6",
  7: "md:row-span-7",
  8: "md:row-span-8",
  9: "md:row-span-9",
  10: "md:row-span-10",
  11: "md:row-span-11",
  12: "md:row-span-12",
};

interface BentoCardProps {
  span?: BentoSpan;
  rowSpan?: BentoSpan;
  eyebrow?: React.ReactNode;
  title?: React.ReactNode;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  bodyClassName?: string;
  /** Apply an ambient accent glow when this card wants the user's eye. */
  glow?: boolean;
  /** Whole card is a link/button affordance. */
  interactive?: boolean;
  onClick?: () => void;
}

export function BentoCard({
  span = 12,
  rowSpan,
  eyebrow,
  title,
  action,
  children,
  className,
  bodyClassName,
  glow = false,
  interactive = false,
  onClick,
}: BentoCardProps) {
  const hasHeader = eyebrow || title || action;
  return (
    <div
      className={cn(
        "border border-border bg-surface flex flex-col rounded-xl overflow-hidden",
        SPAN_MD[span],
        rowSpan && ROW_SPAN[rowSpan],
        glow && "glow-accent",
        interactive &&
          "cursor-pointer transition-all duration-[var(--dur-med)] hover:bg-surface-elevated hover:border-border-strong",
        className
      )}
      onClick={onClick}
      role={interactive ? "button" : undefined}
      tabIndex={interactive ? 0 : undefined}
      onKeyDown={
        interactive
          ? (e) => {
              if (onClick && (e.key === "Enter" || e.key === " ")) {
                e.preventDefault();
                onClick();
              }
            }
          : undefined
      }
    >
      {hasHeader && (
        <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-3">
          <div className="flex items-center gap-2 min-w-0">
            {eyebrow && <span className="label-xs truncate">{eyebrow}</span>}
            {title && (
              <span className="text-sm font-semibold text-text truncate">
                {title}
              </span>
            )}
          </div>
          {action && <div className="flex items-center gap-1">{action}</div>}
        </div>
      )}
      <div className={cn("flex-1 p-4", bodyClassName)}>{children}</div>
    </div>
  );
}
