-- db/seed_chiller_routing.sql — extend the DB-driven feeder_generic routing rule to the all-electrical Chiller/Compressor
-- meters (BATCH D #14). The AHU/Chiller/Compressor MFMs are pure-electrical 70-col meters with real data (verified live:
-- gic_25_n11_ahu_01_ng / gic_26_n10_og_air_compressor_1_ng); asset_candidates._CLASS_SQL already tags them class=Chiller
-- / class=Compressor, and class_from_subject._CONCEPT_HINTS already maps 'chiller'/'compressor' subjects to those classes.
-- feeder_generic already covered class=Panel/AHU/Fan/Pump; cards #130 (loadPct → energy-power) and #132 (Voltage &
-- Current → voltage-current) stayed UNROUTED only because Chiller/Compressor were absent from the selector. This adds the
-- two class clauses so those meters route to the individual-feeder-meter-shell energy-power | voltage-current cards.
--
-- POLICY, not code: the routing rule is the EDITABLE render_guarantee_matrix.feeder_generic row (cmd_catalog); this file
-- only re-sets its asset_selector to include the extra OR-clauses. Read back by config/prompt_matrix.py (match_selector).
-- Idempotent — it UPDATEs the one existing row to a fixed selector string; re-running sets the SAME value. It does NOT
-- INSERT a new tag (the render-guarantee suite keys off tag=feeder_generic). No consumer code changes — routing only.
-- Run AFTER db/render_guarantee_seed.sql:  psql -h localhost -p 5432 -d cmd_catalog -f db/seed_chiller_routing.sql
-- Optional-but-recommended: with the DB unseeded, feeder_generic simply keeps its prior class set (no Chiller/Compressor).

UPDATE render_guarantee_matrix
   SET asset_selector = 'class=Panel&has_data|class=AHU&has_data|class=Fan&has_data|class=Pump&has_data'
                        || '|class=Chiller&has_data|class=Compressor&has_data',
       note           = 'RN-01/05: non-UPS loading%% / section (Panel/AHU/Fan/Pump + Chiller/Compressor all-electrical) [BATCH D #14]'
 WHERE tag = 'feeder_generic';

-- Safety net: if render_guarantee_seed.sql has not been applied yet (no feeder_generic row to UPDATE), INSERT the row
-- already carrying the Chiller/Compressor clauses so routing is complete either way. ON CONFLICT keeps this idempotent.
INSERT INTO render_guarantee_matrix (tag, asset_selector, asset_name_hint, page_glob, time_window, phrasing, note) VALUES
 ('feeder_generic',
  'class=Panel&has_data|class=AHU&has_data|class=Fan&has_data|class=Pump&has_data|class=Chiller&has_data|class=Compressor&has_data',
  'GIC-05-N3-FCBC',
  'individual-feeder-meter-shell/energy-power|individual-feeder-meter-shell/voltage-current',
  '',
  '{page} {a}',
  'RN-01/05: non-UPS loading%% / section (Panel/AHU/Fan/Pump + Chiller/Compressor all-electrical) [BATCH D #14]')
ON CONFLICT (tag) DO UPDATE SET asset_selector = EXCLUDED.asset_selector,
    page_glob = EXCLUDED.page_glob, phrasing = EXCLUDED.phrasing, note = EXCLUDED.note;
