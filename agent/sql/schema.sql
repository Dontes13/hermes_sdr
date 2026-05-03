-- Trigger function: auto-update updated_at on row change
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Leads table
CREATE TABLE IF NOT EXISTS leads (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company text NOT NULL,
  city text NOT NULL,
  website text,
  email text,
  owner_name text,
  phone text,
  google_rating numeric,
  google_reviews int,
  intel_json jsonb NOT NULL DEFAULT '{}'::jsonb,
  status text NOT NULL DEFAULT 'new'
    CHECK (status IN ('new','enriched','drafted','approved','sent',
                      'replied','booked','dead','unsubscribed')),
  briefing_md text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Unique partial index on place_id within intel_json
CREATE UNIQUE INDEX IF NOT EXISTS leads_place_id_idx
  ON leads ((intel_json->>'place_id'))
  WHERE intel_json->>'place_id' IS NOT NULL;

CREATE INDEX IF NOT EXISTS leads_status_idx ON leads(status);
CREATE INDEX IF NOT EXISTS leads_city_idx ON leads(city);

-- Auto-update updated_at trigger
CREATE OR REPLACE TRIGGER leads_updated_at
  BEFORE UPDATE ON leads
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at();

-- Messages table
CREATE TABLE IF NOT EXISTS messages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id uuid NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  direction text NOT NULL CHECK (direction IN ('outbound','inbound')),
  subject text,
  body text NOT NULL,
  hook_tier_used int,
  hook_text text,
  hook_rationale text,
  provider_msg_id text,
  provider_thread_id text,
  sent_at timestamptz,
  is_test boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- Idempotent add: if the column didn't exist on older schemas, add it now.
ALTER TABLE messages ADD COLUMN IF NOT EXISTS is_test boolean NOT NULL DEFAULT false;

CREATE INDEX IF NOT EXISTS messages_lead_id_idx ON messages(lead_id);

-- Config table
CREATE TABLE IF NOT EXISTS config (
  key text PRIMARY KEY,
  value text NOT NULL
);

-- Migrate legacy gmail-specific column names to provider-agnostic names.
-- Idempotent: no-ops on fresh schemas where the new names already exist.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'messages' AND column_name = 'gmail_msg_id'
  ) THEN
    ALTER TABLE messages RENAME COLUMN gmail_msg_id TO provider_msg_id;
  END IF;

  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'messages' AND column_name = 'gmail_thread_id'
  ) THEN
    ALTER TABLE messages RENAME COLUMN gmail_thread_id TO provider_thread_id;
  END IF;
END $$;

-- Drop the legacy Gmail sync table and its index (if they exist)
DROP INDEX IF EXISTS messages_gmail_thread_idx;
DROP TABLE IF EXISTS gmail_sync;

-- AgentMail sync state (single-row table: cached inbox_id + polling cursor)
CREATE TABLE IF NOT EXISTS agentmail_sync (
  id int PRIMARY KEY DEFAULT 1,
  inbox_id text,
  last_polled_at timestamptz,
  CONSTRAINT single_row CHECK (id = 1)
);

INSERT INTO agentmail_sync (id) VALUES (1) ON CONFLICT DO NOTHING;

-- Indexes for thread lookups and message ordering
CREATE INDEX IF NOT EXISTS messages_provider_thread_idx
  ON messages(provider_thread_id)
  WHERE provider_thread_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS messages_sent_at_idx
  ON messages(sent_at)
  WHERE sent_at IS NOT NULL;

-- Campaigns table: defines an autonomous run for a (city, target) pair.
-- tick_running_at is the advisory lock; a worker claims a campaign by
-- conditionally setting it to now() iff it's NULL or older than 10 minutes.
CREATE TABLE IF NOT EXISTS campaigns (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  city text NOT NULL,
  target text NOT NULL,
  sample_email text,
  status text NOT NULL DEFAULT 'active'
    CHECK (status IN ('active','paused','completed','archived')),
  autonomy text NOT NULL DEFAULT 'full'
    CHECK (autonomy IN ('full','review_drafts')),
  daily_send_cap int NOT NULL DEFAULT 15,
  total_lead_cap int,
  tick_running_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS campaigns_status_idx ON campaigns(status);

CREATE OR REPLACE TRIGGER campaigns_updated_at
  BEFORE UPDATE ON campaigns
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at();

-- Link leads to campaigns. ON DELETE SET NULL so archiving a campaign
-- preserves its lead history.
ALTER TABLE leads ADD COLUMN IF NOT EXISTS campaign_id uuid REFERENCES campaigns(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS leads_campaign_idx ON leads(campaign_id);

-- Chat sessions for the assistant. messages is a jsonb array of turns;
-- pending_action holds a single at-a-time action awaiting confirmation.
CREATE TABLE IF NOT EXISTS chat_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  messages jsonb NOT NULL DEFAULT '[]'::jsonb,
  pending_action jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE OR REPLACE TRIGGER chat_sessions_updated_at
  BEFORE UPDATE ON chat_sessions
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at();

-- ────────────────────────────────────────────────────────────────────────
-- LinkedIn channel (added 2026-04-26)
-- Email pipeline stays the source of truth; LinkedIn is a parallel channel
-- expressed as metadata on existing messages rows + a few new lead columns.
-- ────────────────────────────────────────────────────────────────────────

-- Channel + provider on messages. Backfill 'email'/'agentmail' for old rows.
ALTER TABLE messages
  ADD COLUMN IF NOT EXISTS channel text NOT NULL DEFAULT 'email'
    CHECK (channel IN ('email','linkedin_invite','linkedin_dm'));

ALTER TABLE messages
  ADD COLUMN IF NOT EXISTS provider text NOT NULL DEFAULT 'agentmail'
    CHECK (provider IN ('agentmail','unipile'));

CREATE INDEX IF NOT EXISTS messages_channel_idx ON messages(channel);

-- LinkedIn fields on leads. linkedin_state is null until we attempt an
-- invite; followup_eligible_at is set when an email is sent (sent_at + N days).
ALTER TABLE leads
  ADD COLUMN IF NOT EXISTS linkedin_url text;

ALTER TABLE leads
  ADD COLUMN IF NOT EXISTS linkedin_state text
    CHECK (linkedin_state IN ('invite_sent','connected','declined','withdrawn'));

ALTER TABLE leads
  ADD COLUMN IF NOT EXISTS linkedin_followup_eligible_at timestamptz;

CREATE INDEX IF NOT EXISTS leads_linkedin_eligible_idx
  ON leads(linkedin_followup_eligible_at)
  WHERE linkedin_followup_eligible_at IS NOT NULL
    AND linkedin_state IS NULL;

CREATE INDEX IF NOT EXISTS leads_linkedin_state_idx
  ON leads(linkedin_state)
  WHERE linkedin_state IS NOT NULL;

-- Unipile sync state (cursors for invite-status + chat-message polling)
CREATE TABLE IF NOT EXISTS unipile_sync (
  id int PRIMARY KEY DEFAULT 1,
  account_id text,
  last_chat_polled_at timestamptz,
  last_invite_polled_at timestamptz,
  CONSTRAINT unipile_sync_single_row CHECK (id = 1)
);

INSERT INTO unipile_sync (id) VALUES (1) ON CONFLICT DO NOTHING;
