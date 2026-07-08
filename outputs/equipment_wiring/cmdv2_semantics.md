# CMD_V2 source semantics for the `equipment` schema tables (cross-ref, 2026-07-08)

Source tree: /home/rohith/CMD/backend2 (Django, apps: core / panels / assets / kit_preview).
Local mirror verified against cmd_catalog `equipment` schema via pg_constraint + empirical joins.
All file:line cites are into /home/rohith/CMD/backend2 unless absolute.

## 1. equipment_config — resolution chain + which screens read what

Model: core/models.py:265-352 (`EquipmentConfig`, db_table `equipment_config`,
OneToOne -> Equipment, ALL fields nullable so overrides can be partial).
`CONFIG_FIELDS` (core/models.py:333-341) is the exact list served to the FE.

Resolution (core/config.py:50-68 `resolve_config`): per-equipment EquipmentConfig
field -> panel-type default (`core/config_defaults.py` BY_PANEL_TYPE: transformer /
distribution_panel / lt_panel) or asset-type default (BY_ASSET_TYPE: dg / ups)
-> None. IMPORTANT: the source system NEVER serves a raw NULL for rated_kva etc. —
code defaults always backstop (this is why their 120-row table with mostly-NULL
columns still works: the NULLs fall through to config_defaults.py:12-120).

Per-FEEDER override (core/config.py:20-47 `feeder_rating_overrides`): a feeder
(MFM) does NOT use the panel-sized config; its ratings are DERIVED from its own
nameplate `MFM.rated_capacity_kva`:
  rated_kw = kva * 0.9 (assumed PF), rated_current_a = kva*1000/(sqrt(3)*415),
  current_high_threshold_a = 1.2*rated_a, contracted_kw = 0.9*kw,
  critical_load_kw = 0.5*kw, energy_target_kwh_today = kw*24,
  nominal voltage converted L-L -> L-N (415 -> 240) because per-phase columns are L-N.
No-op when the nameplate is missing (falls back to panel-sized defaults, never zeros).

Endpoint: GET /api/mfm/{id}/config/ (core/urls.py:12, core/views.py:385-406
`mfm_config`) -> `resolve_for_id` (core/config.py:99-128): id < FEEDER_ID_OFFSET =
panel Equipment; id >= offset = feeder MFM, config subject = the MAPPED device
(m.equipment) else the located panel, then `feeder_rating_overrides` applied.
`_frontend_config` (core/config.py:87-96) renames nominal_voltage_v ->
voltage_nominal_v and thd_*_limit_pct -> ieee_519_*_thd_limit_pct + injects IEEE-519
PQ defaults. The response also embeds the resolved 3D object (core/views.py:396).

How rated_kva is USED (loading computations):
- energypower.py:235 `rated_kva = cfg.get('rated_kva') or RATED_KVA`; live_power
  widget ships {apparent_kva, rated_kva} (energypower.py:308) — FE draws bar vs rated.
- panel_poweranalysis.py:119-125: headline = live apparent kVA with target=rated_kva;
  `marker_pct = worst_peak / rated * 100` (peak marker as % of rated capacity).
- energydist.py:79-84 `_cap_util(kwh, rated_kva, hours)`: window capacity
  `cap = rated_kva * 0.9(PF) * hours` kWh, `util = kwh / cap * 100` — per-feeder
  capacity/utilization on the Sankey/energy-distribution page (lines 297, 320).
- realtime.py:112: per-feeder rated_kw (from feeder_rating_overrides of
  MFM.rated_capacity_kva) is the kw-band denominator (see RTM below).
- feeder_overview.py:122-127 kw_load card: pct = kpi_kw_load_pct_of_rated, ships
  rated_kw + rated_kva; status = band(load, 75, 90) -> Normal/Elevated/Critical.
- Loading % formula: core/derive.py:16-21 `kw_load_pct = active_kw / rated_kw * 100`
  (backend-derived, OVERWRITES the logger's kpi column: realtime.py:134-143).

How voltage_statutory_deviation_pct is USED:
- Deviation formula: core/derive.py:57-64 `voltage_deviation_pct =
  (V - nominal_LN) / nominal_LN * 100` vs the per-phase (L-N) nominal (the logger
  bakes it vs 240 V — garbage for HT; backend re-derives for >=1 kV: realtime.py:114-118,140-142).
- feeder_voltagehistoryview.py:66-71: statutory band lines
  `max_line = nominal*(1+dev/100)`, `min_line = nominal*(1-dev/100)`; per-phase
  bucket max above max_line = SWELL event, min below min_line = SAG event
  (lines 79-90). `dev` default 5.0 when unset.
- feeder_overview.py:174-188 `_voltage_card`: limit_pct = cfg statutory dev (or 5.0);
  status = band(|vdev|, 3, 5) -> Normal/Elevated/Critical; nominal is trusted only
  if within 0.5x..2x of the actual, else derived actual/(1+dev/100) (HT-safe).
- DG voltage/current card: assets/consumers/dg.py:214 ships nominal_voltage_v +
  voltage_statutory_deviation_pct as the V&C Max/Min reference lines (DG default 5%).

Fields our copy has data for: rated_kva (113 rows) + voltage_statutory_deviation_pct
(7 rows) — exactly the two above. Everything else (contracted_kw, critical_load_kw,
thd limits, demand_limit_kw, targets, UPS zones) is NULL upstream; in the source
system those only ever materialize via config_defaults.py code defaults.
`rating` (a TEXT variant tag like "660A") is NOT in CONFIG_FIELDS — it is read only
by the 3D resolver (core/resolver.py:57-60) to pick a model variant.

## 2. rtm_threshold — exact banding semantics

Model: core/models.py:353-402. One row per (scope, metric); scope = panel_type XOR
equipment (DB CHECK `rtm_threshold_exactly_one_scope`). metric in
{kw, kvar, pf, volt, amp, i_unbal}. The 4 columns are BAND UPPER EDGES.

Resolution: core/rtm.py:7-17 `resolve_thresholds` — per-equipment row -> panel-type
row -> code DEFAULT_BANDS (core/rtm_defaults.py:28-35). Loaded once per WS connect
(panels/consumers/realtime.py:126-132).

Classification: core/rtm_defaults.py:40-55 `classify(value, (lo,no,mo,hi), direction)`
-> 5 bands ['low','normal','moderate','high','critical']:
  ascending (higher=worse; kw/kvar/volt/amp/i_unbal):
    value < low_max -> low; < normal_max -> normal; < moderate_max -> moderate;
    < high_max -> high; else critical.  (strict `<` against each *_max)
  descending (higher=better; pf ONLY):
    value >= low_max -> low; >= normal_max -> normal; >= moderate_max -> moderate;
    >= high_max -> high; else critical.  (so pf bounds are stored descending:
    0.98/0.95/0.90/0.85)
  value None -> 'normal' (honest neutral, NOT critical).

CRITICAL SUBTLETY — the value banded is NOT the display value. METRIC_META
(core/rtm_defaults.py:15-22) maps each metric to (display_col, basis_col,
direction, absval):
  kw      display active_power_total_kw      banded on kpi_kw_load_pct_of_rated (%)
  kvar    display reactive_power_total_kvar  banded on ratio_kvar_kva scaled x100 (%)
  pf      display+band power_factor_total    (desc)
  volt    display voltage_ll_avg             banded on |kpi_voltage_deviation_pct| (absval=True)
  amp     display current_avg                banded on kpi_kva_load_pct_of_rated (%)
  i_unbal display+band current_unbalance_pct
So thresholds are in NORMALIZED units (% of rated / |dev %| / raw pf) — one
threshold set works across feeders of any size. BASIS_SCALE (line 25) multiplies
ratio_kvar_kva by 100 before comparing. absval takes |value| first
(realtime.py:50-58 `_row` applies scale -> abs -> classify).
Note kw bands on % of rated KW but amp bands on % of rated KVA.

Wire shape: each RTM row ships `bands = {metric: band}` per metric plus
`band = bands['kw']` as the row's overall color (realtime.py:59-65).

Our 18 local rows = 3 panel_types x 6 metrics (verified: values byte-equal to
DEFAULT_BANDS; panel_type_id 1/2/3, equipment_id all NULL — i.e. the seeded
type-defaults from seed_rtm_thresholds.py, no per-equipment overrides exist).

## 3. breaker — provenance + the two consumers

Model: panels/models.py:21-55. OneToOne MFM (per-FEEDER, not per-panel);
fields breaker_type (ACB/MCCB/MCB/unknown), rating_a (A, nullable), plus audit
fields source/glb_node/panel_key. LOCAL FK verified: equipment.breaker.mfm_id ->
equipment.mfm(id).

Provenance (core/management/commands/seed_breaker_types.py:1-22): there is NO
breaker telemetry or nameplate anywhere — rows are seeded by scanning the 8 PCC
panel GLBs whose switchgear nodes are named `<Feeder>_<Rating>A_ACB_Unit`;
MCCB feeders are one generic node (rating_a stays NULL — hence only 168/301 rated).
Only PCC panels have GLBs; HT/non-PCC feeders got class-rule/default rows.

Usage — ANNOTATION ONLY, never a computation input:
1. panels/consumers/base.py:98-119 `_load_feeders` joins
   `Breaker.objects.filter(mfm__reference_id=eid)` onto every feeder dict as
   breaker_type / breaker_rating_a.
2. energydist.py:314 (incomers[]) and :333 (consumers[]) ship
   `breaker_type` + `breaker_rating_a` on every SLD/Sankey node so the SLD renders
   the REAL breaker type instead of the old hardcoded "ACB"/"MCCB".
The source system does NOT divide current by rating_a anywhere (no overload-%
denominator use). The feeder-overview "breaker" KPI card
(feeder_overview.py:146-149) reads TELEMETRY columns breaker_state /
breaker_trips_last_24h — unrelated to this table. So: mirror = surface
breaker_type/rating_a as SLD/feeder FACTS; any overload-% math would be NEW
semantics, not a port (rated_current_a from config is the existing current
reference, with current_high_threshold_a = 1.2x rated as the alarm line).

## 4. kitpreview_* — GLB serving + scene config + template

App: kit_preview/ (port of the standalone FastAPI :8470 kit-preview).
Tables (kit_preview/models.py): kitpreview_cat_group (catalog subheading) ->
kitpreview_cat_asset (THE 3D object), kitpreview_app_kv (key/value; key
'viewer_defaults' = the GLOBAL viewer baseline, key 'default_panel_model' = the
EMS catch-all slug), kitpreview_viewer_rule (the ONE binding table),
kitpreview_preset/_version, kitpreview_combo, kitpreview_asset_rules (designer-
side preset/combo state).

CatAsset (models.py:95-138): slug/label + TWO GLB sources — uploaded `glb_file`
(FileField upload_to='objects/', stored under MEDIA_ROOT) WINS over external
`url` text. `model_url(request)` (models.py:131-138) returns glb_file.url made
ABSOLUTE via request.build_absolute_uri (FE fetches cross-origin, a bare /media/
path would resolve wrong), else the raw `url`.
- `default_overrides` JSON = per-asset viewer config (camera/lighting/flows/Home pose).
- `template` JSON = backend-driven KPI/card page content
  ({props:{title, subtitle, topKpis, defaultDetail, ...}}).

Media: config/settings.py:145-146 MEDIA_URL='media/', MEDIA_ROOT=BASE_DIR/media;
served by static() in config/urls.py:31. Two upload homes: admin-uploaded
CatAsset.glb_file -> MEDIA_ROOT/objects/; the API upload endpoint
PUT /api/kit-preview/assets/{asset}/glb/ writes MEDIA_ROOT/kit_preview/{safe}.glb
and returns url '/media/kit_preview/{safe}.glb' (kit_preview/views.py:24,304-325;
path-traversal guarded by _safe_id).

ViewerRule (models.py:161-194): scope -> model (+ optional per-binding preset).
Scope EXACTLY ONE of for_type (AssetType/PanelType code, optionally narrowed by
`rating` e.g. "660A") or for_key (one Equipment.key). page_type in
individual/overview/variant. unique_together (for_type, for_key, rating, page_type).

Resolution (core/resolver.py:63-108 `resolve_binding`), most-specific first:
  1. for_key = equipment.key
  2. for_type + rating (rating read from EquipmentConfig.rating, resolver.py:57-60)
  3. for_type with rating=''
  4. global default panel (AppKV['default_panel_model'] slug) — 'individual'
     page_type only, and only when fallback_default (?default=panel).
Preset merge: CatAsset.default_overrides is the BASE, rule.preset DEEP-merged on
top (rule wins per leaf, _merge resolver.py:26-33); then the final viewer config =
AppKV['viewer_defaults'] deep-merged with that preset (resolver.py:180-182).

LOAD RULE (resolver.py:124-178): an lt_panel/distribution_panel equipment fed off
a panel has no own model — resolve the PARENT (source of its first `feeders_in`
edge, resolver.py:127-129) and return the parent's model + a `highlight`
{name,key,parentKey,parentName} so the FE loads the whole panel GLB and glows this
load's compartment. Skipped when the load has its own for_key rule.

What the 3D viewer consumes — GET /api/equipment/{id}/viewer/ and
/api/equipment/key/{key}/viewer/ (core/urls.py:16-17, core/views.py:484-537;
?default=panel, ?page=overview|variant):
  {equipment:{id,key,kind,type,pageType},
   object:{slug,label,url(absolute GLB),rating}|null,
   viewer: global_defaults (+) preset   (the merged scene config),
   template: CatAsset.template|null,
   highlight: {...}|null}
The same `object` is embedded in /api/mfm/{id}/config/ (core/views.py:396).
Catalog CRUD + presets/combos/rules live under /api/kit-preview/*
(kit_preview/urls.py:12-45; auth disabled, DRF).

## 5. feeder + mfm — how backend2 walks topology (incl. incomer/outgoing tabs)

TWO SEPARATE GRAPHS, and this is the key insight:

(a) `feeder` (core/models.py:229-263) = the SLD edge table. Directed
Equipment -> Equipment, "power flows source -> target"; kind feed/spare/coupler;
`metered` False for MFM-less edges; unique (source,target,kind).
LOCAL FK verified: equipment.feeder.source_id/target_id BOTH ->
equipment.equipment(id) — NOT mfm ids. Direction verified empirically on the
local copy: pcc-1a (equipment id 47) IN-edges from tx-01 + solar-plant;
OUT-edges to bpdb-01, hhf-01-pcc1, ups-01/02/03. So: incomers of E = sources of
edges where target=E (`feeders_in`); outgoers = targets where source=E
(`feeders_out`) — Equipment.incomers()/outgoers() helpers core/models.py:106-113.
Runtime consumers of this table in backend2 are ONLY:
  - core/resolver.py:124-129 `_feeder_parent` (the 3D parent-panel/highlight rule);
  - the incomers()/outgoers() model helpers (no other callers found).
It is topology-of-record for the SLD but NOT what drives the page data.

(b) `mfm` (panels/models.py:11 + core/models.py:139-228 MeterBase) = the METER
graph that actually drives every panel page. Each MFM has:
  reference = the panel it is LOCATED IN (sits on),
  equipment = the device it is MAPPED TO / measures,
  role in incoming/outgoing/spare/coupler (which side of the feed it reads),
  data_source + table_name (the gic_* timeseries), rated_capacity_kva,
  energy_direction/energy_scale/power_scale (per-meter CT/firmware corrections),
  parent_series (sheet lineage), section/zone/load_profile/asset_category.
Deliberately NO FK to Feeder ("topology lives in the Feeder table",
core/models.py:143-145).

Panel pages fan out by: `MFM.objects.filter(reference_id=eid)` + skip rows with
no data_source/table_name (panels/consumers/base.py:96-120), then split by
`role`: incomers = role=='incoming', outgoing = role in ('outgoing','spare')
depending on page (energydist.py:250-251,276-277; realtime.py:108 keeps only
incoming+outgoing). RTM groups to exactly two sections
'incomers'/'outgoing' (realtime.py:85-94) with direction import/export
(realtime.py:176). Panel totals = SUM over incomers (panel_poweranalysis.py:90,
energypower.py:128); delivered = sum over metered outgoing; loss = supplied -
metered_out kept as a balancing Sankey node (energydist.py:280-289).

Sidebar Incomings/Outgoings tabs: core/ems_tree.py curates the section/panel
scaffold; core/views.py:126-190 fills each hierarchical panel with
Overview + role groups by grouping every MFM under its `reference` panel by
`role` (_GROUPS Incoming/Outgoing/Spare/Bus Coupler, views.py:16-17,164-168);
feeder leaf ids are MFM.id + FEEDER_ID_OFFSET.

Per-meter correction fields (energy_direction/energy_scale/power_scale,
core/models.py:170-212): backend2 applies them INSIDE core/services.py when
reading energy/power registers (they encode verified CT-miswire decades).
For V48 these must remain FACTS surfaced to the AI, never silent multipliers
(hard rule 1) — but note the source system DOES apply them at read time; that is
the proven semantic if a default-off knob is ever wanted.

## 6. Direct implications for V48 wiring

- equipment.feeder edges are Equipment-id space; bridge to meters only through
  equipment.mfm (reference/equipment + table_name) — mfm.table_name is the sole
  safe bridge to canonical lt_mfm, as established.
- Incomer/outgoing classification for PANEL DATA should mirror mfm.role (that is
  what all 8 PCC pages do); equipment.feeder is the richer SLD graph (194 edges,
  includes unmetered nodes: solar-plant, grid, DG bus) for topology_sld cards and
  parent-panel 3D highlighting.
- RTM banding: copy classify() semantics exactly (strict <, pf descending with
  >=, None -> 'normal', band on the normalized basis column with x100 kvar scale
  and |volt|). Thresholds resolve equipment-row -> panel_type-row -> code default.
- equipment_config: wire ONLY rated_kva + voltage_statutory_deviation_pct as
  facts; the source system's other values come from code defaults, so absent
  columns are 'no data upstream', not gaps to fill.
- breaker: annotation-only (SLD node breaker_type/rating_a); no overload math in
  the source system.
- kitpreview: viewer payload = {object.url (absolute GLB), viewer (global
  'viewer_defaults' deep-merged with default_overrides+rule preset), template,
  highlight}; resolution for_key -> for_type+rating -> for_type -> default panel;
  GLBs live under MEDIA_ROOT (media/objects/ uploads, media/kit_preview/ API
  uploads) served at /media/.
