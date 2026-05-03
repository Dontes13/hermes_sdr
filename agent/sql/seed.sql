INSERT INTO config (key, value) VALUES
  ('target_cities', 'Miami'),
  ('calendly_link', 'https://calendly.com/PLACEHOLDER/intro'),
  ('sender_name', 'Enrique'),
  ('sender_title', 'CTO, Helios Marketing'),
  ('daily_lead_cap', '15')
ON CONFLICT (key) DO NOTHING;
