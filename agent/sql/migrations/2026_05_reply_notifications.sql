-- Track whether a notification has been sent for an inbound reply
ALTER TABLE messages
  ADD COLUMN IF NOT EXISTS notification_sent_at TIMESTAMPTZ;

-- Add the notification recipient to config (idempotent — only insert if missing)
INSERT INTO config (key, value)
VALUES ('notify_email', 'heliosmarketingg@gmail.com')
ON CONFLICT (key) DO NOTHING;
