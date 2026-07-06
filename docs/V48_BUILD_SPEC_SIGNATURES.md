> Part of the V48 build-spec, generated 2026-06-23. Rewritten 2026-06-29 to the **payload-morph model** (CLAUDE.md §B4 "one payload per card", commit dfded69; see `V48_PAYLOAD_MORPH_CORRECTION.md`). See `V48_BUILD_SPEC.md` for the index.

I have full grounding on the real V47 conventions (`q(db, sql)`, `llm(system, user)`, `loads_lenient`, `resolve_asset`, `panel_members`, `energy_delta`, `aggregate_shape`, the builders, `ai_log`) AND on the corrected morph model. The signatures below consume/produce the corrected contract shapes.

## What changed in this rewrite (the morph)

The pre-morph spec had **Layer 2 emit a whole per-tab `frame` in one of the per-tab dialects** (canon set `flat_asset`/`widgets_envelope`/`column_row`/`shared_context`) — data AND preformatted labels/colours fused into one fat object. The morph splits that by ownership:

- **Layer 2 (AI) per-card OUTPUT is now `{ exact_metadata, data_instructions }`** (Decision A, hybrid). `exact_metadata` is the FINISHED, byte-identical METADATA block the AI authors (labels/units/rosters/order/thresholds/contracts/colours/badges/tabs — the §B4 morphable tier). `data_instructions` is a sibling PARSEABLE RECIPE (a resolved `card_data_recipe.fields`: per-field `kind/role/metric/label/unit` + the L3/L6 resolution delta `column/agg/source/sql_fragment/base_columns/edge/value`, plus a per-card envelope `payload_shape/orientation/entity_dim/selection_dim/binding/window/source`). The AI never touches DATA values or design-system chrome.
- **The HELPER/worker functions PARSE `data_instructions` and FILL the DATA tier** — `history`/`periods`/`apiExtras` (numbers + initial interaction-state seeds) from EITHER the live socket frame (`ws/mfm/{id}/{screen}/`) OR a **test-DB fixture in the identical Snapshot shape**, aggregating groups via `panel_topology`. The two fill sources are interchangeable at the mapper boundary.
- **The MERGE** flattens `exact_metadata` + filled-DATA into **ONE payload per card, every key exactly once, no second `root`** (CLAUDE.md §B4).
- **The "dialect" survives ONLY as the DATA-FILL (mapper-input) shape** the helper targets (`card_handling.payload_family`: `flat_series`/`tiles`/`scene`/…), NEVER as a Layer-2 output. It is a worker concern, not an AI emit.
- **UI-selection state stays HOOK-owned** (frontend, in progress) — neither Layer 2 nor the worker. Per-card payloads carry only a read-only SEED.

**LLM seam is SYNCHRONOUS urllib + `ThreadPoolExecutor`** — NOT `asyncio`/`httpx`. The `ai_log` logger monkeypatches `urllib.request.urlopen`, so every :8200 call MUST go through `urllib.request.urlopen` to be captured. Concurrency (1a∥1b, the per-card fan-out) is therefore `ThreadPoolExecutor`, not `asyncio.gather` — each worker thread makes a blocking `urlopen` the patched logger sees.

## Function signatures

V48 Python signatures, organized into the atomic folder skeleton (one concern per file). Concurrency is `ThreadPoolExecutor`, per-card fan-out and the group pre-pass are explicit. Types reference the contract schemas by their `$id` titles (`PipelineInput`, `Layer1aOutput`, `Layer1bOutput`, `Layer2CardInput`, `Layer2CardOutput`, `SharedContext`, `PageFrameEnvelope`, `OrchestratorState`) plus the two morph sub-shapes `ExactMetadata` and `DataInstructions` (sub-objects of `Layer2CardOutput`). Type aliases are `dict`/`TypedDict`-shaped to the JSON contracts; `JSON = dict[str, Any]`.

```python
# ── v48/clients/llm_client.py ──────────────────────────────────────────────
# Qwen3.6 client — the ONE LLM seam. SYNCHRONOUS, via urllib.request.urlopen,
# so the ai_log monkeypatch (which patches urllib.request.urlopen) captures EVERY
# call. Mirrors v47 pipeline.llm() verbatim (temp 0, response_format json_object,
# enable_thinking=False). Concurrency is ThreadPoolExecutor, NOT asyncio —
# httpx/aiohttp would BYPASS the urllib patch and lose the ai_<run_id>.jsonl log.

def call_qwen(
    system: str,
    user: str,
    *,
    url: str = "http://localhost:8200/v1/chat/completions",
    model: str = "Qwen/Qwen3.6-35B-A3B-FP8",
    timeout: float = 120.0,
    lenient: bool = True,
) -> JSON:
    """One BLOCKING Qwen3.6 chat call (temp 0, JSON mode, thinking off) issued via urllib.request.Request + urllib.request.urlopen (the seam ai_log patches — DO NOT use httpx/aiohttp). Strips <think>, parses via loads_lenient (lenient=True) or re.search('{.*}'); FAIL-OPEN returns {} on a dead/slow model so one card degrades, never the run. Safe to call from a ThreadPoolExecutor worker."""

def loads_lenient(txt: str) -> JSON:
    """Salvage a possibly-truncated LLM JSON object (strip <think>, walk every resumable cut boundary newest-first, prune a partial trailing list element); ported verbatim from v47 column_resolve.loads_lenient — shared by 1a/1b/Layer2."""

def install_ai_log(run_id: str) -> str:
    """Monkeypatch urllib.request.urlopen so EVERY :8200 call is logged to logs/ai_<run_id>.jsonl ({seq,ts,ms,model,system,user,output,usage}); import FIRST, before any layer makes a call. The patch is thread-safe (the seq counter + append are atomic enough for the fan-out). Returns the log path (OrchestratorState.log_path)."""

def gather_llm(jobs: list[Callable[[], T]], *, max_workers: int = 8) -> list[T]:
    """The concurrency primitive replacing asyncio.gather. Run N blocking jobs (each ends in a call_qwen → urlopen) on a ThreadPoolExecutor and collect results IN ORDER. Used for 1a∥1b and the per-card fan-out. Because each job blocks on the PATCHED urllib.request.urlopen, every concurrent call is still ai_log'd. Exceptions per job are captured, never crash the pool (FAIL-OPEN per slot)."""


# ── v48/clients/db_client.py ───────────────────────────────────────────────
# The deterministic DB seam. q() ported from v47 column_resolve.q (psql --csv -t,
# PGCLIENTENCODING=UTF8, RAISES on non-zero — never a silent empty). DB-target-
# parameterized so the same worker code hits live OR the test DB.

def q(db: str, sql: str) -> list[list[str]]:
    """Run `psql -U postgres -d <db> --csv -t -c <sql>`; return CSV rows; raise on non-zero (loud failure, never silent []). db ∈ {cmd_catalog, lt_panels_db, lt_panels, <test_db>}."""

def data_db_name(db_target: str) -> str:
    """Map PipelineInput.env.DB_TARGET ('live'|'test') to the time-series DB name the helper/worker queries when filling the DATA tier: live→'lt_panels', test→the test DB (the test-DB fixture lands in the IDENTICAL Snapshot shape, interchangeable at the mapper boundary). cmd_catalog/lt_panels_db registry reads are unaffected."""

def catalog(sql: str) -> list[list[str]]:
    """q('cmd_catalog', sql), filtered to status='live' by every caller — the shared metadata INPUT to all 3 layers."""


# ── v48/layer1a/route.py ───────────────────────────────────────────────────
# Pure-AI storytelling router. Picks the page that TELLS THE STORY BEST (NOT
# asset/metric/keyword match), emits a per-card analytical story, carries DB
# layout/size refs verbatim, and attaches the deterministic Step-0 partition.
# UNCHANGED by the morph (1a never emits a card payload).

def route_1a(prompt: str, *, avoid_ctx: JSON | None = None) -> Layer1aOutput:
    """Pure-AI Layer 1a: route prompt → page_specs.page_key (verbatim) by ANALYTICAL INTENT, emit page-level `story` + per-card `analytical_story`, extract metric/intent; carry layout (page_specs.grid_template_*) + per-card slot/size; attach interdependency_groups (Step-0 partition). One mandatory call_qwen call (blocking; runs as a gather_llm job alongside 1b); FAIL-OPEN to keys[0]/'power'/'trend'. Morph impact: NONE — 1a emits page+metric+intent, never a card {data+metadata} payload."""

def build_route_surface() -> str:
    """DETERMINISTIC: build the 1a routing input — live page_specs grouped by '## SHELL' (page_key/title/purpose/analytical_theme/reusable_answers/archetype) + each page's real card titles via page_layout_cards⋈cards (string_agg, slot_order). Feeds route_1a's user prompt. whats_on_page is deliberately NOT fed (render plumbing)."""

def carry_layout_and_slots(page_key: str) -> tuple[JSON, list[JSON]]:
    """DETERMINISTIC: read page_specs layout block + page_layout_cards slot map + card_grid_size (116/145; missing ids 117–176→defaulted+logged) for the chosen page; returns (Layer1aOutput.layout, cards[].slot/.size) carried through verbatim — placement is from the DB, positions never move."""


# ── v48/layer1a/partition.py ───────────────────────────────────────────────
# DETERMINISTIC Step-0 interdependency partition (NOT AI). Splits 1a's chosen
# cards into transitively-connected groups + standalone via cmd_catalog couplings.
# UNCHANGED by the morph — only what each group/standalone card OUTPUTS changes.

def partition_groups(page_key: str, card_ids: list[int]) -> tuple[list[JSON], list[int]]:
    """DETERMINISTIC Step-0: from card_link + cards.interdependency prose + card_combo/_member + selection_dimension (via v_interaction), union into transitively-connected interdependency_groups[] (group_id, card_ids, combo_id, coupling[] looked up NOT invented); edgeless cards → standalone. The prose∪card_link UNION is mandatory (card_link ALONE orphans the lone time-bucket card). OPEN (pending user): the morph leaves partition UNCHANGED, so the RTM time-footer card 160 still detaches from rtm_ctx — closing that orphan (union page_control.affects_cards / combo-region co-membership) is one of the un-applied build-spec review fixes. Returns (groups, standalone_card_ids)."""

def lookup_couplings(page_key: str, card_ids: list[int]) -> list[JSON]:
    """DETERMINISTIC: read card_link edges (src/dst_card, dimension, link_type, src/dst_effect, trigger, scope, bidirectional, wired) for the group's cards — the coupling[] handed to Layer 2 + carried into shared_context.interaction.couplings, sourced from cmd_catalog (AI only validates these later, never invents)."""


# ── v48/layer1b/asset.py ───────────────────────────────────────────────────
# Pure-AI asset resolve (confident pin OR ambiguous candidate list). Ported from
# v47 resolve_asset/ASSET_SYSTEM — class-from-subject inference, 6-class
# discriminator, asset-picker round-trip via PIPELINE_ASSET_ID. UNCHANGED by morph.

def resolve_asset_1b(prompt: str, mention: str, *, pinned_id: int | None = None) -> tuple[JSON | None, list[JSON]]:
    """Pure-AI asset resolve: if pinned_id (PIPELINE_ASSET_ID) → return (asset{how='user-choice'}, []) skipping the call. Else one blocking call_qwen → CONFIDENT → (asset{how='AI'}, []); AMBIGUOUS (the DEFAULT) → (None, candidate_list[]) for the AssetPicker. Returns (asset, candidate_list) for Layer1bOutput. Morph impact: NONE — no card-payload coupling."""

def asset_candidates() -> list[list[str]]:
    """DETERMINISTIC: lt_panels_db lt_mfm⋈lt_mfm_type listing with the load-bearing index contract [id,name,table_name,mfm_type_id,load_group,class]; the universe resolve_asset_1b picks from and the candidate_list shape."""


# ── v48/layer1b/columns.py ─────────────────────────────────────────────────
# Pure-AI CARD-AGNOSTIC column basket. Ported from v47 resolve_columns WITHOUT
# recipe_fields (the GENEROUS probable list IS the basket) + the anti-hallucination
# guardrail. This basket is the INPUT to Layer 2's per-card data_instructions
# (the card-SPECIFIC resolve_columns-with-recipe_fields half stays in Layer 2).

def resolve_basket_1b(prompt: str, metric: str, intent: str, asset: JSON) -> JSON:
    """Pure-AI card-agnostic basket: across the asset's table(s) (+ topology siblings for panel concepts), one blocking call_qwen returns the GENEROUS feasible+probable column set (raw/derived/const/event, with metric/label/unit/rank/why/base_columns); reconciles derived_metrics.base_columns ∩ live schema; returns column_basket{tables,columns,unmappable} for Layer1bOutput. Morph impact: NONE — output is a real-column basket; the morph reuses it as INPUT to data_instructions."""

def column_dictionary(asset: JSON) -> list[JSON]:
    """DETERMINISTIC: per-column lines (column|label|kind|unit|has_data) from the live lt_panels schema + derivable derived_metrics (base_columns all present) + nameplate_config consts — the candidate universe fed to resolve_basket_1b."""

def guard_columns(picked: list[JSON], real_cols: set[str], metric: str, intent: str) -> tuple[list[JSON], list[JSON]]:
    """DETERMINISTIC anti-hallucination post-pass (ported from v47 layer35_correct/_same_family): keep only columns in real; a dropped name → difflib fuzzy + _same_family gate (rejects cross-metric swaps) OR _retry_one LLM → append corrected real col or mark unmappable. A fabricated column is worse than a missing one."""


# ── v48/layer2/card_input.py ───────────────────────────────────────────────
# DETERMINISTIC assembly of one fan-out unit. Joins 1a story + 1b asset/basket +
# the card's cmd_catalog row + (group cards only) the read-only shared_context ref.

def build_card_input(
    run_id: str,
    card_id: int,
    l1a: Layer1aOutput,
    l1b: Layer1bOutput,
    *,
    group_id: str | None = None,
    shared_ctx_ref: JSON | None = None,
) -> Layer2CardInput:
    """DETERMINISTIC: assemble the per-card Layer-2 input — story (page_story/analytical_story/metric/intent/template_card_ids), asset, column_basket, catalog_row (handling_class/recipe/contract/capabilities/controls/feasibility via load_catalog_row), swap_candidates, is_group_card+shared_ctx_ref. This is exactly what the AI sees per fan-out unit; the AI must author exact_metadata + data_instructions from it."""

def load_catalog_row(card_id: int) -> JSON:
    """DETERMINISTIC: read the full per-card cmd_catalog detail set into catalog_row — card_handling (handling_class, payload_family=the DATA-fill dialect, backend_strategy), card_data_recipe (reconciled_fields|fields = the UNRESOLVED recipe the AI resolves into data_instructions, payload_shape, orientation, entity_dim, selection_dim, selection_role), card_contract_binding→contract_components (payload_schema_json = the per-card payload SHAPE exact_metadata must match its METADATA keys to, canonical_shape, host_cmd_component), contract_capabilities + contract_hardcodes (byte-identical-default sources), card_controls (segmented_tabs/time_options/defaults = the tabs/labels/order seed for exact_metadata), card_feasibility. payload_family resolves the DATA-fill mapper-input shape (flat_series|tiles|scene|…)."""

def swap_pool(card_id: int, template_card_ids: list[int]) -> list[JSON]:
    """DETERMINISTIC: the ±15% card_grid_size pool (closest 6), off-page, card_feasibility.verdict='render_real', NOT in template_card_ids — the offered swap_candidates the gate later validates against (no-dup invariant starts here)."""


# ── v48/layer2/card_run.py ─────────────────────────────────────────────────
# Pure-AI per-card Layer 2 OUTPUT = { exact_metadata, data_instructions } (+ swap
# decision + per-card story + conforms). The AI authors the FINISHED metadata block
# and emits the PARSEABLE data-fill recipe. It never fills DATA or touches chrome.

def layer2_card(card_in: Layer2CardInput) -> Layer2CardOutput:
    """Pure-AI Layer 2 for ONE card (fan-out unit), runs as a gather_llm job. One+ blocking call_qwen authoring the corrected per-card output:
      (1) swap decision — KEEP default; swap only if confidence≥0.9 AND target matches analytical_story AND in pool AND not a duplicate;
      (2) exact_metadata — the FINISHED, byte-identical METADATA block for this card (author_exact_metadata): labels/units/rosters/order/thresholds/contracts/colours/badges/tabs, every metadata key once, defaulted from the card's static config so the resting render is byte-identical, ZERO design-system chrome; for a group card this is the atom's OWN presentation block (three-tier B: lean-on-DATA, fat-on-METADATA);
      (3) data_instructions — the PARSEABLE recipe (author_data_instructions): a resolved card_data_recipe.fields[] (per-field kind/role/metric/label/unit + L3-resolved column + L6-decided agg/source/sql_fragment/base_columns/edge/value) plus the per-card envelope (payload_shape/orientation/entity_dim/selection_dim/binding/window/source). For a group card data_instructions points at the shared buffer (source resolves to `$ctx` — the dotted `$ctx.<buffer>` vs bare-`$ctx`+`buffer_key` form is OPEN/pending user, must match CONTRACTS §5 `source` enum — plus selection_role) and holds NO baked data;
      (4) per-card analytical_story (validated against 1a's angle);
      (5) run validate_card_output.
    conforms=false + failure on an honest gap — NO reloop. The AI does NOT fill DATA values and does NOT mint chrome."""

def author_exact_metadata(card_in: Layer2CardInput, swap_id: int) -> JSON:
    """Pure-AI sub-call (the §B4 metadata producer = buildHeatmapViewModel()/buildHpqPresentation()'s METADATA half). Authors the card's exact_metadata: the finished METADATA keys for its render-payload shape (heatmap: title/metricTabs/metricAxisLabels/statusColors/statusLegend/units/descriptors/selectionColors/bandThresholds/sectionContracts; rail: title/statusBadge.dsTone/supply chrome/trend.lineColor+areaOpacity/quickStats; HPQ per-card HpqPresentation block). Every key once, byte-identical default from contract_capabilities/contract_hardcodes/card_controls, new renderers opt-in default-OFF (e.g. showLegend:false), ZERO chrome. The two 'AI-default, data-overridable' slots (sectionContracts; HPQ signature.spokes/selectedName) are authored as defaults the worker may overwrite."""

def author_data_instructions(card_in: Layer2CardInput) -> JSON:
    """Pure-AI + DETERMINISTIC reconcile (the card-SPECIFIC half of v47 resolve_columns, threaded with recipe_fields). Produce DataInstructions: resolve each card_data_recipe.fields[i].metric → a real column from column_basket (guard_columns post-pass), decide agg per kind (raw→avg/last, derived→derived_metrics.sql_fragment, event→rising-edge count, const→baked value, text→label col), set source per field (`live|test-db|const|$ctx` — the §ctx form for group cards, dotted `$ctx.<buffer>` vs bare `$ctx`+`buffer_key`, is OPEN/pending user and must match the CONTRACTS §5 `source` enum), and attach the envelope {payload_shape, orientation, entity_dim, selection_dim, selection_role, binding{asset_id,table,ts_col,nameplate_scope}, window{lookback,sampling,time_mode}}. The HELPER parses THIS to fill the DATA tier."""

def gate_swap(decision: JSON, pool: list[int], template_card_ids: list[int], already_chosen: set[int]) -> JSON:
    """DETERMINISTIC swap gate (ported from v47 layer2_swap.run): honor a swap ONLY if action='swap' AND confidence≥0.9 AND _criterion_ok (rejects vague better/relevant/nicer/…) AND swap_to_id in pool AND off-page AND not in template_card_ids/already_chosen (no-dup); cascades all-or-nothing. Resolves swap_decision.origin (kept|swapped|must_swap)."""

def validate_card_output(out: Layer2CardOutput, card_in: Layer2CardInput) -> tuple[bool, JSON | None]:
    """DETERMINISTIC: assert the AI emit conforms BEFORE the worker fills. exact_metadata covers exactly the METADATA keys of catalog_row.contract.payload_schema_json (every key once, no second 'root', no duplicate title/sections/contractKw, byte-identical defaults present, ZERO chrome keys); data_instructions.fields[] all resolve to real columns / derived_metrics / consts (no hallucinated column); for a group card data_instructions.source points at a shared_context buffer and holds NO inline data. Returns (conforms, failure|None) — failure is LOGGED, never reloop'd."""


# ── v48/worker/shared_context.py ───────────────────────────────────────────
# DETERMINISTIC Move-1 group pre-pass (relocated L6.2). Builds the ONE shared_context
# per interdependency group (single multi-buffer DATA buffer + interaction seeds)
# BEFORE the fan-out. The buffer is the SINGLE DATA copy; each atom carries its OWN
# exact_metadata (NOT here). The hook owns live state (frontend, in progress).

def build_shared_context(
    group: JSON,
    l1b: Layer1bOutput,
    *,
    db_target: str = "live",
    spec: JSON | None = None,
) -> tuple[SharedContext, JSON | None]:
    """DETERMINISTIC Move-1 worker (relocated L6.2): for one interdependency group build shared_context ($id=group_id, asset, buffers[] each the EXACT typed HistorySample[]-style array + own range/sampling seed + socket_owner=true, interaction seeds, couplings from cmd_catalog, config from card_controls.defaults, apiExtras) ONCE — the SINGLE DATA buffer the group's atoms point at via $ctx. Queries 1b's asset+basket against db_target (live lt_panels OR the test-DB fixture, identical Snapshot shape). AI-provided `spec` knobs the aggregation; worker does the labour. shared_context holds the single DATA buffer + interaction seeds + truly-shared config ONLY — per-card METADATA does NOT live here (each atom carries its own exact_metadata). Functions NEVER appear here (hard invariant). Returns (shared_context, failure|None)."""

def build_buffer(member_spec: JSON, window: str, *, db_target: str = "live") -> JSON:
    """DETERMINISTIC: build ONE windowed buffer (a buffers[] entry) — the time-bucketed HistorySample[] for its members via panel_members/_bucketed against db_target; carries key/range/sampling/socket_owner=true. Multi-buffer (B-gen #2): called once per independently-windowed buffer. The seeded array is the SEED, not the sole source — the live socket stays the live-merge owner (hook-side)."""

def seed_interaction(group: JSON, card_ids: list[int]) -> JSON:
    """DETERMINISTIC (B-gen #1): build SharedContext.interaction — cursor/selection/metric + an open `scalars` map of ANY host-owned scalar/enum (selectedLabel/selectedBucket/selTime/series/tab/compositeView/sampling) seeded READ-ONLY from card_controls.defaults/segmented_tabs; couplings from card_link+selection_dimension. This is the SEED the hook reads into its useState cells (the hook is the live owner; the seed is a useMemo projection, not an independent owner). Functions NEVER included (hard invariant)."""


# ── v48/worker/data_fill.py ────────────────────────────────────────────────
# DETERMINISTIC HELPER: PARSE data_instructions → FILL the DATA tier into the
# Snapshot/frame shape the FE mapper consumes. Two interchangeable sources land
# in the IDENTICAL Snapshot shape: live socket frame OR test-DB fixture. The AI
# NEVER runs here; the worker NEVER touches exact_metadata.

def fill_data(data_instructions: JSON, *, db_target: str = "live", shared_ctx: SharedContext | None = None) -> tuple[JSON, bool, str]:
    """DETERMINISTIC HELPER ENTRY: parse data_instructions and FILL the DATA tier. Branch on the envelope:
      - resolver_scope='panel' (handling_class panel_aggregate/topology_sld) → aggregate_frame (group math via panel_topology) → nested frame DATA;
      - single-asset → fill_single_asset (per-field column reads over the window);
      - a group atom whose data_instructions.source resolves to a shared buffer → fill_from_shared (project the slots out of shared_ctx's single buffer, NO new query).
    (NOTE — OPEN, pending user: the exact `$ctx` source form is unresolved — dotted `$ctx.<buffer>` here vs the bare `$ctx` token + sibling `buffer_key` in CONTRACTS §5; the column-row/queue single-meter family has NO branch here — the `column_row` 4th DATA-fill dialect is a known OPEN gap.) Returns (data_tier, ok, why) — the DATA half of the one payload, in the Snapshot/frame shape the FE mapper targets. Honest-degrade (ok=false) on no data in window / unwired component — NEVER fabricate. The worker fills DATA only; exact_metadata is untouched."""

def fill_single_asset(data_instructions: JSON, *, db_target: str = "live") -> tuple[JSON, bool, str]:
    """DETERMINISTIC: fill the DATA tier for a single-asset card by parsing data_instructions.fields[] and reading each resolved column over the bound window. Per field.agg: raw→avg/last over (binding.table, window); derived→emit derived_metrics.sql_fragment with :NAME nameplate_config literals (scope mfm_type:hv V_NOM=11000 else 415) substituted; event→rising-edge COUNT(*) FILTER over the boolean *_event_active; const→bake field.value (never queried); text→read the label column. Time is ALWAYS :start/:end/:bucket bind params (WINDOW_BOUNDS/_bucket_sql), never literal — re-slice = re-bind. orientation flips the row shape (time|entity|snapshot). Lands in the flat_asset/flat_series Snapshot shape."""

def fill_from_shared(data_instructions: JSON, shared_ctx: SharedContext) -> tuple[JSON, bool, str]:
    """DETERMINISTIC (Approach-B group atom): the data_instructions.source resolves to a shared buffer (the exact form — dotted `$ctx.<buffer>` vs bare `$ctx` + `buffer_key` — is OPEN, pending user; must match the CONTRACTS §5 `source` enum once decided); project the atom's fields[] slots out of shared_ctx's single buffer (NO new DB query — the buffer was filled ONCE in Move 1). Returns a DATA tier that is a VIEW onto the shared buffer, so one buffer update recomputes every atom consistently (mirrors the hook's single-state useMemo derivation)."""

def map_socket_frame(frame: JSON, data_instructions: JSON) -> JSON:
    """DETERMINISTIC: the live path — parse a live socket frame (ws/mfm/{id}/{screen}/, e.g. RTM widgets.feeders[].queue[]) into the SAME Snapshot/HistorySample[] DATA tier the test-DB fixture produces (BAND_KEY_TO_METRIC mapping backend kw/kvar/pf/volt/amp/i_unbal → frontend metric keys). Reference-only in V48 (the worker bakes from the test DB); documents that live and fixture are interchangeable at the mapper boundary."""


# ── v48/worker/panel.py ────────────────────────────────────────────────────
# DETERMINISTIC member resolution + energy math. Ported verbatim from v47
# panel_resolve (the direction gotcha + energy_delta), DB-target-parameterized.

def panel_members(panel_mfm_id: int, *, db_target: str = "live") -> list[JSON]:
    """DETERMINISTIC (ported v47 panel_resolve.panel_members): the bus's members via panel_topology WHERE to_mfm=<panel> — edge_kind='outgoing'→role=source (incomers), 'incoming' (minus from_name ILIKE 'spare%')→role=consumer (feeders); enriched from lt_mfm (panel_id = the time-series WHERE key) + lt_config_value capacity. {mfm_id,name,role,table,panel_id,mfm_type_id,load_group,capacity_kw}. Panels keyed by mfm_id NOT table (PCC-1A=174 / 1B=185 share mfm_lt_115, separable only by topology)."""

def energy_delta(table: str, panel_id: str, ts_from: str, ts_to: str, *, col: str = "active_energy_import_kwh", db_target: str = "live") -> float | None:
    """DETERMINISTIC (ported v47): window energy = value@end − value@start (latest at-or-before each bound, NOT max−min — robust to the non-monotonic sim odometer); panel_id is the time-series WHERE key. db_target selects live lt_panels OR the test DB."""

def now_expr(table: str, *, db_target: str = "live") -> tuple[str | None, str | None]:
    """DETERMINISTIC: the window anchor (select max(ts) from table) + ts column name (ported v47 panel_resolve.now_expr/_ts_col)."""


# ── v48/worker/aggregate.py ────────────────────────────────────────────────
# DETERMINISTIC aggregate builders (relocated L6/L6.2 data-domain math). Self-
# contained — reads raw lt_panels directly, NOT backend2:8889 (reference only).
# Fires for handling_class ∈ {panel_aggregate, topology_sld}. This is the group
# DATA-fill — it produces the DATA tier, never the metadata.

def aggregate_frame(card_id: int, panel_mfm_id: int, *, window: str = "today", spec: JSON | None = None, focus: JSON | None = None, db_target: str = "live") -> tuple[JSON | None, bool, str]:
    """DETERMINISTIC worker (ported v47 l6_2.aggregate_shape): dispatch by the card's frozen contract component (with per-card overrides) → an aggregate builder → compute the DERIVED DATA-tier fields by aggregating panel_members via panel_topology (loss_pct, share_pct, 5-layer sankey, demand points, radar spokes, PQ rows, ai_summary). Reuses EMS semantics verbatim (energy = active_energy_import_kwh value@end−value@start via energy_delta; now_expr = max(ts) anchor; consumers grouped by load_group; capacity_kwh = rated_kw × window_hours). The AI's data_instructions envelope (spec) knobs strategy/window/grouping; validates via validate_aggregate; stamps `focus` AFTER validation. Returns (data_tier|None, ok, why) — honest-degrade, never fabricate."""

def aggregate_builder_for(card_id: int) -> Callable[..., JSON] | None:
    """DETERMINISTIC: resolve the builder for a card — per-card override (_BUILDERS_BY_CARD: 21→current_distribution radar, 22→other_panels_events, 26→feeder_pq) first, else by frozen component (_BUILDERS: EnergyInputDistributionCard→energy_distribution, EnergySingleLineDiagram→panel_overview, DemandProfileCard→demand_profile). None → honest gap (logged, no reloop); panel-TOTAL cards fall back to single-asset since the panel's own meter IS the total."""

def validate_aggregate(payload: JSON) -> tuple[bool, str]:
    """DETERMINISTIC L6.5-style guardrail (ported v47 l6_2.validate): real structure + some non-null data across the recognized shapes (sources/consumers, incomers/outgoings, points, spokes, rows). Returns (ok, why)."""


# ── v48/worker/merge.py ────────────────────────────────────────────────────
# DETERMINISTIC MERGE — the heart of the morph. Flatten the AI's exact_metadata
# and the worker's filled DATA tier into ONE payload per card, every key EXACTLY
# once, no second 'root'. This is what §B4 calls "the one payload per card".

def merge_payload(exact_metadata: JSON, data_tier: JSON, card_in: Layer2CardInput) -> tuple[JSON, bool, str]:
    """DETERMINISTIC: fold exact_metadata (AI METADATA keys) and data_tier (worker DATA keys) into ONE flat payload object, every key EXACTLY once, NO second 'root', NO duplicate title/sections/contractKw, ZERO design-system chrome. Asserts the key sets are DISJOINT except the two 'AI-default, data-overridable' slots — sectionContracts (RTM) and signature.spokes/selectedName (HPQ) — where the worker value (if the frame carried it) OVERWRITES the AI default ({...SECTION_CONTRACT_KW, ...backendSectionContracts}); else the AI default stands. Seeds the initial interaction-state keys (metric/selectedSampleIndex/liveMode/selectedSectionId/selectedFeederId) as a READ-ONLY snapshot the hook will own (group cards from shared_context.interaction; for STANDALONE cards the seed SOURCE is OPEN/pending user — `card_controls.defaults` is the intended source but no current function reads it, one of the un-applied build-spec review fixes). Returns (payload, ok, why) — ok=false on a key collision (the duplicate-root bug) or a missing required metadata field (byte-identical-default violation)."""

def assert_one_payload(payload: JSON, payload_schema_json: JSON) -> tuple[bool, str]:
    """DETERMINISTIC §B4 invariant check: every key appears EXACTLY once; no 'root'/'data'/'metadata' wrapper key (flat namespace); every METADATA field in payload_schema_json is PRESENT and populated (producer-always-populates); new-renderer flags default OFF (showLegend:false). Returns (ok, why). The LIVE Storybook-sentinel mutate-one-field DOM check is the acceptance gate ON TOP of this (golden-payload comparison alone hides dead fields)."""


# ── v48/stitch/stitcher.py ─────────────────────────────────────────────────
# DETERMINISTIC Move-3 stitcher + page assembler. Merges each card's metadata+data
# into its one payload, bundles group atoms + their shared_context into the page
# frame. $ctx↔$id resolution. Each card stitched exactly once (no-dup).

def stitch_card(card_out: Layer2CardOutput, card_in: Layer2CardInput, *, db_target: str = "live", shared_ctx: SharedContext | None = None) -> tuple[JSON, bool, str]:
    """DETERMINISTIC Move-3 per-card: fill_data(card_out.data_instructions, …) → data_tier, then merge_payload(card_out.exact_metadata, data_tier, …) → the ONE payload for this card. For a group atom the data_tier is a VIEW onto shared_ctx's buffer (fill_from_shared) so the atom holds NO data copy but carries its OWN exact_metadata (three-tier B). Returns (card_payload, conforms, why) — conforms=false propagated into failures[], the card left unfilled."""

def stitch_group(shared_ctx: SharedContext, atoms: list[JSON], card_inputs: dict[int, Layer2CardInput], *, db_target: str = "live") -> JSON:
    """DETERMINISTIC Move-3 group: for each lean atom run stitch_card (data_tier = projection of shared_ctx's single buffer), attach $ctx, and bundle {shared_context, cards:[merged atom payloads]} for ONE group; asserts every atom.$ctx resolves to shared_ctx.$id (the identity chain group_id↔$id↔$ctx) and the buffer is stored ONCE (atoms reference it, never copy it). No-dup: each card stitched exactly once."""

def assemble_page_frame(
    l1a: Layer1aOutput,
    shared_contexts: list[SharedContext],
    card_outputs: list[Layer2CardOutput],
    card_inputs: dict[int, Layer2CardInput],
    *,
    config_endpoint: JSON | None = None,
    db_target: str = "live",
) -> PageFrameEnvelope:
    """DETERMINISTIC: assemble the final PageFrameEnvelope — carry layout from 1a; for each group bundle its shared_context + stitched atom payloads (stitch_group); for each standalone card run stitch_card → its one merged payload; attach config_endpoint (the y-axis nameplate side payload not in the WS frame). `data_fill_shape` (the RENAMED former `frame_dialect`, per CONTRACTS §8) describes the DATA-fill source shape — enum `shared_context | flat_asset | widgets_envelope` (NOT the `payload_family` vocabulary `flat_series/tiles`; G6 crosswalk + the missing `column_row` 4th dialect + the derivation source are OPEN, pending user) — NOT what the AI emits; every card carries its own merged one-payload regardless. Reproduces quirks (load_factor_pct fraction, synthetic loss node mfm_id:null, pending/error union)."""

def build_config_endpoint(asset: JSON, *, db_target: str = "live") -> JSON:
    """DETERMINISTIC: populate GET /api/mfm/{id}/config/ (rated_kw nameplate, MfmConfigResponse) for y-axis auto-scale — the side payload NOT on the one-payload nor in the WS frame. Returns PageFrameEnvelope.config_endpoint."""


# ── v48/orchestrator.py ────────────────────────────────────────────────────
# The harness: fires on a frontend prompt, runs 1a∥1b (ThreadPoolExecutor),
# joins, partitions, fans out Layer 2 per card with a one-time group pre-pass,
# fills + merges + stitches, emits. NO reloop / NO re-route — failures accumulate.

def run_pipeline(pipeline_input: PipelineInput) -> OrchestratorState:
    """ENTRY (synchronous; concurrency via ThreadPoolExecutor so the ai_log urllib patch sees every call). Install ai_log FIRST; run kickoff_1a_1b (1a∥1b) → join; if 1b ambiguous → write asset_choice.json, phase='awaiting_asset_choice', return (AssetPicker re-runs with PIPELINE_ASSET_ID). Else partition → run_layer2 (group pre-pass + per-card fan-out emitting {exact_metadata, data_instructions}) → worker fills DATA + merges into one payload + stitches → assemble_page_frame → emit. Returns the final OrchestratorState (page_frame + failures[]). No reloop/re-route."""

def kickoff_1a_1b(pipeline_input: PipelineInput) -> tuple[Layer1aOutput, Layer1bOutput]:
    """Fire route_1a and (resolve_asset_1b → resolve_basket_1b) CONCURRENTLY via gather_llm (ThreadPoolExecutor) the moment the prompt arrives; JOIN — Layer 2 cannot start until BOTH complete. Each runs a blocking call_qwen through the patched urllib.request.urlopen (so both are ai_log'd). Returns (l1a, l1b)."""

def run_layer2(state: OrchestratorState) -> list[Layer2CardOutput]:
    """Layer-2 orchestration. partition_groups → for EACH interdependency group: run the ONE-TIME group pre-pass build_shared_context (Move 1) SYNCHRONOUSLY FIRST, THEN gather_llm the per-card layer2_card atoms (Move 2, ThreadPoolExecutor); standalone cards fan out in the SAME gather_llm. Threads template_card_ids/already_chosen so no parallel run duplicates a card. Each card's AI output {exact_metadata, data_instructions} is then handed to the worker (fill_data → merge_payload) at stitch time. Returns all card_outputs."""

def fanout_group(group: JSON, shared_ctx: SharedContext, state: OrchestratorState) -> list[Layer2CardOutput]:
    """Move 2 for one group: build each card's Layer2CardInput (with shared_ctx_ref) and gather_llm layer2_card across the group's cards IN PARALLEL (ThreadPoolExecutor) — the pre-pass shared_context already built. Lean atoms only: each emits its OWN exact_metadata + a data_instructions pointing at the shared buffer via `$ctx` (the exact `$ctx` source form is OPEN/pending user; no baked data)."""

def fanout_standalone(card_ids: list[int], state: OrchestratorState) -> list[Layer2CardOutput]:
    """Move 2 for edgeless cards: gather_llm layer2_card per standalone card IN PARALLEL (ThreadPoolExecutor); each skips Move 1 and emits exact_metadata + a data_instructions whose source is live|test-db (self-contained). Same fan-out tier as the groups."""

def emit_asset_choice(state: OrchestratorState, l1b: Layer1bOutput) -> JSON:
    """DETERMINISTIC: when 1b is ambiguous, write asset_choice.json {needs_asset_choice:true, prompt, mention, candidates:candidate_list} (mirror of v47) and set phase='awaiting_asset_choice'; the frontend AssetPicker re-runs pinned via PIPELINE_ASSET_ID."""

def log_failure(state: OrchestratorState, stage: str, reason: str, *, card_id: int | None = None, group_id: str | None = None, detail: str | None = None) -> None:
    """DETERMINISTIC: append an exact-error record to OrchestratorState.failures[] (stage ∈ routing|asset|columns|partition|shared_context|swap|fill|merge|aggregate|emit). LOGS only — NEVER triggers reloop/re-route (unlike v47 L4/L1). The card/group is left unfilled with conforms=false."""

def emit_output(state: OrchestratorState) -> JSON:
    """DETERMINISTIC: serialize the final OrchestratorState → {page_frame, config_endpoint, failures, log_path} for the frontend; phase='done' (or 'failed' if no card produced a conforming one-payload)."""
```

### Notes the build must honor (grounded in the read source)

- **The LLM seam is SYNCHRONOUS urllib, concurrency via `ThreadPoolExecutor` — NOT asyncio.** `call_qwen` is `pipeline.llm()` (temp 0, `response_format=json_object`, `chat_template_kwargs.enable_thinking=False`) issued through `urllib.request.Request` + `urllib.request.urlopen`. `ai_log.py` monkeypatches **`urllib.request.urlopen`**, so any client that did NOT go through `urllib` (e.g. an `httpx`/`aiohttp` async client) would BYPASS the logger and lose `logs/ai_<run_id>.jsonl`. Therefore 1a∥1b and the per-card fan-out run on a `ThreadPoolExecutor` (`gather_llm`), where each worker thread issues a BLOCKING `urlopen` the patch still intercepts. `install_ai_log` is imported FIRST. (`/home/rohith/desktop/BFI/backend/layer2/pipeline_v47/ai_log.py` patches `urllib.request.urlopen`; `pipeline.py:185-186` issues the call via `urllib.request.urlopen`.)

- **Layer 2 per-card OUTPUT is `{ exact_metadata, data_instructions }`** (Decision A, hybrid). `author_exact_metadata` is the §B4 metadata-producer half (`buildHeatmapViewModel()`/`buildHpqPresentation()`'s METADATA tier) — the FINISHED, byte-identical METADATA block. `author_data_instructions` is the card-SPECIFIC half of v47 `resolve_columns` (threaded with `recipe_fields`) + the L6 agg/source decision — a resolved `card_data_recipe.fields[]` plus the per-card envelope. The AI authors BOTH; it NEVER fills DATA values and NEVER mints design-system chrome.

- **The HELPER/worker PARSES `data_instructions` and FILLS the DATA tier** — `fill_data` branches by scope: `panel`→`aggregate_frame` (group math via `panel_topology`), single-asset→`fill_single_asset` (per-field column reads over the window), group-atom→`fill_from_shared` (project slots out of shared_context's single buffer, no new query). Two interchangeable fill sources land in the IDENTICAL Snapshot shape — live socket frame (`map_socket_frame`, reference) OR the test-DB fixture (the V48 worker bakes from the test DB). The worker NEVER touches `exact_metadata`.

- **The MERGE is the morph's core invariant.** `merge_payload` flattens `exact_metadata` + filled DATA into ONE payload per card, every key EXACTLY once, no second `root`, no duplicate `title`/`sections`/`contractKw`, ZERO chrome. The only overlap allowed is the two "AI-default, data-overridable" slots — `sectionContracts` (RTM) and `signature.spokes`/`selectedName` (HPQ) — where a worker value overwrites the AI default. `assert_one_payload` enforces §B4 (every key once, flat namespace, producer-always-populates, opt-in default-OFF).

- **The "dialect" survives ONLY as the DATA-fill / mapper-input shape**, NOT as a Layer-2 output. `card_handling.payload_family` (`flat_series`/`tiles`/`scene`/…) names the backend-frame shape the worker fills; `data_fill_shape` (the renamed `frame_dialect`, enum `flat_asset|widgets_envelope|shared_context` per CONTRACTS §8) in `assemble_page_frame` describes the DATA-fill source shape, never what the AI emits. The `payload_family`→`data_fill_shape` crosswalk, the missing `column_row` 4th dialect, and where `data_fill_shape` is derived (not a DB column) are OPEN (pending user). Every card carries its own merged one-payload regardless of dialect.

- **The group pre-pass is sequenced before the fan-out**, not inside it: `run_layer2` runs `build_shared_context(...)` (Move 1) SYNCHRONOUSLY, THEN `gather_llm(layer2_card...)` (Move 2). `shared_context` holds the SINGLE DATA buffer + interaction seeds + truly-shared config ONLY — **per-card METADATA does NOT live there**; each lean atom carries its OWN `exact_metadata` (three-tier Approach B: lean-on-DATA, fat-on-METADATA). The buffer is stored once; atoms reference it via `$ctx`, never copy it.

- **Hook-integration note (frontend-side, IN PROGRESS).** UI-selection state is a THIRD class owned by the hook (`useRealTimeMonitoringData` in RTM: the five `useState` cells `liveMode`/`selectedSampleIndex`/`selectedFeederId`/`selectedSectionId`/`metric` + all `handle*` setters), NOT by Layer 2 nor the worker. Each card's merged payload carries only a READ-ONLY SEED of that state (a `useMemo` projection, not an independent owner); writes flow UP via hook setters (one emit → one setter → all interdependent atom payloads recompute consistently). The Approach-B per-atom `exact_metadata` block is grounded on the RTM hook structure but the broader cross-card group wiring is **STILL IN PROGRESS on the frontend — mark provisional**. The worker-side re-slice analog (re-bind the window/selection and re-fill, the EMS `sendSelectedPeriod`/`sendSelectedPanel` equivalent) lives at the reslice endpoint; the FE atom `presentation`/metadata wiring is the open frontend piece.

- **Worker is DB-target-parameterized** via the `db_target` kwarg on every data-touching function (`panel_members`, `energy_delta`, `aggregate_frame`, `build_shared_context`, `build_buffer`, `fill_data`, `fill_single_asset`) so the identical code runs against live `lt_panels` or the test DB per `PipelineInput.env.DB_TARGET`. The test-DB fixture lands in the IDENTICAL Snapshot shape so live and fixture are interchangeable at the mapper boundary.

- **The direction gotcha and energy math are ported, not re-derived** (`panel_resolve.panel_members`: `to_mfm=<panel>`, `outgoing→source`, `incoming` minus `spare%`→`consumer`; `energy_delta` = value@end−value@start via two at-or-before probes, NOT max−min; panels keyed by `panel_id`/`mfm_id`, never table). `aggregate_frame` is `l6_2.aggregate_shape` with the AI `spec`/`data_instructions` envelope upgraded from the deterministic `card_config`.

- **No-dup is enforced both in-prompt and deterministically** — `gate_swap` carries `template_card_ids` + `already_chosen`, and `run_layer2` threads `already_chosen` across the parallel runs so no two concurrent `layer2_card` calls swap in the same card; `stitch_card`/`stitch_group` stitch each card exactly once.

- **No reloop/re-route**: the only failure path is `conforms=false` → `log_failure` → `failures[]`; there is no `need_reroute`/`avoid_ctx` re-entry (the `avoid_ctx` param on `route_1a` is retained only as an optional first-pass nicety, never re-driven). The card/group is left unfilled.

- **Buildable-today caveat:** the one-payload `{exact_metadata, data_instructions}` contract has **RTM + panel-overview HPQ** as its VALIDATED reference templates (the §B4 references), but morph adoption is WIDESPREAD — the live Storybook §B4 sentinel (2026-06-29) shows ~36/59 EMS cards strongly/moderately payload-driven across ALL panels, NOT just the 2 reference tabs (the old "~7 cards / 2 tabs" PAYLOAD_AUDIT_ALL claim is SUPERSEDED; see V48_STORYBOOK_MORPH_VERIFICATION.md). A ~23-card weak/zero punch-list remains — V&C hardcoded sub-cards (415V/237A + the `Max:430KW` unit bug), some aggregate cards, Energy-Distribution/Energy-Power partially verified; for those V48 either waits for the CMD V2 morph or emits the DATA half with hardcoded chrome. Mark provisional. Acceptance is the LIVE mutate-one-field Storybook sentinel (`:6008`, read the card DOM) — green RTL tests + byte-identical defaults hid 3 real RTM gaps.

Relevant grounding files (all absolute): `/home/rohith/desktop/BFI/backend/layer2/pipeline_v47/column_resolve.py`, `/home/rohith/desktop/BFI/backend/layer2/pipeline_v47/pipeline.py`, `/home/rohith/desktop/BFI/backend/layer2/pipeline_v47/panel_resolve.py`, `/home/rohith/desktop/BFI/backend/layer2/pipeline_v47/l6.py`, `/home/rohith/desktop/BFI/backend/layer2/pipeline_v47/l6_2.py`, `/home/rohith/desktop/BFI/backend/layer2/pipeline_v47/ems_aggregate.py`, `/home/rohith/desktop/BFI/backend/layer2/pipeline_v47/layer2_swap.py`, `/home/rohith/desktop/BFI/backend/layer2/pipeline_v47/ai_log.py`; the morph references `/home/rohith/CMD_V2/CLAUDE.md` (§B4) and `/home/rohith/CMD_V2/src/pages/electrical/lt-pcc/panel-overview/{realtime-monitoring,harmonics-pq}/`; correction doc `/home/rohith/desktop/BFI/backend/layer2/pipeline_v48/V48_PAYLOAD_MORPH_CORRECTION.md`; contracts `/home/rohith/desktop/BFI/backend/layer2/pipeline_v48/V48_BUILD_SPEC_CONTRACTS.md`.
