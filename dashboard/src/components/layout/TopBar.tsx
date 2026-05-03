import * as React from "react";
import { cn } from "@/lib/utils";

interface TopBarProps {
  title: string;
  eyebrow?: string;
  subtitle?: string;
  right?: React.ReactNode;
  className?: string;
}

export function TopBar({
  title,
  eyebrow,
  subtitle,
  right,
  className,
}: TopBarProps) {
  return (
    <header
      className={cn(
        "flex items-end justify-between gap-4 border-b border-border px-8 py-5",
        className
      )}
    >
      <div className="space-y-1">
        {eyebrow && (
          <div className="flex items-center gap-1.5 label-xs">
            {String(eyebrow)
              .split("/")
              .map((seg, i, arr) => (
                <React.Fragment key={i}>
                  <span
                    style={{
                      color:
                        i < arr.length - 1
                          ? "var(--text-mute)"
                          : "var(--accent)",
                    }}
                  >
                    {seg.trim().toUpperCase()}
                  </span>
                  {i < arr.length - 1 && (
                    <span className="text-border-strong">/</span>
                  )}
                </React.Fragment>
              ))}
          </div>
        )}
        <h1 className="text-xl font-semibold tracking-tight text-text">
          {title}
        </h1>
        {subtitle && (
          <div className="text-[11px] text-text-mute">
            {subtitle}
          </div>
        )}
      </div>
      {right && <div className="flex items-center gap-2">{right}</div>}
    </header>
  );
}
