# Pipeline V48 — Design Notes

> Scribe log. Captures the user's ideas verbatim as discussed. No deviations, no hallucinations.
> Started: 2026-06-23

---

## Premise

- Reworking **pipeline V47 → V48**: a much simpler, straightforward pipeline.
- V48 has **exactly 3 layers**: **1a**, **1b**, **2**. No more.
- **All 3 layers are pure AI layers** — the AI is the decision-maker in each.
- **Qwen 3.6 is mandatorily invoked** in every layer (1a, 1b, 2). No layer runs without an actual Qwen 3.6 call; the model is non-optional.
  - (grounding, from project memory) Qwen 3.6 = `Qwen3.6-35B-A3B-FP8` on the vLLM backend at `:8200`.
- There will be **deterministic functions/code in between** the layers, but their purpose is **only to support the AI layers** (plumbing/feeding/serving) — never to make the decisions themselves.

---

## ⚖️ GUIDING RULE #1 — Atomic Structure (VERY IMPORTANT)

- The **entire V48 codebase + folder must follow an atomic structure**: **one dedicated, single-purpose file per concern.** Never one big file holding all the code + prompts + references mixed together.
- Applies to **everything we add** — DBs, prompts, code, references. Each gets its own dedicated file.
- **Why:** any change has an obvious single place to be made (localized edits); the pipeline stays **end-to-end smooth and reusable**; no monolith to untangle.
- **Concrete implication:** a prompt is its own file (not inline in a module); each DB/table concern its own module; each layer is a *small folder of single-purpose pieces* (its prompt, its DB reads, its parser, its output schema) — not one file.
- **★ Rule #1b — PROVISION atomisation (config/):** every **tunable** — an allow-list, a vocab, a threshold, a DB name, a feature flag, an open-decision toggle — lives in its **own dedicated editable file under `config/`** (one knob-set per file). Layers **READ from `config/`, never hardcode** a tunable. So a page, metric, window, or flag can be **added/removed/changed without touching layer code**. Examples: `config/available_pages.py` (add/remove routable pages), `config/metrics.py` + `config/intents.py` (vocab), `config/windows.py`, `config/swap.py` (gate params), `config/dialects.py`, `config/payload_shapes.py`, `config/flags.py` (open-decision toggles). Every open item also gets a `config/flags.py` toggle, not just a doc.

### Reference: the "atomic structure in place" (CMD_V2) — the SPIRIT to mirror
Decompose to the smallest meaningful unit; compose only at the boundary. Three nested levels + the data flow that fills them:
- **L1 — leaf atom (presentation):** a metric is never a fused string; it's `{ value, unit, separator, label, decimals, (qualifier) }` × a semantic visual token (`CHART_COLORS.*`, `SURFACES.*`, `TYPOGRAPHY.*`, never raw hex), composed at the render boundary via `composeValueUnit(value, unit, sep)` / `composeMetricText(...)`.
- **L2 — payload atom (data binding):** each card's payload = an array of atomic field bindings in `cmd_catalog.card_data_recipe.fields` (jsonb). Each field = self-describing tuple `{ kind, role, label, metric, unit }`. `kind` ∈ raw(345)/derived(166)/const(137)/text(231)/event(16); `role` ∈ series/kpi/column/line/spoke/cell/segment/narrative; `metric` = binding key into lt_panels / derived_metrics.
- **L3 — composed shape:** field atoms compose into one of the 10 canonical `payload_shapes` (TilePayload, SeriesPayload, RadarPayload, SankeyPayload, …); `role` decides which slot of the shape an atom lands in. Cross-card behaviour is its own atom: `selection_dimension` (14).
- **Data flow:** `lt_panels` raw col / `derived_metrics.sql` / const-nameplate → **field atom** (kind+metric+unit) → **payload_shape JSON** → component; backend frame → mapper → Snapshot → viewModel → **leaf atoms** (`composeValueUnit` + tokens).

> V48 mirrors this dedicated-unit-per-concern discipline at the **file/folder level**, not just the data level.

---

## Hard Dependency: CMD V2

- All 3 layers are **dependent on the CMD V2 frontend and backend** — **most importantly the frontend and design**.
- The AI layers do **not** invent output freely; what 1a/1b/2 produce must **conform to what the CMD V2 frontend + design expects** (its cards / component + design contract). The frontend + design is the anchor; the layers serve it.
- **Location:** `/home/rohith/CMD_V2` — Vite + React + TypeScript app (Storybook, `src/`, `src/features`, `src/data`), backend API specs (`BACKEND_API_SPEC*.md`), 3D/SLD assets, `prodo/` deploy.
- **User: these panels' cards are >90% atomized to take from the payload** — **Panel Overview** (Energy & Distribution, Energy & Power, Harmonics & PQ, Real-Time Monitoring, Voltage & Current) and **Equipment Detail** (Voltage & Current, Real-Time Monitoring, Energy & Power, Power Quality). So Layer 2's emitted frame fills ~all card content; the residual <10% is non-payload chrome (functions/static) that stays in the FE (consistent with "functions never travel in payload"). These are the low-risk, high-fit panels for the payload-driven approach.

---

## Hard Dependency: `cmd_catalog` DB (shared input to ALL 3 layers)

- The V47 metadata DB **`cmd_catalog`** (Postgres; `psql -U postgres -d cmd_catalog`) holds all metadata about templates, cards, contracts, layouts, etc.
- **It is the shared INPUT for all 3 layers** (1a, 1b, 2). Every layer reads from this DB.
- Confirmed live structure (post-rebuild, 2026-06-29): **145 cards (135 live, max id 176)**, **75 page_specs**, **280 components**; status columns present. (The OLD "28 tables + 2 views, 116 cards / 29 page specs / 12 page areas" snapshot is STALE.)
- Core spine: `cards.page → pages.area`, `cards.primary_component → components.name`, `card_* → cards.id`, `page_layout_cards / page_spec_cards → page_specs.page_key`. **Per-card render shape lives in `card_handling` / `card_data_recipe.payload_shape` — there is NO dedicated dialect column.**
- Full table-by-table reference (purpose, sample rows, which layer each feeds): see `V47_DB_REFERENCE.md` (being generated).

---

## Testing: dedicated test DB (to be created)

- For **testing the pipeline** and the **payloads of the CMD V2 cards**, we will create a **separate test DB** populated with the necessary details.
- Purpose: exercise/validate the pipeline's output payloads against known/controlled data instead of depending on the live EMS feeds.
- This is a **distinct DB** from:
  1. `cmd_catalog` — metadata, the shared *input* to all 3 layers.
  2. the live EMS / `lt_panels` time-series — the real data.
- Status: **to be created.** (Open: exact contents — mock EMS readings? expected/golden payloads? both? — to be defined.)

---

## Execution Model (wiring)

- On **prompt** arrival, **Layer 1a and Layer 1b are kicked off simultaneously** (parallel; both triggered by the prompt).
- **Layer 2 depends on the output of BOTH 1a and 1b** — it cannot start until 1a and 1b are both done.
- **Layer 2 runs in parallel across ALL cards** — fired concurrently per card, **not sequential** card-by-card.
- User: the run harness **fires when a prompt is sent from the frontend** (frontend prompt → kicks off 1a + 1b).

```
frontend prompt ──┬──► [1a] ──┐
                  └──► [1b] ──┴──► [2]  (fan-out: one parallel run per card)
```

---

> Recorded from the user's statements + the brainstorm whiteboard. Only what the user said.

## Layer 1a

- User: 1a is **similar to Layer 1 of V47**.
- From sketch: 1a produces the **Template** (and the page/cards side).
- User: **1a chooses which page TELLS THE STORY BEST** — NOT asset-matching, NOT metric/keyword matching (the asset is 1b's separate job). 1a is the **narrative/storytelling router**.
- **★ CORE PRINCIPLE (very fundamental):** a **template is NOT asset-specific — it is a CARDS-COMBO.** 1a picks the template whose **cards-combo best serves the prompt, for ANY asset.** Templates are **asset-agnostic**; whatever asset 1b resolves is plugged in. ⇒ **No asset↔page compatibility check** — any template works with any asset. If a specific card can't *fill* from the resolved asset's data, that's a **per-card data concern** handled downstream (1b column basket + Layer 2 per-card resolve → swap or log), never a page/shell gate.
- User: **1a ALSO outputs a per-card analytical story** — after choosing the template, for **each card** in it, **what story that card tells wrt its role/function + the prompt**. A prompt-specific story; a **different kind** from the static card details stored in the DB.

## Layer 1b

- User: 1b should **check the DB metadata + schema**, **resolve the appropriate asset w.r.t. the prompt**, and produce **all the relevant column basket for Layer 2**.
- User: the **column basket = ALL possible relevant tables AND columns that could possibly answer the prompt.** It is **NOT dependent on the template/cards** (prompt-driven, card-agnostic) — that is exactly why it lives in 1b.
- User: **asset-resolve → 1b.** Also **part of V47's L3 → 1b** — the **card-agnostic part** — **because at 1b time we don't fully know the template + cards chosen by 1a** (1a and 1b run in parallel).
- User: **1b must ALSO output the candidate ASSET LIST** for UI disambiguation — like V47, when the asset is ambiguous the user selects it from a list shown in the UI.
- User: **asset picker round-trip is IN (confirmed)** — ambiguous → list → user picks → re-run pinned (like V47 `PIPELINE_ASSET_ID`).
- From sketch: 1b's outputs = **Asset + Columns**.

## Validation Layer — NON-AI, between {1a, 1b} and Layer 2 (user, 2026-06-30) ✅ BUILT

- User: *"i want a **data validation layer before layer 2**. 1b already resolves columns right and 1a already selects the cards. so i want a **non ai layer using pandas** to **validate data and payload**."*
- **Position:** runs AFTER 1a∥1b finish, BEFORE Layer 2. Sequential (depends on both). Pure deterministic — **no Qwen**.
- **Inputs (already produced):** 1b's resolved **column basket** (this asset's real `lt_panels` columns) + 1a's **selected cards**, whose **default payloads + per-leaf roles** now live in `cmd_catalog.card_payloads` (see [[v48-card-payloads-db]]).
- **Validates BOTH** (user decision): **(1) data** — pull the asset's real rows into pandas, per basket column check present / null-rate / latest-ok / dtype / series-capable; **(2) payload-fillability** — for each selected card's default payload, can its **DATA leaves** be filled by the validated columns (demand-vs-supply counts; coarse, NOT the semantic binding — that's Layer 2's job).
- **Deterministic leaf split (no AI):** a payload leaf is **DATA** if numeric / numeric-array / time-series; **METADATA** if string / bool / color / unit. (The morph is per-leaf — most content objects are "mixed" — so classify at the leaf by TYPE.)
- **On-failure policy = DEFERRED** (user: "we will decide later") → default **annotate-only** (attach pass·warn·fail + reasons; never drops/blocks). Toggle later via `config/validation.FAILURE_POLICY` (annotate | drop | fail) without touching layer code (Rule #1b).
- **Output:** `{verdict, data:{columns[…]}, payload:{cards[…]}}`; `asset_pending` when 1b is ambiguous/empty (asset picker must resolve first). Wired into `run/harness.py` → `out["validation"]`.
- **Files** (`validate/`): `data_load · data_validate · leaf_classify · payload_validate · payload_lookup · report · schema · build`; knobs in `config/validation.py`. Live AHU-5 voltage-current: 0.12s, pass (45/45 cols, 3/3 cards fillable). This is the V48 clean-room of **V47's L4 feasibility job**.

## Layer 2

- User: Layer 2 is **similar to Layer 2 of V47**.
- User: Layer 2 runs **in parallel for every card** (not sequential).
- User: **the DB's per-card details → Layer 2 to decide swapping** — cmd_catalog holds all kinds of details of every card; these are handed to Layer 2 to make the swap decisions.
- User: **swap dedup rule** — Layer 2's swap **takes 1a's story into account** and **must NOT swap in a card already chosen by 1a as part of the template**. So 1a's chosen card set is respected and a swap can never duplicate an existing template card (prevents collisions across the parallel per-card runs).
- User: **the other part of V47's L3 → Layer 2** (the card-specific part, which needs the chosen cards), **plus V47's L4 job → Layer 2.**
- User: the **updated CMD V2 card payloads take a simple, straightforward payload**, provided directly in **appropriate JSON format by a layer** → so the emit is just JSON (lands in Layer 2).
- From sketch: **Layer 2 = prompt-based analytical story + validation of payload** → outputs **Card Analysis** + **Payload**. (Each card gets an analytical story wrt the prompt; Layer 2 validates the payload before emitting.)
- User: **data fill = a hybrid (combo of a + b):**
  - **(a)** deterministic support code under Layer 2 **queries the test DB** — **"purely labour work"** (just the grunt fetching), **and**
  - **(b)** Layer 2 also emits **payload structure + bindings** so the **CMD V2 backend can fill live values** at render.
  - **Per-card flexible — must handle BOTH cases:** **bindings-only (b)** for the **live-data** case; **baked-in (a)** where baking-in is needed. Decided **per card**.
  - **Layer 2's AI decides HOW** to query/shape; the deterministic code only executes the labour. (Reinforces rule: AI decides, deterministic code supports.)

### Layer 2 emit model — post payload-morph (Decision A, RESOLVED 2026-06-29)

Per the CMD V2 payload-morph (one payload per card = `{data + metadata}`, §B4), Layer 2's per-card output is a **HYBRID of "be the producer" (for metadata) + "instruct" (for data)**:
- **METADATA → Layer 2 gives it EXACT.** The AI authors the finished presentation block (labels, units, rosters, order, thresholds, contracts, colors, badges, tabs) — the actual final values.
- **DATA → Layer 2 gives parseable INSTRUCTIONS, not the data.** The AI emits a readable recipe telling the **hook/helper functions HOW to fill the data** (which metrics/columns/aggregations/source; live-bindings vs baked-from-test-DB per card). The **hook/helpers parse + fill the data** and keep owning the **live state + interactivity + interdependency**.
- So **Layer 2 per-card output = `{ exact_metadata, data_instructions }`.** Helpers run the instructions → data; metadata + data merge into the one payload; the hook owns live behavior.
- Fits the core rules: AI decides HOW (authors metadata + recipe), deterministic helpers labour (fill data). Supersedes the stale "Layer 2 emits the whole per-tab frame" model — see `V48_PAYLOAD_MORPH_CORRECTION.md`.

### Layer 2 DATA source — reuse CMD V2's EMS backend DIRECTLY (user, 2026-06-29) ★ AUTHORITATIVE
- **User: "for data there is a mechanism in EMS backend we can use" + "use CMD V2 directly only. just add to plan."**
- **So the DATA half is NOT a fresh V48 worker, NOT a fixture, NOT self-contained re-implemented math.** Layer 2 reuses the **real CMD V2 EMS backend consumer strategies directly** (`/home/rohith/CMD/backend` — `lt_panels/consumers/<view>/<panel>.py` + `assets/consumers/<class>/<view>.py`, fed by `assets/services.py`: `fetch_live` / `fetch_bucketed` / `fetch_window` / `resolve_range` + `_timefilters`). **No copy** (V45/V47 forked a copy → `ems_backend`; V48 does NOT — uses CMD directly).
- **The card→mechanism binding already exists in metadata:** `cmd_catalog.card_handling.backend_strategy` names the exact consumer per card (e.g. RTM heatmap → `consumers/real_time_monitoring/pcc_panel.py`; UPS battery → `assets/consumers/ups/battery_autonomy.py`). ~45 cards point at a consumer; ~78 are blank (narrative / nav / sld / 3d — no time-series DATA). This field is already surfaced in the Layer-1a output `handling{backend_strategy}`.
- **So `data_instructions` (the AI's 2nd output) = the PARAMETERS that drive the chosen consumer** — which asset (1b's `mfm_id`), which preset/range, which sampling, which widget, which selected bucket — **not** a hand-rolled fill recipe. The consumer produces the widget DATA; the per-widget interactivity (timeline_time / selected_panel / selected_period) already lives inside the consumer = the "interactivity retained as in EMS."
- **⇒ SUPERSEDES the earlier line ("L6/L6.2 data-aggregation RELOCATES into self-contained V48 worker functions; NOT a reuse of backend2; V48 implements the math self-contained").** That note is now OBSOLETE: the aggregation does NOT get re-implemented in V48 — it is **sourced from CMD's own consumers directly.** (`Retire/relocate` table updated below.)
- **Call surface — SETTLED (2026-06-29, post hardcoding audit): drive a WS dispatcher by `(resolved mfm_id, page-endpoint)`.** Not a fixed strategy file, not an in-process adapter. The dispatcher (`ws/mfm/<mfm_id>/<endpoint>/`) picks the **class-correct** strategy for the resolved asset and gives `?columns=` + interactivity + graceful degradation for free; an in-process adapter would have to re-implement `resolve_category`/`STRATEGIES`. So `card_handling.backend_strategy` is read as **(view/page-endpoint + representative class file)**, and the *actual* strategy = `STRATEGIES[resolved_asset_class]`. See `findings/ems_backend_hardcoding.md`.
- **UPDATE (2026-06-29, user: "for now copy the backend to v48 and rename it appropriately"): the WS dispatcher we drive is now V48's OWN copy — `pipeline_v48/ems_backend/` (verbatim fork of `/home/rohith/CMD/backend`, 148/148 `.py`).** This **reverses the earlier "use CMD directly, no copy"** for the call surface: V48 owns + adapts its EMS backend (chiefly to wire `mfm_type_id → lt_parameter` column-sourcing) **without touching live CMD**. `"for now"` = pragmatic; may revisit. Boundary: all EMS edits land in `ems_backend/`, never in `/home/rohith/CMD/backend`. Provenance: `ems_backend/V48_PROVENANCE.md`.

#### Hardcoding check (user, 2026-06-29: "there is hardcoding in EMS backend… of tables and columns") — hands-on audit → `findings/ems_backend_hardcoding.md`
- **TABLES are NOT hardcoded** — every consumer reads `self.mfm.db_link/table_name/panel_id` from the registry row keyed by the URL `mfm_id`; aggregate rosters come from the topology graph (`mfm.incoming/outgoing`); strategy is picked by asset name/type. So a 1b-resolved asset flows straight through. **This is the green light for reuse-by-resolved-asset.**
- **COLUMNS *are* hardcoded** — each strategy carries literal per-(view×class) column maps (RTM `_METRIC_COLS`/`_FETCH_COLS`, V&C `_EVENT_COLS`). BUT **column-tolerant**: services introspect the real table and drop+None-pad absent columns (cross-class degrades, never errors); column-row strategies also accept a `?columns=` override (aggregate ones do not).
- **⇒ REFINES the `data_instructions` knob list above:** the AI controls **`{asset mfm_id, range/preset, sampling, widget, selection-commands}` — NOT the column list.** Columns are the consumer's fixed recipe (good: no AI-invented column math). The 1b basket therefore feeds **upstream metric/asset selection**, not the consumer read-list. Consumer columns == `lt_parameter.column_name` (same vocabulary as the basket).
- **Constraint:** a consumer returns correct DATA only where the resolved asset's table has its assumed columns (full same-class; graceful-blank cross-class). So `card_handling.backend_strategy` must agree with the resolved asset's class — else accept blanks + **log** (no reloop).
- Hardcoded thresholds (`415V` nominal, severity bands) are **cosmetic** (colouring/derived math), not data-sourcing; in-code TODO to move to per-MFM config.

### Verified payload contract (see `CMDV2_PAYLOAD_VERIFICATION.md`) — ⚠ SUPERSEDED (historical snapshot; kept for history)

> **SUPERSEDED 2026-06-29 by Decision A (morph correction above).** The OLD "Layer 2 emits the whole per-tab frame" + "two frame dialects emitted by Layer 2" model NO LONGER HOLDS. Current canon: Layer 2 per-card output = `{ exact_metadata, data_instructions }` — Layer 2 does NOT emit the frame. The per-tab "dialects" survive ONLY as the **data-fill (mapper-input) shape** the helper targets (`data_fill_shape`), NOT as Layer 2 output. Read this subsection as background; the morph-correction section above is authoritative.

- **Cards take a plain-JSON FRAME** at the backend-frame boundary (the `mapper.ts` input). The frontend keeps `mapper → viewModel → Cards.tsx` **as-is**. (HISTORICAL: this section once said "Layer 2 directly provides that whole frame JSON" — superseded; helpers fill the data per Layer 2's `data_instructions`, frame is not a Layer 2 output.)
- The "pre-computed strings" in the frame (KPI value strings, status enums, captions, `ai_summary`) come from a source today, but that is **irrelevant** — since the payload is provided per the morph contract, raw-vs-preformatted doesn't matter. (Caveat about "simple vs raw" → dissolved.)
- **Frame dialects survive only as `data_fill_shape`** (the mapper-input shape a helper targets, NOT a Layer 2 output and NOT a DB column). Conceptual four-set: flat **`flat_asset`** (asset tabs: DG / transformer / UPS) · keyed **`widgets_envelope`** (electrical / lt-pcc panel-overview) · **`column_row`** (single-meter `individual-feeder-meter-shell/*`) · **`shared_context`** (interdependent pages). **(OPEN, pending user — build-spec review fix #4: the live CONTRACTS `data_fill_shape` enum currently carries only the 3 — `flat_asset | widgets_envelope | shared_context`; the 4th `column_row` dialect is NOT yet in the contract enum and `data_fill_shape` has no `cmd_catalog` column / underived derivation. Treat the 4-set as conceptual until the enum + derivation land.)**
- **Hard exceptions are NOT V48's problem:** `DataTable` render-functions, `EventTimelineChart` accessor-functions, interactive callbacks, 3D `THREE.Object3D` — all minted **downstream in `Cards.tsx` JSX**, after the frame. V48 only emits the underlying data.

### Aggregation model (how the frame gets built)

- **Simple cards** (frame values = raw meter readings, e.g. DG Engine & Cooling `points[]`) → worker functions just **fetch + list**. Little work.
- **Aggregate cards** (frame values = derived, e.g. PCC Energy Distribution `loss_pct` / `share_pct` / `sankey` / `ai_summary`) → the DB has only raw rows, so the derived values must be **computed**.
- **User: for cards that need data-domain aggregation, the AI provides the payload to the WORKER FUNCTIONS, and the worker functions deal with the aggregation.** (AI provides/decides → deterministic worker functions do the aggregation labour.)
- **User decision: the aggregation math uses ONLY our current V48 pipeline plan** (V48's own worker functions) — **NOT** a reuse of backend2 `:8889`. (Backend2's strategies may still serve as a *reference* for the math, but V48 implements it self-contained.)

## Interdependent pages — Approach B (card atoms + `shared_context`)

> Full design + payload schemas + verification: `V48_INTERDEPENDENT_CARDS_DESIGN.md`.

- **Problem:** pages like Real-Time Monitoring have all cards interdependent (one shared buffer + one shared cursor/selection/metric), which today forces page-level payloads — but V48 needs card-level atoms.
- **Decision: Approach B.** The shared data lives **ONCE** in a `shared_context`; cards are **lean atoms** that point at it via `$ctx` (no data in the atom, no duplication). Page emits `{ shared_context, cards:[atoms] }`. (Yes — there is one extra shared payload per interdependent page; this is the price of not duplicating the buffer into every card.) **(OPEN, pending user: the exact `$ctx` source form — dotted `$ctx.history` vs bare ref + `buffer_key` — is not finalized.)**
- **How Layer 2 handles it:** Step 0 partition the page (from `cmd_catalog` couplings) into interdependent **groups** + **standalone** cards. For a group: (1) a **worker builds `shared_context` ONCE** (relocated L6.2 aggregation; AI specs, worker labours); (2) **per-card AI runs in parallel** emit lean atoms (couplings looked up from `cmd_catalog`, AI validates); (3) a **stitcher** bundles. Standalone cards skip step 1.
- **Refinement:** "Layer 2 parallel per card" → **parallel per card for atoms, with a one-time group-level shared-context pre-pass.**
- **Frontend (CMD V2):** new `joinSharedContext.ts` + `validateRtmWiring.ts`; the page hook's **source half** swapped to read `shared_context.history` (seeded state from `interaction.initial`); **derivation + handlers + components unchanged**.
- **VERIFIED behaves exactly as EMS frontend:** `shared_context.history` IS the exact `HistorySample[]` the hook already consumes (drop-in); downstream is source-agnostic; same seeds; components untouched. **Condition:** keep the socket as **live-merge owner** and treat `shared_context.history` as the **SEED** (not sole source) → live ticking/freeze/resume byte-identical.
- **VERIFIED across ALL 11 coupled/page-wise tabs (not just RTM): B generalizes — no hard failures.** The only thing that can't enter `shared_context` is a function (re-attached host-side). 6 design refinements make it tab-agnostic: (1) any host-owned scalar/enum is an `interaction` seed (not just cursor); (2) multi-buffer/multi-window context (some tabs have N windowed buffers, each own socket); (3) whole-tab-snapshot is the context (no per-card slicing when a card reads a sibling stat or a shared axis/threshold); (4) functions never travel in the payload (hard invariant); (5) carry the whole typed snapshot incl. `apiExtras`; (6) known gap: H&PQ flag-gated off → live untestable until flag flips. See `V48_INTERDEPENDENT_CARDS_DESIGN.md`.
- **Later:** can migrate to a generic assembler (Approach C) once ≥2 more coupled tabs are live — B and C share the same `shared_context`/worker tier, so it's a promotion, not a rewrite.
- **⚠ IN PROGRESS (user, 2026-06-29): the interdependency handling on the EMS frontend is STILL BEING BUILT.** The shared-state mechanism + how it coexists with one-payload-per-card is not finalized on the CMD V2 side. So Approach B's **frontend coupling is provisional** — RTM is the reference, but it can still move. Re-verify when the frontend morph/interdependency settles.

## Layout / placement

- User: **placement/layout info is in the DB — we'll use that.** (cmd_catalog `page_specs.grid_template_*` + `page_layout_cards.cell / region / slot_order`.)
- User: **Sizes are in the DB too** (`card_grid_size`).

## Interactivity

- User: **interactivity is RETAINED, as it is in EMS** (controls / cross-card selection / date-sync — kept like CMD V2 / EMS today).

## Failure handling

- User: **failures are LOGGED with the exact errors and details** — a card that can't be filled, an asset that won't resolve, a weak template, etc. **No reloop / re-route** (unlike V47's L4 reloop + L1 re-route); just capture exactly what failed and why.

## V47 stages → V48 disposition (per user)

| V47 stage | Disposition |
|---|---|
| asset-resolve | → **1b** |
| L3 column-resolve | **split**: card-agnostic part → **1b**; card-specific part → **Layer 2** |
| L4 payload swap / reloop | → **Layer 2** |
| L5 render-contract build | **RETIRED** — render-shaping stays in the FE mapper/viewModel |
| L6 SQL authoring | **render-shaping RETIRED; data-aggregation REUSED from CMD's EMS consumers directly** (per `card_handling.backend_strategy`) — not re-implemented in V48 |
| L6.2 panel-aggregate | **render-shaping RETIRED; data-aggregation REUSED from CMD's EMS consumers directly** — not re-implemented in V48 |
| narrate (AiSummary) | **PARKED** — decide later (note: `ai_summary` is part of the aggregate frame) |

- **Why (verified — see `CMDV2_PAYLOAD_VERIFICATION.md`):** the CMD V2 cards take a plain-JSON frame that Layer 2 provides directly, so the **render-contract (L5) + render-shaping (tones, axis domains, label synthesis, headroom)** genuinely leaves the pipeline — the FE mapper/viewModel keeps it.
- **~~But the *data-domain aggregation* L6 / L6.2 does NOT vanish — it RELOCATES into Layer 2's worker functions… NOT a reuse of backend2… V48 implements the math self-contained.~~** ⚠ **SUPERSEDED 2026-06-29** by *"Layer 2 DATA source — reuse CMD V2's EMS backend DIRECTLY"* above. The aggregation is **NOT** re-implemented self-contained in V48 — DATA is **sourced from CMD's own EMS consumer strategies directly** (addressed by `card_handling.backend_strategy`). L5 still retires (render-contract stays in the FE mapper); but L6/L6.2's data-aggregation is **reused from CMD, not relocated into new V48 worker math.**

## From the whiteboard sketch (brainstorm)

- **Layer-1 (1a + 1b):** Template (1a) · Asset + Columns (1b) → feed **Payload**, **each card's analytical story**, **Sizes**.
- **Layer-2:** **prompt-based analytical story + validation of payload** → **Card Analysis** + **Payload**.
- Recurring theme: **each card = a story wrt the prompt**.
- CMD primitives referenced: **Heat · Line · Bar · Radar**. Real counts (post-rebuild, 2026-06-29): **145 cards (135 live, max id 176)**, **10 payload shapes**. (The OLD "116 cards" count is STALE.)

> References: `CMDV2_PAYLOAD_VERIFICATION.md` (verified payload contract — what Layer 2 emits). Factual V47 background (not V48 mapping): `V47_PIPELINE_FLOW.md`, `V47_DB_REFERENCE.md`.

---

## Open Questions / Parking Lot

- **Test DB contents** — discuss at the END (parked).
- **narrate** — parked, decide later.
- ~~(a)/(b) data-fill split~~ — **RESOLVED:** per-card flexible — bindings-only for live data, baked-in where needed.
- **Keep the "analytical story" notions distinct (don't conflate):** (i) 1a's per-card story (role/function/prompt), (ii) the DB card-detail inputs → Layer 2 for swapping, (iii) the sketch's Layer-2 "prompt-based analytical story + validation of payload".
- ~~Unverified assumption (CMD V2 plain JSON)~~ — **VERIFIED:** holds at the backend-frame boundary; Layer 2 directly provides the plain-JSON frame. See `CMDV2_PAYLOAD_VERIFICATION.md`.
- **Three data quirks — PARKED for later (bundle with test-DB discussion):** BMS chiller frame (unvalidated shape); y-axis auto-scale needs a separate `/config/` call (not in the frame); a few percent-vs-fraction number quirks to reproduce.
- **Architecture research (inter-layer contracts + folder skeleton + per-layer prompts) — PARKED:** DBs are being modified; user will signal when to start.
- **`$ctx` source form — OPEN (pending user):** dotted `$ctx.history` vs bare ref + `buffer_key` (see Approach B above).
- **The 10 build-spec review fixes — OPEN (pending user):** e.g. the `emit_mode` leak (PROMPTS vs CONTRACTS), `column_row` dialect handling, `data_fill_shape` derivation, partition orphan card 160, the composite/sld `payload_shape` map, etc. — to be resolved before/at implementation.
- ~~Per-card output → per-tab frame assembly (gap #2)~~ — **RESOLVED via Approach B:** interdependent pages emit `{ shared_context, cards:[lean atoms] }`; a stitcher bundles per-card atoms + the one shared_context. Verified to drive the EMS frontend identically (seed model). See `V48_INTERDEPENDENT_CARDS_DESIGN.md`.
