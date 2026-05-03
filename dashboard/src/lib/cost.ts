/**
 * Rough per-lead cost model for a campaign.
 *
 * Tuned from public pricing + typical token counts. This is a back-of-the-
 * envelope estimate, not a billing guarantee — actual spend depends on how
 * many leads die during enrich, Firecrawl fallback rate, and model pricing
 * changes. Easy to retune here if the ratio drifts.
 */

// USD per pipeline step, per lead surfaced (not per sent).
export const UNIT_COSTS = {
  /** Google Places Text Search (new): ~$0.032/call × ~3 calls per prospect
   *  page, amortized over ~20 surfaced candidates per tick. */
  places: 0.005,
  /** Gemini 2.5 Flash structured extraction: ~5–10K input tokens +
   *  optional Firecrawl fallback. */
  enrich: 0.002,
  /** Gemini 2.5 Pro draft generation: ~2K input + ~300 output tokens. */
  draft: 0.005,
  /** AgentMail: sends are bundled in plan in v1. Set to a non-zero value
   *  if you start metering it. */
  send: 0,
} as const;

/** Enrichment fires on every prospected lead, even ones that die with no
 *  email. We still pay for those Flash calls. Historical rate ≈ 30%
 *  die-off, so wasted enrich ≈ 1.4× of successfully-drafted leads. */
export const ENRICH_WASTE_FACTOR = 1.4;

/** Cost to take one lead all the way from prospect to sent. */
export function costPerLead(): number {
  return (
    UNIT_COSTS.places +
    UNIT_COSTS.enrich * ENRICH_WASTE_FACTOR +
    UNIT_COSTS.draft +
    UNIT_COSTS.send
  );
}

export interface CostEstimate {
  perLead: number;
  /** Total cost if the campaign runs to its lead cap. Null if uncapped. */
  total: number | null;
  /** Upper-bound cost for one full send-capped day. */
  perDay: number;
}

export function estimateCampaignCost(
  totalLeadCap: number | null | undefined,
  dailySendCap: number
): CostEstimate {
  const perLead = costPerLead();
  return {
    perLead,
    total: totalLeadCap ? totalLeadCap * perLead : null,
    perDay: dailySendCap * perLead,
  };
}

export function formatUsd(n: number): string {
  if (n < 1) return `$${n.toFixed(3)}`;
  if (n < 10) return `$${n.toFixed(2)}`;
  return `$${n.toFixed(0)}`;
}
