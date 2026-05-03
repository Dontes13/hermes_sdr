import * as React from "react";

/**
 * Minimal inline SVG sparkline. No axes, no tooltip — for at-a-glance
 * trends on cards. Pass an array of numbers; they're scaled to fit.
 */
export function Sparkline({
  data,
  width = 80,
  height = 20,
  strokeWidth = 1.25,
  color,
  fill = true,
  className,
}: {
  data: number[];
  width?: number;
  height?: number;
  strokeWidth?: number;
  /** Defaults to var(--accent). Pass an explicit hex/oklch to override. */
  color?: string;
  fill?: boolean;
  className?: string;
}) {
  if (!data.length) {
    return (
      <svg
        width={width}
        height={height}
        className={className}
        aria-hidden
      />
    );
  }

  const stroke = color ?? "var(--accent)";
  const max = Math.max(...data, 1);
  const min = Math.min(...data, 0);
  const range = max - min || 1;
  const stepX = data.length > 1 ? width / (data.length - 1) : 0;

  const points = data.map((v, i) => {
    const x = i * stepX;
    const y = height - ((v - min) / range) * (height - strokeWidth) - strokeWidth / 2;
    return [x, y] as const;
  });

  const line = points.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x},${y}`).join(" ");
  const area =
    fill && points.length > 1
      ? `${line} L${width},${height} L0,${height} Z`
      : "";

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={className}
      aria-hidden
    >
      {area && (
        <path
          d={area}
          fill={stroke}
          opacity={0.15}
        />
      )}
      <path
        d={line}
        fill="none"
        stroke={stroke}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
