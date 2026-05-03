import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * Two-column layout used by Approvals and Replies: a fixed-width sidebar
 * (scrollable) with selectable items, plus a detail pane that reacts to
 * the selected sidebar item.
 *
 * Consolidates the 360px/380px variants that existed per-page into a
 * single canonical 320px width.
 */
export function SplitPane({
  sidebar,
  detail,
  className,
  sidebarWidth = 320,
}: {
  sidebar: React.ReactNode;
  detail: React.ReactNode;
  className?: string;
  sidebarWidth?: number;
}) {
  return (
    <div className={cn("flex flex-1 min-h-0", className)}>
      <aside
        className="shrink-0 border-r border-border bg-surface flex flex-col"
        style={{ width: sidebarWidth }}
      >
        {sidebar}
      </aside>
      <main className="flex-1 min-w-0 bg-bg overflow-y-auto">{detail}</main>
    </div>
  );
}

/**
 * Standard row in a SplitPane sidebar. Handles active indicator (2px
 * accent left rail), hover elevation, keyboard activation.
 */
export function SplitPaneItem({
  active = false,
  onClick,
  children,
  className,
}: {
  active?: boolean;
  onClick?: () => void;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => {
        if (onClick && (e.key === "Enter" || e.key === " ")) {
          e.preventDefault();
          onClick();
        }
      }}
      className={cn(
        "group relative cursor-pointer border-b border-border px-4 py-3 transition-colors outline-none",
        active
          ? "bg-surface-2"
          : "hover:bg-surface-2/50 focus-visible:bg-surface-2/50",
        className
      )}
    >
      {active && (
        <span
          aria-hidden
          className="absolute left-0 top-0 bottom-0 w-[2px]"
          style={{ backgroundColor: "var(--accent)" }}
        />
      )}
      {children}
    </div>
  );
}
