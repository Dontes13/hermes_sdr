import type { HookTier } from "@/lib/types";
import { HOOK_TIER_NAMES } from "@/lib/types";
import { cn } from "@/lib/utils";

const TIER_VAR: Record<HookTier, string> = {
  1: "var(--tier-1)",
  2: "var(--tier-2)",
  3: "var(--tier-3)",
  4: "var(--tier-4)",
  5: "var(--tier-5)",
};

interface HookTierBadgeProps {
  tier: HookTier | null | undefined;
  /** Show the tier name alongside the label (e.g., "T2 · Website Intel"). */
  showName?: boolean;
  /** Visual size. "sm" fits inline with list rows. */
  size?: "sm" | "md";
  className?: string;
}

export function HookTierBadge({
  tier,
  showName = false,
  size = "sm",
  className,
}: HookTierBadgeProps) {
  if (tier == null) {
    return (
      <span
        className={cn(
          "inline-flex items-center gap-1.5 font-mono uppercase tracking-wider text-text-mute",
          size === "sm" ? "text-[10px]" : "text-xs",
          className
        )}
      >
        <span className="h-[6px] w-[6px] rounded-full bg-border" />
        <span>—</span>
      </span>
    );
  }

  const color = TIER_VAR[tier];
  const label = `T${tier}`;
  const name = HOOK_TIER_NAMES[tier];

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 font-mono uppercase tracking-wider",
        size === "sm" ? "text-[10px]" : "text-xs",
        className
      )}
      style={{ color }}
    >
      <span
        aria-hidden
        className="h-[6px] w-[6px] rounded-full"
        style={{ backgroundColor: color }}
      />
      <span className="font-semibold">{label}</span>
      {showName && (
        <span className="text-text-dim normal-case tracking-normal">
          · {name}
        </span>
      )}
    </span>
  );
}
