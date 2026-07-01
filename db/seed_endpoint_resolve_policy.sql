-- db/seed_endpoint_resolve_policy.sql — editable POLICY rows for grounding/endpoint_resolve.py + default_assemble.py +
-- swap_settle.py. Keeps the two non-scalar policies (page-tail→ems-code alias, resolver_scope→policy-scope map) and the
-- extra reason causes as DB rows so the endpoint-resolve/default/swap logic hardcodes NOTHING. Idempotent (ON CONFLICT).
-- Run:  psql -h localhost -p 5432 -d cmd_catalog -f db/seed_endpoint_resolve_policy.sql

-- ── page-tail → ems page CODE aliases (only where the FE tail differs from its ems page code) ──────────────────────
-- Read by grounding.endpoint_resolve._ems_page_code as quality_policy.txt('page_tail_alias.<tail>').
INSERT INTO data_quality_policy (key, num_value, txt_value, note) VALUES
 ('page_tail_alias.harmonics-pq',    NULL, 'power-quality', 'FE Harmonics/PQ tab → ems page code power-quality [ER endpoint-resolve]'),
 ('page_tail_alias.overview-sld-3d', NULL, 'overview',      'FE SLD/3D tab → ems overview screen [ER endpoint-resolve]')
ON CONFLICT (key) DO UPDATE SET txt_value = EXCLUDED.txt_value, note = EXCLUDED.note;

-- ── resolver_scope (card_handling) → endpoint_policy scope ────────────────────────────────────────────────────────
-- card_handling.resolver_scope ∈ {meter,asset,site,panel,none}; endpoint_policy scope ∈ {single_asset,panel_aggregate}.
-- Read by grounding.endpoint_resolve._policy_scope as quality_policy.txt('scope_map.<resolver_scope>').
INSERT INTO data_quality_policy (key, num_value, txt_value, note) VALUES
 ('scope_map.meter',        NULL, 'single_asset',    'a single meter → single-asset endpoint/shape [ER endpoint-resolve]'),
 ('scope_map.asset',        NULL, 'single_asset',    'a single asset → single-asset endpoint/shape [ER endpoint-resolve]'),
 ('scope_map.panel',        NULL, 'panel_aggregate', 'a panel → aggregate endpoint/shape (fan-out) [ER endpoint-resolve]'),
 ('scope_map.site',         NULL, 'panel_aggregate', 'a site rollup → aggregate endpoint/shape [ER endpoint-resolve]'),
 ('scope_map.none',         NULL, 'single_asset',    'no scope → default single-asset [ER endpoint-resolve]'),
 ('scope_map.default',      NULL, 'single_asset',    'fallback policy scope when a resolver_scope has no map row [ER]'),
 ('scope_map.panel_default',NULL, 'panel_aggregate', 'default for panel/site-like scopes with no explicit map [ER]')
ON CONFLICT (key) DO UPDATE SET txt_value = EXCLUDED.txt_value, note = EXCLUDED.note;

-- ── default_assemble policies: typed placeholders + narrative-slot scrub list ─────────────────────────────────────
-- Read by grounding.default_assemble to strip fabricated demo values without breaking prop types. All editable rows.
INSERT INTO data_quality_policy (key, num_value, txt_value, note) VALUES
 ('placeholder.scalar',    0, '0', 'typed placeholder for a stripped scalar data leaf (keeps prop numeric) [VC-02]'),
 ('placeholder.narrative', NULL, '', 'neutral placeholder for a scrubbed narrative string (keeps prop a string) [VC-02]'),
 ('narrative_slots',       NULL,
  'insight,text,summary,note,caption,subtitle,likelysource,nextpriority,trendlabel,message,headline,description,detail,commentary',
  'metadata string slots that embed a fabricated metric → scrubbed to placeholder.narrative [VC-02, META-01]')
ON CONFLICT (key) DO UPDATE SET num_value = EXCLUDED.num_value, txt_value = EXCLUDED.txt_value, note = EXCLUDED.note;

-- ── swap_settle policy: the registered front-end renderer id set (FILL ∪ COMPONENTS ∪ COMPOSE in host/web/src/cmd) ──
-- Read by grounding.swap_settle.registered_card_ids. Editable: follows the front-end registry without a code change.
INSERT INTO data_quality_policy (key, num_value, txt_value, note) VALUES
 ('registered_card_ids', NULL,
  '5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,36,37,38,39,40,41,42,43,44,45,46,47,48,49,160',
  'card_ids that have a front-end renderer — swap targets are restricted to this set [FR-5]')
ON CONFLICT (key) DO UPDATE SET txt_value = EXCLUDED.txt_value, note = EXCLUDED.note;

-- ── extra reason causes used by endpoint_resolve / default_assemble / swap_settle ─────────────────────────────────
INSERT INTO reason_template (cause, template) VALUES
 ('endpoint_unconfigured', 'No endpoint configured for {page} ({scope}) — card cannot fetch live data.'),
 ('no_metered_feeders',    'Panel {asset} has no metered feeders reporting — no per-panel history available.'),
 ('no_renderer',           'No renderer wired for card #{card_id} — cannot display this card.'),
 ('no_default_payload',    'No default payload for card #{card_id} — nothing to render.'),
 ('literal_scrubbed',      'Demo values removed from the default payload; awaiting live data.'),
 ('swap_dup',              'Swap to card #{target} reverted — that card is already on the page.')
ON CONFLICT (cause) DO UPDATE SET template = EXCLUDED.template;
