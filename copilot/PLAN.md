# EMS Query Copilot — Full Implementation Plan

**Status:** PLAN (no code written yet) · **Date:** 2026-06-18
**Owner dir:** `backend/layer2/ems_copilot/` (a NEW sibling of `pipeline_v47/`, deliberately *outside* the pipeline)

---

## 0. What this is (and is not)

A **pre-submission prompt-authoring assistant**. As the user types an EMS query, it returns:

```json
{ "autofill": "...", "suggestions": ["...", "...", "...", "...", "..."] }
```

- `autofill` — inline ghost-text completion of the *current* text.
- `suggestions` — top-5 full natural-language EMS prompts in a dropdown.

It is **NOT** a chatbot, **NOT** dashboard generation, **NOT** post-submit intent clarification. It fires on every (debounced) keystroke and never runs the pipeline.

### Hard constraints (locked)
1. **Separate new layer, zero pipeline coupling.** Lives in its own directory, own HTTP server, own port, own systemd unit, own model endpoint. It does **not** import `pipeline.py`, `layer2_swap.py`, `column_resolve.py`, `l6.py`, `l6_2.py`, or anything in L1/L2/L3. A test asserts this.
2. **Reads the same data the pipeline reads — read-only, via its own helper.** It queries `cmd_catalog` and `lt_panels_db` for metadata; it does not mutate them and does not share code with the pipeline's `q()`/`db()` helpers (it copies a 6-line `psql` reader so there is no import edge).
3. **Model = `Qwen/Qwen3-4B-Instruct-2507-FP8`** on a *new* endpoint (`:8201`), never the pipeline's 35B (`:8200`).

---

## 1. Research & analysis (ground truth from the codebase)

### 1.1 The four databases (all PostgreSQL, localhost:5432, user `postgres`, accessed via `psql --csv -t` subprocess — no ORM anywhere)

| DB | Role | Used by copilot? |
|---|---|---|
| `cmd_catalog` | Rich EMS metadata: cards, pages, metrics, asset classes, topology | ✅ primary metadata |
| `lt_panels_db` | Registry/dictionary: `lt_mfm` (assets), `lt_parameter` (metrics), `lt_mfm_type` (classes) | ✅ primary asset+metric vocab |
| `lt_panels` | Raw per-meter time-series (250 tables, ~190 cols, ~1.1M rows each) | ⚠️ schema only (to flag which metric columns actually carry data); not a typeahead source |
| `premier_energies` | Legacy/parallel meter store (396 tables, `timestamp` not `ts`) | ❌ NOT referenced by any v47 code; excluded |

### 1.2 The five copilot vocabularies → exact sources

| Vocabulary | Source(s) | Size | Best fields to surface |
|---|---|---|---|
| **ASSETS** | `lt_panels_db.lt_mfm.name` (verbatim user-typed names) + `lt_mfm.load_group` + `lt_mfm_type.name` (class) | 220 assets, 6 classes, 11 load-groups | `name` (e.g. `Transformer 1`, `AHU-5`, `PCC Panel 1 A`, `UPS-01 CL:600KVA`, `Diesel Generator-01`) → `table_name` + `panel_id` + `mfm_type_id` |
| (asset enrichment) | `cmd_catalog.panel_topology.from_name/to_name` (deep load-side names, ratings inline) + `asset_3d_registry` (9 friendly classes) | 167+163 distinct names; 9 classes | load-side feeders, friendly class labels (Transformer/DG/Solar/UPS/BPDB/HHF/PCC) |
| **TEMPLATES / PAGES** | `cmd_catalog.page_specs` grouped by `cmd_catalog.pages.area` | 29 pages, 12 areas | `title`, `archetype` (Overview/Thermal/Power Quality/…), `analytical_theme`, `reusable_business_objective` (dense NL seeds) |
| **CARDS** | `cmd_catalog.cards` | 116 (each NL-unique) | `title`, `user_question` + `sem_answers` (pre-written NL questions = ideal suggestion seeds), `card_purpose`, `analytical_role` (12-value intent enum) |
| (card→metric bridge) | `cmd_catalog.card_data_recipe.fields` (jsonb) | 116 | per-card `{metric,label,unit,kind}` — which metrics each card can actually render |
| **METRICS** | `lt_panels_db.lt_parameter` (per-class dictionary) + `cmd_catalog.derived_metrics` + `card_controls.segmented_tabs` | 1086 param rows (≈300 distinct cols), 45 derived, friendly switch labels | `name` (friendly) + `column_name` (real) + `unit` + `kind` (measured/derived) + `mfm_type_id` (class scope) |
| **ALIASES** | ⚠️ **NO TABLE EXISTS** (the one real gap) | — | must be **built** (see §5) |

**Key joins (all FK-clean):**
- `lt_mfm.mfm_type_id → lt_mfm_type.id` and `→ lt_parameter.mfm_type_id` (a class's valid metrics).
- `lt_mfm.table_name`/`panel_id` → the `lt_panels.<table>` time-series (and `panel_id` is the WHERE key when two meters share a table, e.g. PCC 1A id 174 / 1B id 185 both → `mfm_lt_115`).
- `cmd_catalog.cards.page → pages.area`; `card_data_recipe.fields[].metric` matches either `derived_metrics.metric_key` or a raw `lt_parameter.column_name`.

**Notable facts that shape the design:**
- `lt_mfm` has 5 NO-DATA meters (empty `table_name`) → exclude from asset suggestions.
- `lt_parameter` is partitioned by class (180 LT / 241 TF / 134 HT / 226 UPS / 146 APFC / 159 DG) with heavy overlap → dedup to distinct `(column_name,label,unit)` and tag with the class set; filter by the in-context asset's class when one is present.
- Asset names carry embedded specs (`UPS-01 CL:600KVA`, `HHF-01 (TYPE-01) 300A +600KVAR`) → store a cleaned **display** form alongside the verbatim **canonical** form.
- DG assets exist in `lt_mfm` (`Diesel Generator-01`, `mfm_dg_*`) even though they're absent from `panel_topology.from_name` — so `lt_mfm` (not topology) is the authoritative asset list.

### 1.3 Model serving

- **Active:** `Qwen3.6-35B-A3B-FP8` @ `:8200`, user-systemd `~/.config/systemd/user/vllm.service`, util 0.60, holds 63.6 GB. **Do not touch / do not share.**
- **GPU headroom:** RTX PRO 6000, 97.9 GB total, ~78.5 GB used → **~19 GB free.** A 4B FP8 model (~4-5 GB weights + small KV cache at len 8192) fits at util ≈ 0.10-0.12.
- **Template to clone:** the disabled `/etc/systemd/system/vllm-ai.service` (already a `:8201` unit) → new `vllm-copilot.service`.
- **Caveat:** `Qwen3-4B-Instruct-2507-FP8` is **not in the HF cache yet** — first launch downloads it. vLLM binary is `…/3.11.9/bin/vllm` (v0.16.1rc1). Verify the exact HF repo id + FP8 compatibility before wiring the unit.
- **LLM call shape (reference, not import):** `pipeline_v46/backend/layer1/ai_router.py` → httpx `POST {url}/v1/chat/completions`, `chat_template_kwargs:{enable_thinking:false}`, low temp. The copilot copies this shape pointed at `:8201` with its **own** env (`COPILOT_LLM_URL`, `COPILOT_LLM_MODEL`).

### 1.4 API-server boundary

- No FastAPI/Flask anywhere. Real servers: `reslice_server.py` (stdlib `:8771`), Django `command_center :8000` / legacy EMS `:8899` / `backend2 :8889`, Vite host `:3147`.
- `command_center`, the legacy EMS backend, `backend2` are all pipeline/EMS-coupled → **disqualified** by the no-coupling rule.
- **Decision (given "separate layer"):** stand up a **dedicated standalone stdlib server** `ems_copilot/server.py` on **`:8772`** (modeled on `reslice_server.py`'s `ThreadingHTTPServer` + CORS pattern), with its own `ems-copilot.service` unit. This is cleaner than folding into `:8771` and fully decouples copilot uptime from the pipeline.

### 1.5 Frontend prompt surfaces

- **Primary target — v47 host `PromptBar`** in `host/src/V47Grid.tsx` (lines 99-119): controlled `<input>` via local `useState`, submit on Enter or Generate button, POSTs `/run` to `:8771`. Vite (`:3147`), Tailwind v4, warm-paper palette (teal `#2f6f6f`, border `#e2ddd0`, bg `#faf8f3`). The hand-built **AssetPicker** overlay in the same file (lines 123-158) is the template to mirror for a suggestions dropdown.
- **Secondary — BFI Next.js modals** `PaperTextInput.tsx` / `TextInputOverlay.tsx` → `useVoicePipeline.sendTextDirect()`. Tailwind v3, different backend (Layer2 RAG).
- **No autocomplete/combobox library** is installed in any frontend → the ghost-text + dropdown are hand-built (consistent with the codebase).

---

## 2. Architecture

```
                       ┌─────────────────────────────────────────────────────────┐
   keystroke (debounced)│              ems_copilot/  (NEW separate layer)          │
  ┌──────────────┐ POST │                                                          │
  │ Frontend     │/copilot/suggest                                                 │
  │ GhostTextInput├────────▶ server.py  (stdlib HTTP, :8772, CORS)                 │
  │ + Dropdown   │◀────────  │   {autofill, suggestions}                           │
  └──────────────┘         │  │                                                    │
   (V47 PromptBar /        │  ▼                                                    │
    BFI modal)             │ retrieve.py ──► copilot_index.sqlite (FTS5)           │
                           │   (lexical+fuzzy+alias, <10ms)   ▲                    │
                           │  │                                │ built offline by   │
                           │  ▼                                │ build_index.py     │
                           │ generate.py ──► Qwen3-4B @ :8201 (vllm-copilot.service)│
                           │   (RAG prompt, JSON out, ~80-200ms)                    │
                           └──────────────────────────────────┬────────────────────┘
                                                              │ read-only psql
                       ┌──────────────────────────────────────▼───────────────────┐
                       │ cmd_catalog  ·  lt_panels_db  ·  lt_panels (schema only)   │
                       └────────────────────────────────────────────────────────────┘
```

**Two-tier latency model (the core design idea):**
- **Tier 0 — instant (<10 ms), no LLM:** `retrieve.py` does lexical+fuzzy+alias match against the prebuilt SQLite FTS5 index and synthesizes baseline suggestions from templates. Rendered immediately so the dropdown never feels laggy.
- **Tier 1 — model (~80-200 ms):** `generate.py` sends the partial text + the Tier-0 retrieved entities to Qwen3-4B, which produces a natural inline `autofill` and rephrased/diversified `suggestions`. Streamed in to replace Tier-0 once ready.
- If the model is cold/slow/down → Tier 0 alone is the answer (graceful degradation; the feature still works).

**Retrieve-then-generate (grounded RAG):** the model only ever sees real EMS entities, so suggestions cannot hallucinate assets/metrics that don't exist.

---

## 3. Component breakdown (files in `ems_copilot/`)

| File | Responsibility |
|---|---|
| `db.py` | 6-line `psql --csv -t` reader (copied, not imported) for `cmd_catalog` / `lt_panels_db`. Read-only. |
| `build_index.py` | Offline/periodic. Flattens the 5 vocabularies → `copilot_index.sqlite`. Generates aliases (curated + LLM). Idempotent. |
| `copilot_index.sqlite` | The suggestion corpus + FTS5 index + alias table + template patterns (see §4). Self-contained, committed-or-rebuilt. |
| `retrieve.py` | Per-keystroke Tier-0: tokenize → prefix/substring/fuzzy/alias match → ranked top-N entities per type + deterministic template suggestions. No LLM, no network. |
| `generate.py` | Tier-1: build compact prompt → call Qwen3-4B (`:8201`) → parse+validate JSON → enforce prefix-consistency, entity-grounding, dedupe, top-5. |
| `server.py` | Stdlib `ThreadingHTTPServer` on `:8772`. Routes: `POST /copilot/suggest`, `GET /copilot/health`, `POST /copilot/reindex`. CORS. Warmup ping on boot. Per-prefix LRU cache. |
| `prompts.py` | The system/user prompt templates + JSON schema for the model. |
| `config.py` | Env: `COPILOT_LLM_URL` (default `http://localhost:8201/v1`), `COPILOT_LLM_MODEL`, `COPILOT_PORT=8772`, debounce/cap knobs. |
| `tests/` | Golden-prompt eval (the two spec examples + more), latency test, degradation test, **no-coupling import assertion**. |
| `deploy/vllm-copilot.service` | systemd unit for the 4B model on `:8201`. |
| `deploy/ems-copilot.service` | systemd unit for `server.py` on `:8772`. |
| `frontend/useCopilot.ts` + `GhostText.tsx` + `SuggestionDropdown.tsx` | Portable React widget (drops into V47 PromptBar and the BFI modals). |

---

## 4. Database schema (copilot-owned index — SQLite FTS5, self-contained)

The copilot does **not** alter `cmd_catalog`/`lt_panels_db`. It builds its own `copilot_index.sqlite`:

```sql
-- one row per suggestable EMS entity
CREATE TABLE entities (
  id          INTEGER PRIMARY KEY,
  type        TEXT NOT NULL,          -- 'asset' | 'metric' | 'card' | 'page' | 'derived_metric'
  canonical   TEXT NOT NULL,          -- resolution form (e.g. 'UPS-01 CL:600KVA', 'active_power_total_kw')
  display     TEXT NOT NULL,          -- cleaned label (e.g. 'UPS-01', 'Active Power')
  unit        TEXT,                   -- A, V, kW, kWh, % ... (metrics)
  class_scope TEXT,                   -- 'LT Panel,Transformer,...' (metrics) | asset class | NULL
  area        TEXT,                   -- page area / load_group
  table_name  TEXT,                   -- lt_panels table (assets)
  panel_id    TEXT,                   -- WHERE key (assets)
  kind        TEXT,                   -- measured|derived (metrics); analytical_role (cards)
  has_data    INTEGER DEFAULT 1,      -- 0 for NO-DATA meters / derived w/o base
  popularity  REAL DEFAULT 0,         -- learned from query_log (cold-start = type prior)
  payload     TEXT                    -- JSON: card→metrics, page→archetype/theme, etc.
);

CREATE TABLE aliases (                 -- FILLS THE ALIAS GAP
  entity_id   INTEGER REFERENCES entities(id),
  alias       TEXT NOT NULL,           -- 'amps', 'pf', 'temp', 'the main transformer'
  source      TEXT                     -- 'curated' | 'llm' | 'embedded'
);

CREATE VIRTUAL TABLE entities_fts USING fts5(   -- trigram for prefix+fuzzy
  display, canonical, alias_blob, keyword_blob,
  content='', tokenize='trigram'
);

CREATE TABLE templates (               -- deterministic Tier-0 suggestion patterns
  id INTEGER PRIMARY KEY,
  intent  TEXT,                        -- 'show' | 'compare' | 'trend' | 'list'
  pattern TEXT,                        -- 'compare {metric} between {asset} and {asset}'
  slots   TEXT                         -- JSON slot spec
);

CREATE TABLE query_log (               -- local popularity learning (optional, privacy-local)
  ts TEXT, prefix TEXT, accepted TEXT
);
```

Build counts to assert: ~215 assets (data-bearing) · ~300 distinct metrics + 45 derived · 116 cards · 29 pages.

---

## 5. Retrieval strategy

**Corpus is tiny** (a few thousand short strings) → everything fits in memory/SQLite; we retrieve to keep the model prompt tight and grounded, not for scale.

**Per keystroke (`retrieve.py`):**
1. **Parse** the text: last partial token + full-string context; cheap regex detects the leading **intent verb** (`show|compare|trend|list|monitor|analyze`).
2. **Match** the partial token against `entities_fts` (trigram → prefix > substring > fuzzy) and `aliases`. Rank by `match_quality × type_prior × popularity`.
3. **Context-filter:** if an asset (or its class) already appears in the text, restrict metric candidates to that class's `lt_parameter` set; if a page area is implied, bias cards to that area.
4. **Return** top-N per type (≈8 assets, 8 metrics, 6 cards, 4 pages) + a few **template-filled deterministic suggestions** (Tier-0 baseline).

**Deep semantic mining (the strongest lever — EMS cards/templates already encode meaning):**
Beyond title/role, the builder mines the full semantic surface and turns it into ranked, grounded suggestion material:
- **Exemplar questions (317):** `cards.user_question` + `cards.sem_answers` + `page_specs.reusable_answers` are pre-written NL questions the EMS already answers → indexed as first-class `question` entities and matched by topic. These are the highest-quality suggestion seeds.
- **Metric salience:** metrics are ranked by **how many cards render them** (`card_data_recipe.fields`) — `Load % of Rated` (32 cards), `Active Power Total` (23), `Current Average`/`Power Factor`/`Current Unbalance` (15) float above the long tail of 424 raw columns. So suggestions favour metrics that are actually meaningful in this plant.
- **Card→metric truth:** each card carries its real metric set + `output_insight` + `decision_support`, fed to the model as grounding context.
- **Real time presets (13):** `Today / Yesterday / Last 7 days / This Week / This month / …` lifted from `card_controls.time_options` — the `{time}` slot uses real options, never invented windows.
- **Rich match keywords:** `card_purpose`, `visualization`, `output_insight`, `decision_support`, `sem_purpose`, page `analytical_theme`/`narrative_flow`/`reusable_concepts` all feed the searchable keyword blob so topical matches surface the right card/page/question.

**Alias layer (the gap-filler, built in `build_index.py`):**
- **Curated seed** (hand-written, high-value): `trans→transformer`, `amps/amperage→current`, `power→active_power_total_kw`, `pf→power_factor_total`, `temp→temperature`, `volts→voltage`, `unbalance→iUnbalance`, `pcc→PCC Panel`, `dg→Diesel Generator`, `ahu→Air Handling Unit`, etc.
- **LLM-generated** (batch, build-time, using the 4B model): for each asset/metric/card, ask for 3-5 colloquial synonyms; store as `source='llm'`. This is one-time/offline, so latency is irrelevant.
- **Embedded** (free): split ratings/specs out of names (`UPS-01 CL:600KVA` → alias `UPS-01`, `600KVA`).

---

## 6. Inference flow (`generate.py` → Qwen3-4B @ :8201)

**Prompt (compact):**
- *System:* "You are an EMS query autocomplete. Given the user's partial query and a list of VALID EMS entities (assets, metrics, cards, pages), output strict JSON `{autofill, suggestions}`. `autofill` continues the user's EXACT text inline. `suggestions` = 5 complete EMS queries. Use ONLY entities from the list. No prose."
- *User:* the current text + the Tier-0 retrieved entities, rendered compactly (e.g. `ASSETS: Transformer 1, Transformer 2, …  METRICS: current (A), active power (kW), …  CARDS: …`).

**Params:** `temperature 0.3`, `max_tokens ≤ 220`, `enable_thinking:false`, vLLM **guided JSON** (`response_format:{type:"json_object"}` / `guided_json`), stop on `}`.

**Post-processing (deterministic guardrails):**
- `autofill` must start with the user's exact text; else drop to suffix-only or fall back.
- Every suggestion must reference at least one real retrieved entity; drop hallucinations.
- Dedupe, cap to 5, prefer diversity across intents (show/compare/trend).
- If model errors/timeouts (>250 ms budget) → return Tier-0 deterministic suggestions with `source:"fallback"`.

**Worked examples (validate against these):**
- `"show trans"` → retrieve assets {Transformer 1, Transformer 2, …}, metrics {current, loading, thermal}; model → `autofill:"former 1 current history"`, suggestions = the 5 in the spec.
- `"compare current"` → retrieve metric `current` + assets {Transformer 1/2, feeders}; model → `compare current usage between transformer 1 and 2`, `compare current trends across feeders`, `compare current imbalance across transformers`.

---

## 7. API design

**`POST /copilot/suggest`**
```jsonc
// request
{ "text": "show trans", "cursor": 10, "limit": 5,
  "context": { "asset": null, "recent": [] } }   // context optional
// response
{ "autofill": "show transformer 1 current history",   // full completed string
  "ghost": "former 1 current history",                // suffix to render after the typed text
  "suggestions": ["show transformer 1 current history", "...", "...", "...", "..."],
  "entities": [ {"type":"asset","display":"Transformer 1"} ],   // optional, for highlighting
  "source": "model",                                  // "model" | "fallback"
  "latency_ms": 87 }
```
**`GET /copilot/health`** → `{ ok, model_up, index_rows, warm }`
**`POST /copilot/reindex`** (admin) → rebuilds `copilot_index.sqlite`.

CORS `*` (matches `reslice_server.py`). Request cancellation handled client-side via `AbortController`; server stays stateless + cache-friendly (LRU keyed by normalized prefix).

---

## 8. Frontend integration approach

**Portable widget** (`ems_copilot/frontend/`), framework-agnostic enough to drop into both surfaces:
- `useCopilot(text, {debounceMs:120})` — debounces, aborts in-flight, caches by prefix, returns `{autofill, ghost, suggestions, loading}`.
- `GhostText` — relative-positioned wrapper: the real `<input>` on top, a muted `<span>`/shadow input rendering `typed + ghost` behind it.
- `SuggestionDropdown` — absolutely-positioned list mirroring the existing **AssetPicker** overlay styling.

**v47 PromptBar wiring (`host/src/V47Grid.tsx`, the primary target):**
1. Wrap the existing `<input>` (line 105) in a `relative` container; mount `GhostText` + `SuggestionDropdown`.
2. On `onChange` (line 109) call `useCopilot`. **Do not touch the submit path** — keep Enter→`run()` (line 110) and the Generate button.
3. Add key handlers **before** the existing Enter branch: `Tab` = accept ghost, `ArrowDown/Up` = navigate dropdown, `Enter` on a highlighted suggestion = fill (not submit), `Esc` = dismiss.
4. Add one proxy line to `host/vite.config.ts`: `'/copilot': 'http://localhost:8772'`.

**BFI Next.js (secondary, same widget):** drop `GhostText`+`SuggestionDropdown` into `PaperTextInput.tsx` / `TextInputOverlay.tsx`; submit sink (`sendTextDirect`) unchanged; point fetch at the copilot host.

---

## 9. Implementation phases

| Phase | Deliverable | Verify |
|---|---|---|
| **P0 — Model** | `vllm-copilot.service` (clone of `vllm-ai.service`) running Qwen3-4B-Instruct-2507-FP8 on `:8201`, util ~0.10. | Confirm HF repo id; download; `GET /v1/models`; smoke `chat/completions`; 35B at :8200 unaffected. |
| **P1 — Index** | `db.py` + `build_index.py` → `copilot_index.sqlite` (entities + FTS5). | Row counts (≈215 assets / 300 metrics / 116 cards / 29 pages); spot-check `Transformer 1`, `AHU-5`, `current_r`. |
| **P2 — Aliases** | curated seed + LLM-batch alias generation into `aliases`. | `trans→transformer`, `amps→current`, `pcc→PCC Panel` resolve. |
| **P3 — Retrieve** | `retrieve.py` (lexical+fuzzy+alias+templates). | unit tests on `"show trans"`, `"compare current"`; <10 ms. |
| **P4 — Generate** | `prompts.py` + `generate.py` (4B call, guided JSON, guardrails, fallback). | the two spec examples produce the expected suggestions; prefix-consistency holds. |
| **P5 — Service** | `server.py` (:8772) + `ems-copilot.service` + cache + warmup. | end-to-end latency p50 < 150 ms; `/health`; kill 4B → Tier-0 still answers. |
| **P6 — Frontend** | `useCopilot` + `GhostText` + `SuggestionDropdown`; PromptBar wiring; vite proxy. | ghost text + dropdown render; Tab/Arrows work; submit path untouched. |
| **P7 — QA** | golden-prompt eval set; latency + degradation tests; **no-coupling import assertion**. | `grep`/AST: `ems_copilot` imports nothing from `pipeline_v47` L1/L2/L3; all gates green. |

---

## 10. Risks & mitigations

- **4B cold-start / GPU contention** → keep the unit warm (Restart=always), util pinned low (~0.10-0.12, ≈10-12 GB < ~19 GB free), `max_tokens` ≤ 220, warmup ping on boot. Tier-0 covers any stall.
- **Model not cached** → first launch downloads; verify repo id + FP8 build compat (vLLM 0.16.1rc1) before P5.
- **Metric explosion / wrong-class metrics** → dedup `lt_parameter` + class-scope filter; suggest class-appropriate metrics when an asset is in context.
- **Alias gap** → built explicitly in P2 (curated + LLM + embedded).
- **Two prompt surfaces** → portable widget; ship v47 first, BFI modal as a drop-in.
- **Drift** (cmd_catalog changes) → `POST /copilot/reindex` + a scheduled rebuild; index is cheap to regenerate.

---

## 11. Open decisions (need a call before/at build)

1. **Frontend surface:** v47 host PromptBar (recommended primary) / BFI Next.js modal / both.
2. **Alias layer scope for v1:** curated + LLM-generated (recommended) / curated-only / skip.
3. **Index store:** SQLite FTS5 self-contained (recommended) / in-memory rebuilt on boot / a new `copilot` Postgres schema.
4. **Provision the 4B model now** (download + systemd unit) or design-only until the rest is built.
