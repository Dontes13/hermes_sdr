-- Sprint Feature 4 — Email Warming

CREATE TABLE warming_schedule (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  inbox_id UUID NOT NULL REFERENCES inboxes(id),
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  current_day INTEGER NOT NULL DEFAULT 1,
  status TEXT NOT NULL DEFAULT 'warming'
    CHECK (status IN ('warming', 'complete', 'paused')),
  target_daily_limit INTEGER NOT NULL DEFAULT 40,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (inbox_id)
);

CREATE TABLE warming_sends (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  from_inbox_id UUID NOT NULL REFERENCES inboxes(id),
  to_inbox_id UUID NOT NULL REFERENCES inboxes(id),
  subject TEXT NOT NULL,
  body TEXT NOT NULL,
  sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  replied_at TIMESTAMPTZ,
  provider_thread_id TEXT,
  CHECK (from_inbox_id <> to_inbox_id)
);

CREATE INDEX idx_warming_sends_from_sent_at ON warming_sends (from_inbox_id, sent_at);
CREATE INDEX idx_warming_sends_provider_thread_id ON warming_sends (provider_thread_id)
  WHERE provider_thread_id IS NOT NULL;

-- Lets the sent_today query in _check_inbox_capacity exclude warming traffic.
-- Warming sends do not write to messages, so this is defensive/future-proofing.
ALTER TABLE messages
  ADD COLUMN IF NOT EXISTS is_warming BOOLEAN NOT NULL DEFAULT FALSE;
