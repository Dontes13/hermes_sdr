-- Feature 2: Inbox Capacity Tracking
-- Creates the inboxes table, adds messages.inbox_id, seeds the production
-- inbox from agentmail_sync, and backfills all historical outbound messages.

CREATE TABLE IF NOT EXISTS inboxes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT NOT NULL UNIQUE,
  agentmail_inbox_id TEXT NOT NULL UNIQUE,
  daily_send_limit INTEGER NOT NULL DEFAULT 40,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Sender attribution column on messages
ALTER TABLE messages
  ADD COLUMN IF NOT EXISTS inbox_id UUID REFERENCES inboxes(id);

-- Index for the per-inbox sent_today capacity query
CREATE INDEX IF NOT EXISTS idx_messages_inbox_sent_at
  ON messages (inbox_id, created_at)
  WHERE direction = 'outbound';

-- Seed the production inbox by reading agentmail_inbox_id from agentmail_sync,
-- then backfill all existing outbound messages.
-- Before running: replace 'CONFIGURE_THIS_EMAIL@placeholder.invalid' with the
-- real inbox address (e.g. enrique@agentmail.to). Everything else is automatic.
DO $$
DECLARE
  v_agentmail_inbox_id TEXT;
  v_inbox_uuid         UUID;
BEGIN
  SELECT inbox_id
    INTO v_agentmail_inbox_id
    FROM agentmail_sync
   WHERE id = 1;

  IF v_agentmail_inbox_id IS NOT NULL THEN
    INSERT INTO inboxes (email, agentmail_inbox_id, daily_send_limit)
    VALUES ('CONFIGURE_THIS_EMAIL@placeholder.invalid', v_agentmail_inbox_id, 40)
    ON CONFLICT (agentmail_inbox_id) DO NOTHING;

    SELECT id
      INTO v_inbox_uuid
      FROM inboxes
     WHERE agentmail_inbox_id = v_agentmail_inbox_id;

    -- Backfill every historical outbound message so capacity counts are accurate
    IF v_inbox_uuid IS NOT NULL THEN
      UPDATE messages
         SET inbox_id = v_inbox_uuid
       WHERE inbox_id IS NULL;
    END IF;
  END IF;
END;
$$;
