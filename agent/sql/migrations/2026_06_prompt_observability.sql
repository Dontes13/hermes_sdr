-- Prompt observability: capture the full rendered string sent to Gemini per draft.
-- body_prompt / subject_prompt store the post-Jinja strings (Helios KB + lead
-- briefing + all rules concatenated) that actually hit Gemini for each draft.
CREATE TABLE IF NOT EXISTS message_prompts (
  message_id uuid PRIMARY KEY REFERENCES messages(id) ON DELETE CASCADE,
  body_prompt text NOT NULL,
  subject_prompt text,
  model text,
  subject_variant_id uuid,
  created_at timestamptz NOT NULL DEFAULT now()
);
