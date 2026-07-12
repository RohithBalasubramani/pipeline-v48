-- db/seed_feasibility_refresh.sql — the STALE-VERDICT refresh for the 9 asset deep-tab pages (cards 50-81).
-- [Evidence-B audit 2026-07-02; reproducible per the DB-driven config rule]
--
-- WHY the verdicts went stale: layer2/catalog/feasibility_recompute.py rule (a) checks for a NON-subcard
-- card_payloads row `WHERE card_id=? AND page_key=<the card's page>`; the ASSETS harvest
-- (payload_db/load_asset_payloads.py) inserted the 30 asset-card payload rows with page_key=NULL, so the
-- lookup missed them and every payload-backed asset card was stamped 'no_data' — even though the byte-match
-- defaults ARE harvested. The two asset_3d cards (60, 63) were stamped 'no_data' by rule (b)
-- (data.neuract_live.assets3d.model_for → None: the neuract lt_asset_3d/asset_3d_model tables are empty),
-- but an asset_3d card renders OUTSIDE the payload path via ems_exec/renderers/asset_3d.py run_special —
-- the ViewerResolveResponse envelope always mounts (object=null → the FE's ComingSoon3D chrome), which is
-- exactly the 'static_chrome' verdict (config/feasibility.py: renderable, NOT unrenderable) already used by
-- the same-family cards 3/83/85/98/122/...
--
-- DERIVATION RULE (per card on the 9 asset pages, all currently verdict='no_data'):
--   R0  card_payloads.page_key repair — the root cause: fill the NULL page_key on the 30 non-subcard ASSETS
--       payload rows from page_layout_cards (the card's canonical shell/tab page_key). The harvester's
--       ON CONFLICT clause does NOT touch page_key, so a re-harvest cannot clobber this back to NULL.
--   R1  single-asset card WITH a harvested byte-match default on its own page (post-R0) AND electrical data
--       (UPS/DG/Transformer V-I-kW-kWh feeds)                         → verdict 'render_real'.
--   R2  asset_3d card (handling_class='asset_3d'): renders via run_special (viewer envelope, no payload
--       dependency); no neuract 3D model yet → chrome + ComingSoon mounts → verdict 'static_chrome'
--       (honest: renders SOMETHING, counts toward the page, not unrenderable). Flip to 'render_real' only
--       when a neuract lt_asset_3d/asset_3d_model row lands for the DG/transformer/UPS keys.
--   R3  KEEP (not touched): a genuinely-domain card with NO payload (own or sibling) stays at its honest
--       verdict — card 73 'Power Energy Analysis' (primary component PowerEnergyAnalysisPanel, no harvested
--       story, no sibling card sharing that primary component) stays 'no_data'. Its page
--       diesel-generator-asset-dashboard/operations-runtime is still KEPT by the gate (1/4 = 25% < 40%).
--
-- IDEMPOTENT + NON-CLOBBERING: R0 fills only NULL/'' page_key; R1/R2 flip only rows still carrying a
-- '[feasibility_recompute ...]' or '[seed_feasibility_refresh ...]' stamped reason (mirrors the recompute
-- marker's own never-clobber-a-hand-set-verdict convention). Safe to re-run any number of times.
-- Run:  psql -h 127.0.0.1 -p 5432 -U postgres -d cmd_catalog -f db/seed_feasibility_refresh.sql
--
-- KNOWN GOTCHA (report-only, code untouched): feasibility_recompute rule (b)'s APPLY side would re-stamp
-- cards 60/63 back to 'no_data' on a future recompute run for as long as the neuract model tables stay
-- empty; re-apply this file after any recompute run (or land the neuract 3D rows) to restore the honest
-- static_chrome marks.

-- ── R0: repair the harvested ASSETS payload rows' page_key (root cause of rule-(a) misses) ─────────────────
UPDATE card_payloads cp
SET    page_key = plc.page_key
FROM   page_layout_cards plc
WHERE  plc.card_id = cp.card_id
  AND  cp.card_id BETWEEN 50 AND 81
  AND  cp.is_subcard = false
  AND  (cp.page_key IS NULL OR cp.page_key = '');

-- ── R1: payload-backed single-asset cards → render_real (guarded by the ACTUAL payload row, never asserted) ─
UPDATE card_feasibility cf
SET    verdict = 'render_real',
       reason  = 'Byte-match default payload harvested (card_payloads.page_key repaired from page_layout_cards) '
                 || 'and the asset carries electrical data -> renders real. [seed_feasibility_refresh rule R1]'
WHERE  cf.card_id BETWEEN 50 AND 81
  AND  (cf.reason LIKE '%[feasibility_recompute%' OR cf.reason LIKE '%[seed_feasibility_refresh%')
  AND  NOT EXISTS (SELECT 1 FROM card_handling ch
                   WHERE ch.card_id = cf.card_id AND ch.handling_class = 'asset_3d')
  AND  EXISTS (SELECT 1
               FROM card_payloads cp
               JOIN page_layout_cards plc ON plc.card_id = cp.card_id
               WHERE cp.card_id = cf.card_id
                 AND cp.is_subcard = false
                 AND cp.page_key = plc.page_key);

-- ── R2: asset_3d special-render cards → static_chrome (viewer chrome mounts via run_special; honest) ────────
UPDATE card_feasibility cf
SET    verdict = 'static_chrome',
       reason  = 'asset_3d card renders via ems_exec run_special: the ViewerResolveResponse envelope mounts the '
                 || 'viewer chrome (object=null -> ComingSoon3D until a neuract lt_asset_3d/asset_3d_model row '
                 || 'lands) -> renders SOMETHING, not unrenderable. [seed_feasibility_refresh rule R2]'
WHERE  cf.card_id BETWEEN 50 AND 81
  AND  (cf.reason LIKE '%[feasibility_recompute%' OR cf.reason LIKE '%[seed_feasibility_refresh%')
  AND  EXISTS (SELECT 1 FROM card_handling ch
               WHERE ch.card_id = cf.card_id AND ch.handling_class = 'asset_3d');

-- (R3 is a deliberate NO-OP: card 73 keeps its honest 'no_data' — no payload, no sibling, see header.)
