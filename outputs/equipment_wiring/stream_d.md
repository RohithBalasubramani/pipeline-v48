# Stream D — 3D kitpreview fallback (equipment schema)

Status: DONE (2026-07-08). 15 new tests + 31 existing seam tests green; seeds applied live; all knobs ship OFF.

## What shipped
- `data/equipment/kitpreview.py` (NEW) — `resolve_model(equipment_key, panel_type_code, asset_type_code, rating,
  page_type)` over equipment.kitpreview_viewer_rule ⋈ kitpreview_cat_asset, most-specific-first exactly per backend2
  core/resolver.py resolve_binding: for_key > for_type+rating > for_type(rating wildcard) > app_kv
  default_panel_model ('individual' page family + PANEL-typed nodes only). Empty-string for_key/rating = wildcards;
  rules page_type-scoped ('' matches any). Returns {slug, label, glb_file, default_overrides, template, rule_preset}
  (rule_preset kept SEPARATE per pinned API). `viewer_defaults()` (app_kv JSON, {} on miss). `config_rating(node_id)`
  (equipment_config.rating, 1/120 populated, fail-open None) — additive to the pinned API because the single-door
  rule pins that SQL to data/equipment/*. The cat_asset `url` column is NEVER read (33 dead-host + 21 empty).
  Everything fail-open None/{} via db.eq_q, never raises, never caches failures.
- `layer2/emit/metadata/asset_3d.py` — `_tier_kitpreview(asset_table, page_type)` as the FIFTH tier in
  `_resolve_object` (the 4 lt_asset_3d tiers WIN whenever they bind). Chain: asset table → stream A
  `bridge.identity_node(table)` (the ONLY node source — identity-unverified → null; lazy import under a BROAD
  `except Exception`, so a missing/half-built wave-1 bridge degrades to today's null) → config_rating →
  resolve_model → DEFAULT-DENY local-file gate → object {slug, label, url, rating, preset, default_overrides,
  template}. `_resolve_object` now returns `(obj, gap_cause)`; emit adds an additive `cause` key
  ('glb_not_in_media_root') to the reason dict ONLY when a kit-preview model resolved but the file gate denied.
  obj['preset'] = deep_merge(default_overrides, rule.preset) (rule wins per leaf) — the renderer's existing
  `_asset_preset` chain (viewer → preset → default_overrides) honours it with zero preset-side renderer change.
- `ems_exec/renderers/asset_3d.py` — two minimal additive edits: (1) top-level `template` envelope key when the
  object carries one (omitted otherwise — byte-identical today); (2) the GAPS_KEY cause prefers the resolver's
  specific `cause` over the generic 'no_3d_model'.
- `db/seed_equipment_3d.sql` — `equipment.kitpreview.enabled='off'` + `equipment.kitpreview.media_base=''`
  (data_type='text', section='equipment', ON CONFLICT (key) DO NOTHING — reseeding never flips the kill-switch).
  APPLIED LIVE on cmd_catalog :5432 (2 rows inserted, verified off/'').
- `tests/test_equipment_3d.py` — 15 tests, ALL :5432-local (neuract reads monkeypatched deterministic-miss;
  passes with :5433 down). Covers: rule ranking on the REAL rows (for_key wins; 630A variant beats wildcard;
  unknown rating falls to wildcard; page_type scoping ahu vs ahu-overview; default_panel_model individual+panel
  only), accessors + misses, outage never-raises (kitpreview + end-to-end emit), TIER ORDER (a bound neuract tier
  → tier 5 NEVER consulted, identity_node call-count 0), fallback fires end-to-end (emit object + renderer
  envelope: served http url — never the checked FS path, merged preset reaches the viewer look, template
  pass-through), no-rule-match → today's reason dict (no cause), identity-unverified → null, KNOB-OFF
  byte-identity (result == pre-feature baseline dict + bridge never consulted), DEFAULT-DENY (unset root /
  remote-looking root / file absent → cause 'glb_not_in_media_root' + renderer GAPS cause + template key
  OMITTED), half-built-bridge (raising attr + ImportError) never raises, path-traversal guard.

## Verified facts (re-checked live on :5432 before coding)
- kitpreview_cat_asset: 55 rows, 39 glb_file, 25 template; slug UNIQUE. viewer_rule: 49 rows; unique
  (for_type,for_key,rating,page_type); rating variants only lt_panel/individual; 8 for_key rules (pcc-1a..pcc-4b).
- app_kv: default_panel_model="1000xacb-panel" (cat_asset 18, has glb_file); viewer_defaults JSON.
- equipment.equipment: key UNIQUE; CHECK exactly-one-of asset_type_id/panel_type_id → for_type matches
  panel_type_code XOR asset_type_code. equipment_config.rating: 1/120 (id 128 'bpdb-01' → '660A').
- Stream A bridge.py NOT landed at build time — tier import-guarded broadly; tests stub sys.modules
  'data.equipment.bridge' (stub wins even after A lands).

## Design decisions / deviations (all justified)
1. Critic improvement 4 (FS path leaked as URL): existence check runs against the LOCAL dir knob
   `equipment.kitpreview.media_base`; the SERVED url is built by the existing config/asset3d_media.glb_url()
   (ems_backend /media/ route) — the browser never sees a filesystem path. Tested (url startswith http, tmp root
   not in url). Ops contract: media_base = the directory the ems_backend serves as /media/.
2. Critic improvement 8: pinned obj['preset'] = deep_merge(default_overrides, rule_preset); raw default_overrides
   also kept on the object for fidelity.
3. Critic improvement 2: the whole tier catches BROAD Exception (not just ImportError) — tested with a raising
   identity_node and a poisoned sys.modules entry.
4. media_base='' → deny directly (the design's "fall back to the asset3d_media root" is an http URL → not a
   readable local dir → the identical deny; implemented as deny-on-empty for clarity).
5. `cause` pass-through in the renderer = one extra line beyond the specced "template pass-through only" — required
   by the design's own "GAPS_KEY per-leaf cause 'glb_not_in_media_root'" clause; generic behaviour byte-identical
   (falls back to 'no_3d_model').
6. `config_rating` exported beyond the pinned 2-fn API (single-door rule forces the equipment_config read into
   data/equipment/*; resolve_model's pinned signature takes rating as an argument).
7. Task brief named `data/equipment/three_d.py`; the design's owned-file list (authoritative: "Implement exactly
   your owned files from the design") names `data/equipment/kitpreview.py` — implemented as kitpreview.py.

## Cert safety (rule 2) proof points
- Both knobs ship OFF; knob-off emit output byte-equal to the pre-feature baseline (test) and the bridge is never
  consulted. All new envelope/reason keys are ADDITIVE and omitted on miss. No neuract (:5433) read added anywhere;
  a :5432 blip degrades to today's null for that request only (db.eq_q never caches failures).

## Ops note (NOT code)
Until the cmd_equipment media `objects/*.glb` files (39 referenced) are rsync'd into the local ems_backend media
root, the default-deny gate keeps every 3D card on the honest ComingSoon3D path even with the knob ON:
  rsync -av <cmd_equipment>/media/objects/ <ems_backend MEDIA_ROOT>/objects/
  psql -h 127.0.0.1 -p 5432 -d cmd_catalog -c "UPDATE app_config SET value='<MEDIA_ROOT>' WHERE key='equipment.kitpreview.media_base';"
  psql -h 127.0.0.1 -p 5432 -d cmd_catalog -c "UPDATE app_config SET value='on' WHERE key='equipment.kitpreview.enabled';"
(staged flip only: staging rows ON → 18-page sweep + SSR gate → live flip.)
PARKED (for E's register): kitpreview_combo/preset/version/asset_rules not read (design SKIP); load-parent
highlight rule (backend2 resolver.py:124-178) not ported; breaker glb_node mesh highlight.

## Test evidence
- `pytest -q tests/test_equipment_3d.py` → 15 passed.
- `pytest -q tests/test_equipment_3d.py tests/test_asset3d_dg_seed.py tests/test_residual3_fixes.py` → 46 passed.
- `pytest -q -m "not live" -k "asset3d or asset_3d or equipment"` → 22 passed, 856 deselected.
- Single-door scan (grep -iE "(from|join)\s+equipment\.") over my non-exempt files: clean.
