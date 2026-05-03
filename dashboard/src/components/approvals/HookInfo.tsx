import { HOOK_TIER_NAMES, type HookTier } from "@/lib/types";
import { HookTierBadge } from "@/components/shared/HookTierBadge";

interface HookInfoProps {
  tier: HookTier | null;
  hookText: string | null;
  rationale: string | null;
}

export function HookInfo({ tier, hookText, rationale }: HookInfoProps) {
  return (
    <div className="border border-border bg-surface">
      <div className="flex items-center gap-2 border-b border-border px-4 py-2 font-mono text-[10px] uppercase tracking-[0.2em] text-text-mute">
        <span>Why this hook</span>
      </div>
      <div className="px-5 py-4 space-y-3">
        <div className="flex items-center gap-3">
          <HookTierBadge tier={tier} size="md" />
          {tier != null && (
            <span className="text-sm text-text-dim">
              {HOOK_TIER_NAMES[tier]}
            </span>
          )}
        </div>

        {hookText && (
          <div className="space-y-1">
            <div className="font-mono text-[10px] uppercase tracking-wider text-text-mute">
              Led with
            </div>
            <div className="text-sm text-text italic">&ldquo;{hookText}&rdquo;</div>
          </div>
        )}

        {rationale && (
          <div className="space-y-1">
            <div className="font-mono text-[10px] uppercase tracking-wider text-text-mute">
              Rationale
            </div>
            <div className="text-sm text-text-dim leading-relaxed">
              {rationale}
            </div>
          </div>
        )}

        {!hookText && !rationale && (
          <div className="text-xs text-text-mute italic">
            No hook metadata recorded.
          </div>
        )}
      </div>
    </div>
  );
}
