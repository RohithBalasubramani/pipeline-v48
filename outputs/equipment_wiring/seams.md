# Equipment-wiring integration seams (pipeline_v48) — verified 2026-07-08

All paths relative to /home/rohith/desktop/BFI/backend/layer2/pipeline_v48 unless absolute.

## 1. Canonical cmd_catalog DB helper

- `data/db_client.py :: q(db, sql)` — THE one helper. psql subprocess (`--csv -t`), returns list of CSV rows,
  RAISES on non-zero (callers wrap in try/except for honest-degrade). Endpoint routing via
  `config/databases.conn_env(db)` (cmd_catalog → :5432 local, DATA_DB → :5433 tunnel).
- Usage pattern (layer2/catalog/card_fill_recipe.py:10,30): `from data.db_client import q` then
  `q("cmd_catalog", "SELECT ...")`. Prefer the constant `config.databases.CMD_CATALOG` (data/registry/lt_mfm.py does).
- New equipment reads = `q(CMD_CATALOG, "SELECT ... FROM equipment.<table> ...")` — schema-qualified, LOCAL :5432 only.
- `data/db_client.pg_connect(db)` exists for cursor/pandas consumers; not needed for metadata reads.

## 2. Topology seam (equipment-first edges)

There are TWO edge readers today, and they do NOT share a door:

A) `data/registry/lt_mfm.py` — MIRROR-FIRST (cmd_catalog `registry_lt_mfm_outgoing`, live neuract fallback via `_home()`).
   Functions: `parent_ids()`, `outgoing_edges(ids)`, `outgoing_feeders(mfm_id)`; module-level `_CACHE`.
   Callers:
   - `data/lt_panels/panel_members.py` (panel_members BFS + `_parent_ids`) → which serves
     `layer1b/basket/topology_siblings.py` (member_tables basket enrichment), `ems_exec/executor/members.py:resolve()`
     coverage counts, `ems_exec/renderers/_story/_facts.py` (narrative facts).
   - `layer1b/resolve/asset_candidates.py` (`parent_ids` → has_feeders flag; `outgoing_edges` → `feeder_table()` the
     representative-schema drill for panel baskets).

B) `registries/neuract/members.py` — LIVE :5433 (pooled psycopg2 via `registries/neuract/_db.py` + `config/neuract_dsn`,
   NOT the mirror — despite the folklore, verified in code). Functions: `members_of/outgoers_of` (via `_edge_targets`,
   from_mfm_id=panel) and `incomers_of` (lt_mfm_outgoing WHERE to_mfm_id=panel).
   Callers:
   - `ems_exec/executor/members.py:resolve()` — the generic roster interpreter door serving topology_sld +
     panel_aggregate + every roster card (role tags 'incoming'/'outgoing' drive `select(role_filter)` and the
     member_scope seam shipped this session).
   - `ems_exec/renderers/panel_aggregate.py:render()` (via `_members.resolve`).
   - `layer2/emit/panel_members_block.py` — the Layer-2 PANEL MEMBERS facts (incomers_of + outgoers_of).

NARROWEST PLUG-IN: one new atomic edge-source module (e.g. `data/registry/equipment_edges.py`) consulted by exactly
FIVE functions — `lt_mfm.parent_ids`, `lt_mfm.outgoing_edges`, `lt_mfm.outgoing_feeders`, `members._edge_targets`,
`members.incomers_of` (the two query bodies in B). Plugging there makes ALL enumerated callers inherit:
panel_members_block facts, panel_aggregate/roster fill, SLD/topology renderer (rides executor/members.resolve),
1b has_feeders + feeder_table. Union semantics: equipment edge set FIRST (or additive), fall back byte-identical to
today's tables when equipment rows are absent for a node (CERT SAFETY). Bonus: routing B through the local source
removes a request-time :5433 read.

BRIDGE (verified empirically on cmd_catalog):
- `equipment.feeder.source_id/target_id` FK → `equipment.equipment(id)` (pg_constraint: feeder_source_id_..._fk_equipment_id)
  — NOT equipment.mfm.id. Chain: feeder → equipment.equipment.id → equipment.mfm.equipment_id (242/303 set)
  → equipment.mfm.table_name → public.registry_lt_mfm.table_name → canonical lt_mfm.id.
- table_name census: equipment.mfm has 18 DUPLICATED table_names (un-bridgeable → skip honestly);
  registry_lt_mfm has 0 dups; 201 distinct bridgeable tables. 183/194 edges have a source-side mfm, 177/194 target-side.
- Direction semantics of feeder(source→target) must still be verified empirically per-panel (PCC incomers should be
  transformers/HT) before mapping onto from_mfm_id/to_mfm_id; equipment.mfm.role (incoming/outgoing) is a cross-check.

## 3. Facts seam (Layer-2 user message)

- `layer2/emit/user_message.py :: _build()`:
  - line ~251: `for _fact in (nameplate_line(asset), data_window_line(asset, card_in.get("column_basket"))):
        if _fact: parts.append(_fact)` — NEW fact lines join THIS tuple. Omission-on-miss pattern = each fact fn
    returns '' on no-asset/no-row/outage and NEVER raises (see `layer2/emit/asset_facts.py` docstring: "Any failure
    → '' (line omitted, honest-degrade)").
  - line ~277: `_pm = panel_members_block(asset); if _pm: parts += ["", _pm]` — panel topology facts block; per-member
    equipment enrichment (breaker rating, role, rated_capacity) goes inside `panel_members_block._lines`.
- New equipment facts (breaker rating_a, rtm_threshold bands, equipment_config.rated_kva, energy_scale/direction AS
  FACTS never multipliers) = new single-purpose fns (atomic file, e.g. `layer2/emit/equipment_facts.py`) appended to
  the same tuple; '' on miss keeps certified cards byte-identical.
- Note `panel_members_block._block_for` is `@lru_cache(maxsize=128)` keyed (mfm_id, scope) — per-process.

## 4. Derivations seam (recovery library + gates)

- Register: `ems_exec/derivations/registry.py` — add a descriptor via `_d(fn, columns, fidelity, recover_class)` to
  `_COMPAT` (row/series fns) or `_NAMEPLATE` (rated-denominator fns; `_ctx_table(ctx)` resolves the asset table).
  `_NEURACT = _COMPAT + _NAMEPLATE`; `LIBRARY` superset feeds `catalog()`.
- Flow into the prompt: `layer2/emit/emit.py :: _recovery_library_block(card_in)` renders `catalog()` into the
  `{{RECOVERY_LIBRARY}}` placeholder of `layer2/prompts/data_instructions_v2.md`. A registered fn is AUTOMATICALLY
  offered — no prompt edit.
- Hiding rules (emit.py:60-83): with a card_in, a fn is HIDDEN when (a) its PLAIN base_columns (anything NOT
  startswith("nameplate:")) are not ALL in the card's column basket, or (b) it has a `nameplate:*` base and THIS
  asset's rated_kva is known-empty (`_nameplate_rated` → config.nameplates.rated_kva; None=unknown never hides).
  A trailer line counts hidden fns. scope='topology' rows (from `config/derivation_binding.all_bindings`) get the
  "topology-pair only" mark.
- What a new `overload_pct` fn needs:
  1. fn in `ems_exec/derivations/` (atomic module, e.g. current.py or a new breaker.py) — current_avg ÷ breaker
     rating_a × 100; None on missing input.
  2. Registry row in `_NAMEPLATE`-style dict + `_QUANTITY` entry. Quantity vocab check: 'percent' EXISTS but is a
     WEAK class (`quantity.weak_classes` — dimension-only, won't flag mismatches); 'current' exists as a hard class.
     Give the fn a SPECIFIC family like the existing "load-percent-of-rated" (kpiKwLoadPctOfRated precedent) — e.g.
     reuse it or add "overload-percent-of-breaker" (then it must be classifiable slot-side too).
  3. Base-column spelling TRAP: a new pseudo-base like "breaker:rating_a" is treated as PLAIN by emit.py's filter
     (only "nameplate:" is special) → the fn would be hidden on EVERY card. Either reuse the "nameplate:" prefix
     convention (and extend the empty-denominator check to the breaker rating) or extend the prefix handling in
     `_recovery_library_block` in the same edit.
  4. Optional: `derivation_binding` row (expression/scope) — row-driven expression is authoritative when present
     (`_execute`); scope row for topology marking. Optional `RECOVERY_FN` entry only if a consumer target column
     should auto-recover.
  5. Fidelity: "real_exact" (exact denominator) or "real_approx"; recover_class "nameplate_lookup" analog.
- Gate side: `layer2/gates.py :: enforce_honest_blank` (line 510) — rule (i) drops fields whose base columns miss the
  basket / whose nameplate denominator is empty (`_nameplate_missing`); rule (iii) quantity wall compares fn quantity
  (`quantity_class.name_class(fn)`) vs slot-side class. The breaker denominator needs an equivalent
  "empty-denominator" fact so fill-time honest-degrades match prompt-time hiding.

## 5. Layer-1b candidates seam (alias column)

- Build: `layer1b/resolve/asset_candidates.py :: asset_candidates()` — positional rows
  [id, name, table, mfm_type_id, load_group, class, has_data, has_feeders, never_wired, table_exists] (indices 0-9).
  All consumers are len-guarded (`as_asset` len>6/7/8/9; no_data_gate/ambiguous_candidates len>6;
  asset_resolve ghost check `len(picks[0]) > 9 and not picks[0][9]`) → an ALIAS column at index 10 is additive-safe.
- AI listing: `layer1b/resolve/asset_resolve.py:96-98` — `f"{c[1]}\t{c[5]}\t{c[4]}\t{'NO-DATA' ...}"`
  (name<TAB>class<TAB>load_group<TAB>flag). An alias string can be appended as a 5th TAB column (display context).
- Verbatim mapping wall: `by_name` (exact c[1]) + `by_norm` (`_norm` space/punct/case-collapsed c[1]) →
  `resolve_name()` unique-or-None. Any alias enrichment MUST keep the AI returning the canonical c[1] verbatim.
  Safe options: (a) alias column shown as context only, prompt still demands the canonical name; (b) additionally
  extend `resolve_name` with an alias→row map built from index 10, unique-or-ambiguous (an alias colliding with a
  canonical name or another alias must fall to ambiguous, never a pin). Sources: equipment.mfm.name bridged via
  table_name (registry table_name is unique; skip the 18 dup-table equipment rows).

## 6. asset_3d renderer seam (kitpreview fallback)

- Backend: `ems_exec/renderers/asset_3d.py :: render(asset, card, ctx)` emits the ViewerResolveResponse envelope:
  `{equipment:{id,key,kind,type,pageType}, object:{slug,label,url,rating}|null, viewer:{merged look}}` + a
  `fill.GAPS_KEY` per-leaf reason list when object=null. object comes from
  `layer2/emit/metadata/asset_3d.py :: emit_asset_3d` — a 4-tier SQL resolve over DATA_SCHEMA `lt_asset_3d`/`lt_mfm`
  (override → rating-variant → type-default → global-default), ALL EMPTY today → object=null.
  viewer = deep_merge(viewer.viewer_defaults knob, `_asset_preset(obj)`), and `_asset_preset` ALREADY honors
  `obj.viewer / obj.preset / obj.default_overrides` — so a resolved object carrying kitpreview
  `default_overrides` flows into the merged viewer with zero renderer change.
- FE contract: `host/web/src/cmd/special.tsx :: Asset3dEnvelope` — reads `payload.object?.url`; url present →
  CMD_V2 `<CentralAssetViewer/>` (client-only, SSR shell), url absent → honest `<ComingSoon3D/>`.
  `isAsset3dEnvelope` keys on presence of "object"/"viewer"; routed by card 60 + handling_class `asset_3d`
  (host/exec_cards.py `_SPECIAL_KINDS` → ems_exec.renderers.run_special).
- Kitpreview plug point: a NEW tier inside `emit_asset_3d._resolve_object` (after the 4 lt_asset_3d tiers, since
  those are empty they cost one failed read each) reading LOCAL `cmd_catalog equipment.kitpreview_cat_asset`
  (columns verified: id, slug, label, url, sort, created_at, default_overrides, template, group_id, glb_file) via
  `q(CMD_CATALOG, ...)`, keyed by asset class/table bridged through table_name → equipment.mfm →
  equipment_id → kitpreview mapping (kitpreview_asset_rules/cat_group for class-level defaults). Emit
  `{slug,label,url,rating}` + carry `default_overrides` on the object so `_asset_preset` merges it;
  url from kitpreview url/glb_file (absolute if stored absolute, else via config.asset3d_media.glb_url-style base —
  DB-knob). Absent mapping → unchanged object=null (byte-identical).

## 7. Risks

1. `registries/neuract/members.py` rides LIVE :5433 (pooled psycopg2, NOT the mirror) — equipment-first edges there
   must be local-first with today's behavior as fallback; tests must not require :5433.
2. `equipment.feeder` FKs reference `equipment.equipment(id)`, NOT `equipment.mfm.id` — a direct feeder→mfm.id join
   silently builds a WRONG topology; only feeder→equipment→mfm(equipment_id)→table_name→registry is safe.
3. 18 duplicated table_names in equipment.mfm + 61 mfm rows without equipment_id + ~11/17 edges lacking a bridgeable
   mfm on one side — census must skip un-bridgeable nodes honestly, never guess.
4. emit.py's library filter treats every non-"nameplate:"-prefixed base column as a basket column — a new pseudo-base
   prefix (breaker:) gets the fn permanently hidden unless the filter is extended in the same change.
5. 'percent' is a WEAK quantity class (won't flag mismatches) — an overload_pct fn declared bare 'percent' is
   under-gated; use/extend a specific family (load-percent-of-rated precedent).
6. Per-process caches everywhere (lt_mfm._CACHE, panel_members._MEMBERS_CACHE, panel_members_block lru_cache,
   meters._BY_ID) — a knob-toggled edge source must be consistent from first use; no mid-run source switch.
7. Richer 194-edge topology changes expected_count/reporting_count → coverage verdicts (full vs partial) and
   1b has_feeders/has_data (panel-granularity greening) can shift on certified pages — additive edges need a
   default-off app_config knob or proof of byte-identical output where equipment data is absent.
8. member_scope/role_filter (shipped this session) depends on role tags 'incoming'/'outgoing' derived from WHICH
   query direction produced a member — the equipment edge source must preserve side tagging or select() breaks.
9. Direction semantics of equipment.feeder (source→target) are UNVERIFIED — must be proven empirically (a PCC panel's
   incomers = transformers/HT) before wiring; equipment.mfm.role is the cross-check.
