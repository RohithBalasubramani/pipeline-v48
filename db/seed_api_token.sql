-- db/seed_api_token.sql — declares the api.token shared-secret knob [R6 partial, 2026-07-12]. DEFAULT OFF: seeded
-- EMPTY, so behavior is unchanged until an owner sets a real value. When non-empty, every host (:8770) + admin
-- (:8790) request must carry a matching X-V48-Token header (lib/api_auth.require_token, read lazily per request)
-- or the server responds 401 early. ON CONFLICT DO NOTHING — never overwrites an operator-set token. NOT applied
-- automatically (owner-gated). Run: psql -h localhost -p 5432 -d cmd_catalog -f db/seed_api_token.sql
INSERT INTO app_config (key, value, data_type, section, note) VALUES
  ('api.token', '', 'text', 'api',
   'Shared secret for the V48 HTTP surfaces (host :8770 + admin :8790). Empty = auth DISABLED (default, today''s '
   'behavior). Non-empty = every request must send a matching X-V48-Token header or gets 401. Read lazily per '
   'request (lib/api_auth.py) — editing the row takes effect on the next request, no restart.')
ON CONFLICT (key) DO NOTHING;
