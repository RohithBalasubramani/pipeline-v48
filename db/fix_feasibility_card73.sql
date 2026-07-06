-- db/fix_feasibility_card73.sql — refresh the stale card 73 feasibility verdict (db-data hardening, 2026-07-03).
-- Idempotent keyed UPDATE; safe to re-run.
--
-- Card 73 'Power Energy Analysis' (diesel-generator-asset-dashboard/operations-runtime, ROUTABLE) sat at
-- verdict='no_data' from feasibility_recompute rule (a): "renders from a byte-match default payload and has none ->
-- renders empty". The premise is stale: outputs/cert_results.jsonl shows the page certified 4/4 TWICE with card 73
-- ok=true honest_gap=false — a card with no card_payloads default still renders via the L2 AI-authored exact_metadata
-- envelope + the frontend registry (layer2/build.py only fails the card when BOTH the default payload AND the AI
-- exact_metadata are empty). card_payloads for 73 is still 0 rows (2026-07-03), so the REASON was factually current
-- but the VERDICT was wrong — and as the only no_data row it alone put the page at 0.25 of the 0.40
-- template-disqualification threshold in the 1a renderability gate (one more verdict row would silently unroute the
-- whole dg/operations-runtime template).
UPDATE card_feasibility SET
  verdict = 'render_real',
  reason = 'Renders WITHOUT a card_payloads default: L2 AI-authored exact_metadata + frontend registry cover it — certified ok=true honest_gap=false twice in outputs/cert_results.jsonl (dg/operations-runtime 4/4). card_payloads default still unharvested (0 rows, 2026-07-03) — a Storybook re-harvest (payload_db builder) remains nice-to-have, NOT a render requirement. Refreshed from the stale feasibility_recompute rule (a) no_data mark.'
WHERE card_id = 73 AND verdict = 'no_data';

-- GUARD (documentation, no DML): do NOT re-run layer2/catalog/feasibility_recompute.unrenderable()/recompute as-is —
-- a 2026-07-03 dry-run returns {60, 63, 73}: its rule (b) (asset_3d + neuract model_for None -> no_data) predates the
-- run_special/ViewerResolveResponse render path that the stored static_chrome verdicts for 60/63 already encode
-- [seed_feasibility_refresh rule R2], and rule (a) predates the AI-exact_metadata render path proven for 73 above.
-- Re-running it would REGRESS all three rows. The module needs a run_special exemption (code owner) before any rerun.
