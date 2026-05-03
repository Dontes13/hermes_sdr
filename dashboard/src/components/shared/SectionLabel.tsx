import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * Small uppercase mono header used to delimit page sections.
 * Replaces the many ad-hoc copies of this pattern around the codebase.
 */
export function SectionLabel({
  children,
  action,
  className,
}: {
  children: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn("flex items-center justify-between gap-3 pb-2.5", className)}
    >
      <span className="label-sm">{children}</span>
      {action}
    </div>
  );
}
