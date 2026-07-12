-- db/seed_feasibility_marks.sql — the RENDERABILITY GATE data-mark (asset + EMS pages). Idempotent UPSERT.
--
-- Marks the cards that render EMPTY *regardless of the new renderers* as card_feasibility.verdict='no_data' (+ reason),
-- so Layer 2's per-card enforcer force-swaps them and Layer 1a can drop a too-unrenderable template. This is the DATA
-- side of the gate; the code side is layer2/catalog/feasibility_recompute.py (which computes this SAME set live and is
-- re-runnable as payloads/3D models land). feasibility.py (read-only, owned elsewhere) is untouched.
--
-- CONSERVATIVE rule (only provably-empty families):
--   (a) NO card_payloads row AND handling_class NOT IN (narrative_ai, topology_sld, panel_aggregate, nav_index)
--        -> renders from a harvested default payload; with none, empty.  [30 cards]
--   (b) handling_class='asset_3d' AND data.neuract_live.model_for(<asset key>) is None (neuract has 0 3D models)
--        -> the viewer mounts ComingSoon (empty).  [2 cards]
-- NOT marked (per rule): single_asset WITH a payload, panel_aggregate, topology_sld, narrative_ai.
--
-- family / required_topology / required_mesh are PRESERVED (ON CONFLICT updates verdict+reason only). PK = card_id.
-- Run:  psql -h localhost -p 5432 -d cmd_catalog -f db/seed_feasibility_marks.sql
-- Regenerate identically:  python -m layer2.catalog.feasibility_recompute   (dry-run report) then recompute_feasibility().

INSERT INTO card_feasibility (card_id, verdict, reason) VALUES
  (50, 'no_data', $fx$No card_payloads default harvested for this single_asset_derived card (page ups-asset-dashboard/battery-autonomy); it renders from a byte-match default payload and has none -> renders empty. [feasibility_recompute rule a]$fx$),
  (51, 'no_data', $fx$No card_payloads default harvested for this single_asset_series card (page ups-asset-dashboard/battery-autonomy); it renders from a byte-match default payload and has none -> renders empty. [feasibility_recompute rule a]$fx$),
  (52, 'no_data', $fx$No card_payloads default harvested for this single_asset_derived card (page ups-asset-dashboard/battery-autonomy); it renders from a byte-match default payload and has none -> renders empty. [feasibility_recompute rule a]$fx$),
  (53, 'no_data', $fx$No card_payloads default harvested for this single_asset_derived card (page ups-asset-dashboard/battery-autonomy); it renders from a byte-match default payload and has none -> renders empty. [feasibility_recompute rule a]$fx$),
  (54, 'no_data', $fx$No card_payloads default harvested for this single_asset_derived card (page ups-asset-dashboard/source-transfer); it renders from a byte-match default payload and has none -> renders empty. [feasibility_recompute rule a]$fx$),
  (55, 'no_data', $fx$No card_payloads default harvested for this single_asset_series card (page ups-asset-dashboard/source-transfer); it renders from a byte-match default payload and has none -> renders empty. [feasibility_recompute rule a]$fx$),
  (56, 'no_data', $fx$No card_payloads default harvested for this single_asset_series card (page ups-asset-dashboard/source-transfer); it renders from a byte-match default payload and has none -> renders empty. [feasibility_recompute rule a]$fx$),
  (57, 'no_data', $fx$No card_payloads default harvested for this single_asset_derived card (page ups-asset-dashboard/output-load-capacity); it renders from a byte-match default payload and has none -> renders empty. [feasibility_recompute rule a]$fx$),
  (58, 'no_data', $fx$No card_payloads default harvested for this single_asset_derived card (page ups-asset-dashboard/output-load-capacity); it renders from a byte-match default payload and has none -> renders empty. [feasibility_recompute rule a]$fx$),
  (59, 'no_data', $fx$No card_payloads default harvested for this single_asset_series card (page ups-asset-dashboard/output-load-capacity); it renders from a byte-match default payload and has none -> renders empty. [feasibility_recompute rule a]$fx$),
  (60, 'no_data', $fx$asset_3d card with no 3D model in the neuract registry (model_for('diesel_generator') is None) -> the viewer mounts ComingSoon (empty). [feasibility_recompute rule b]$fx$),
  (61, 'no_data', $fx$No card_payloads default harvested for this single_asset_derived card (page diesel-generator-asset-dashboard/engine-cooling); it renders from a byte-match default payload and has none -> renders empty. [feasibility_recompute rule a]$fx$),
  (62, 'no_data', $fx$No card_payloads default harvested for this single_asset_derived card (page diesel-generator-asset-dashboard/engine-cooling); it renders from a byte-match default payload and has none -> renders empty. [feasibility_recompute rule a]$fx$),
  (63, 'no_data', $fx$asset_3d card with no 3D model in the neuract registry (model_for('diesel_generator') is None) -> the viewer mounts ComingSoon (empty). [feasibility_recompute rule b]$fx$),
  (64, 'no_data', $fx$No card_payloads default harvested for this single_asset_series card (page diesel-generator-asset-dashboard/fuel-efficiency); it renders from a byte-match default payload and has none -> renders empty. [feasibility_recompute rule a]$fx$),
  (65, 'no_data', $fx$No card_payloads default harvested for this single_asset_series card (page diesel-generator-asset-dashboard/fuel-efficiency); it renders from a byte-match default payload and has none -> renders empty. [feasibility_recompute rule a]$fx$),
  (66, 'no_data', $fx$No card_payloads default harvested for this single_asset_derived card (page diesel-generator-asset-dashboard/voltage-current); it renders from a byte-match default payload and has none -> renders empty. [feasibility_recompute rule a]$fx$),
  (67, 'no_data', $fx$No card_payloads default harvested for this single_asset_series card (page diesel-generator-asset-dashboard/voltage-current); it renders from a byte-match default payload and has none -> renders empty. [feasibility_recompute rule a]$fx$),
  (68, 'no_data', $fx$No card_payloads default harvested for this single_asset_derived card (page diesel-generator-asset-dashboard/voltage-current); it renders from a byte-match default payload and has none -> renders empty. [feasibility_recompute rule a]$fx$),
  (69, 'no_data', $fx$No card_payloads default harvested for this single_asset_series card (page diesel-generator-asset-dashboard/voltage-current); it renders from a byte-match default payload and has none -> renders empty. [feasibility_recompute rule a]$fx$),
  (70, 'no_data', $fx$No card_payloads default harvested for this single_asset_derived card (page diesel-generator-asset-dashboard/operations-runtime); it renders from a byte-match default payload and has none -> renders empty. [feasibility_recompute rule a]$fx$),
  (71, 'no_data', $fx$No card_payloads default harvested for this single_asset_series card (page diesel-generator-asset-dashboard/operations-runtime); it renders from a byte-match default payload and has none -> renders empty. [feasibility_recompute rule a]$fx$),
  (72, 'no_data', $fx$No card_payloads default harvested for this single_asset_derived card (page diesel-generator-asset-dashboard/operations-runtime); it renders from a byte-match default payload and has none -> renders empty. [feasibility_recompute rule a]$fx$),
  (73, 'no_data', $fx$No card_payloads default harvested for this single_asset_series card (page diesel-generator-asset-dashboard/operations-runtime); it renders from a byte-match default payload and has none -> renders empty. [feasibility_recompute rule a]$fx$),
  (74, 'no_data', $fx$No card_payloads default harvested for this single_asset_derived card (page transformer-asset-dashboard/thermal-life); it renders from a byte-match default payload and has none -> renders empty. [feasibility_recompute rule a]$fx$),
  (75, 'no_data', $fx$No card_payloads default harvested for this single_asset_series card (page transformer-asset-dashboard/thermal-life); it renders from a byte-match default payload and has none -> renders empty. [feasibility_recompute rule a]$fx$),
  (76, 'no_data', $fx$No card_payloads default harvested for this single_asset_series card (page transformer-asset-dashboard/thermal-life); it renders from a byte-match default payload and has none -> renders empty. [feasibility_recompute rule a]$fx$),
  (77, 'no_data', $fx$No card_payloads default harvested for this single_asset_derived card (page transformer-asset-dashboard/thermal-life); it renders from a byte-match default payload and has none -> renders empty. [feasibility_recompute rule a]$fx$),
  (78, 'no_data', $fx$No card_payloads default harvested for this single_asset_derived card (page transformer-asset-dashboard/tap-rtcc); it renders from a byte-match default payload and has none -> renders empty. [feasibility_recompute rule a]$fx$),
  (79, 'no_data', $fx$No card_payloads default harvested for this single_asset_series card (page transformer-asset-dashboard/tap-rtcc); it renders from a byte-match default payload and has none -> renders empty. [feasibility_recompute rule a]$fx$),
  (80, 'no_data', $fx$No card_payloads default harvested for this single_asset_series card (page transformer-asset-dashboard/tap-rtcc); it renders from a byte-match default payload and has none -> renders empty. [feasibility_recompute rule a]$fx$),
  (81, 'no_data', $fx$No card_payloads default harvested for this single_asset_derived card (page transformer-asset-dashboard/tap-rtcc); it renders from a byte-match default payload and has none -> renders empty. [feasibility_recompute rule a]$fx$)
ON CONFLICT (card_id) DO UPDATE SET verdict = EXCLUDED.verdict, reason = EXCLUDED.reason;
