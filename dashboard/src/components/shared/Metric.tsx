import * as React from "react";
import { cn } from "@/lib/utils";

type MetricSize = "sm" | "md" | "lg" | "xl";
type MetricTone = "default" | "accent" | "warn" | "danger" | "mute";

const SIZE_CLASS: Record<MetricSize, string> = {
  sm: "metric-sm",
  md: "metric-md",
  lg: "metric-lg",
  xl: "metric-xl",
};

const TONE_STYLE: Record<MetricTone, string> = {
  default: "text-text",
  accent: "text-[color:var(--accent)]",
  warn: "text-[color:var(--warn)]",
  danger: "text-[color:var(--danger)]",
  mute: "text-text-mute",
};

interface MetricProps {
  label?: React.ReactNode;
  value: React.ReactNode;
  sub?: React.ReactNode;
  size?: MetricSize;
  tone?: MetricTone;
  /** Stacked (default) vs inline (label to the left). */
  layout?: "stacked" | "inline";
  className?: string;
}

export function Metric({
  label,
  value,
  sub,
  size = "md",
  tone = "default",
  layout = "stacked",
  className,
}: MetricProps) {
  if (layout === "inline") {
    return (
      <div className={cn("flex items-baseline gap-2", className)}>
        {label && <span className="label-xs">{label}</span>}
        <span className={cn(SIZE_CLASS[size], TONE_STYLE[tone])}>{value}</span>
        {sub && <span className="label-xs">{sub}</span>}
      </div>
    );
  }
  return (
    <div className={cn("space-y-1.5", className)}>
      {label && <div className="label-xs">{label}</div>}
      <div className={cn(SIZE_CLASS[size], TONE_STYLE[tone], "animate-tabular")}>
        {value}
      </div>
      {sub && <div className="font-mono text-[10px] text-text-mute">{sub}</div>}
    </div>
  );
}
