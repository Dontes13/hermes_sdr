-- Sprint Feature 3 — ICP scoring columns
ALTER TABLE leads
  ADD COLUMN IF NOT EXISTS icp_score INTEGER,
  ADD COLUMN IF NOT EXISTS icp_score_reasons JSONB,
  ADD COLUMN IF NOT EXISTS vertical TEXT;

CREATE INDEX IF NOT EXISTS idx_leads_icp_score ON leads (icp_score DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_leads_vertical ON leads (vertical);

-- Backfill vertical for all existing leads from intel_json.types.
-- Priority: real_estate_agency wins; then any type containing "restaurant" or "food";
-- fallback "other". Leads with no intel_json or empty types array → "other".
UPDATE leads
SET vertical = CASE
  WHEN intel_json->'types' @> '["real_estate_agency"]'::jsonb
    THEN 'real_estate'
  WHEN EXISTS (
    SELECT 1
    FROM jsonb_array_elements_text(COALESCE(intel_json->'types', '[]'::jsonb)) AS t
    WHERE t LIKE '%restaurant%' OR t LIKE '%food%'
  )
    THEN 'restaurant'
  ELSE 'other'
END
WHERE vertical IS NULL;
