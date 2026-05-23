-- Subject line variants table
CREATE TABLE IF NOT EXISTS subject_variants (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  subject_prompt TEXT NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Track which variant each outbound message used
ALTER TABLE messages
  ADD COLUMN IF NOT EXISTS subject_variant_id UUID REFERENCES subject_variants(id);

-- Index for fast variant analytics queries
CREATE INDEX IF NOT EXISTS idx_messages_subject_variant
  ON messages(subject_variant_id)
  WHERE subject_variant_id IS NOT NULL;

-- Seed two starter variants (Dante can rename / edit these after migration)
INSERT INTO subject_variants (name, subject_prompt) VALUES
  (
    'Variant A — Direct',
    'Generate a short, direct subject line (under 8 words) for a cold outreach email. No emojis. No clickbait. Make it sound like a personal note from one person to another.'
  ),
  (
    'Variant B — Curiosity',
    'Generate a short, curiosity-driven subject line (under 8 words) for a cold outreach email. No emojis. Should make the recipient curious enough to open without feeling tricked.'
  )
ON CONFLICT DO NOTHING;
