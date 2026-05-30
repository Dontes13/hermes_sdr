-- Sprint: Apollo sourcing — lead source tag + apollo_id dedup index
--
-- Run manually in the Supabase SQL editor (Run without RLS), per Hermes
-- convention. There is no automatic migration runner.

ALTER TABLE leads
  ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'google_places'
    CHECK (source IN ('google_places','apollo'));

-- ADD COLUMN ... NOT NULL DEFAULT backfills every existing row with
-- 'google_places' automatically. The explicit UPDATE below is a harmless
-- safety net for any pre-existing NULLs (no-op on a clean apply).
UPDATE leads SET source = 'google_places' WHERE source IS NULL;

-- Dedup key for Apollo-sourced leads. apollo_id lives inside intel_json
-- (no new top-level column). Partial + unique so it constrains only Apollo
-- rows and ignores the Google Places rows that have no apollo_id.
-- Mirrors the existing leads_place_id_idx pattern in schema.sql.
CREATE UNIQUE INDEX IF NOT EXISTS leads_apollo_id_idx
  ON leads ((intel_json->>'apollo_id'))
  WHERE source = 'apollo' AND intel_json->>'apollo_id' IS NOT NULL;
