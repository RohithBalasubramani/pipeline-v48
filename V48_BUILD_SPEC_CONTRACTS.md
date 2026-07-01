> Part of the V48 build-spec, generated 2026-06-23. Re-grounded against the CMD V2 payload-morph (commit dfded69, CLAUDE.md §B4 "one payload per card") on 2026-06-29. See V48_BUILD_SPEC.md for the index and V48_PAYLOAD_MORPH_CORRECTION.md for the morph rationale.

## Inter-layer contracts

These are the authoritative JSON contracts for the V48 pipeline (3 pure-AI layers: 1a, 1b, 2). Every field name is consistent across schemas and grounded in the live `cmd_catalog`, `lt_panels_db`, and `lt_panels` DBs. Filter `cmd_catalog` to `status='live'` everywhere.

**The corrected model (read this first — it changes what "Layer 2 output" structurally is):**

A card is a pure function of **ONE flat payload object** carrying BOTH live DATA and chrome METADATA, **every key EXACTLY once**, no second `root` object, zero design-system chrome, byte-identical defaults (CLAUDE.md §B4:201-218). Two ownerships split that one payload:

- **Layer 2 (AI) = the metadata producer.** Per card it emits `{ card_id, $ctx?, render_slot, exact_metadata, data_instructions }`. `exact_metadata` is the **FINISHED METADATA tier** of the card's one payload (labels · units · colours · rosters · order · thresholds · contracts · badges · tabs), authored with **byte-identical defaults** and morphed per prompt. `data_instructions` is a **parseable recipe** (the per-field `{kind,role,metric,column,unit,agg,source,window}` list + `orientation`/`entity_dim`) that the hook/helper functions PARSE to FILL the DATA tier. Layer 2 NEVER fills DATA and NEVER emits design-system chrome.
- **Worker/helper = the DATA fill.** It parses `data_instructions` and populates the DATA keys (`history` / `periods` / numbers + initial interaction state) from EITHER the live `ws/mfm/{id}/{screen}/` socket frame (production) OR a test-DB fixture in the **identical Snapshot shape** (offline/CI) — interchangeable at the mapper boundary. It keeps owning live state, interactivity, and interdependency. The helper writes into the named DATA keys; it never touches `exact_metadata`.
- **The stitcher** merges `{...exact_metadata, ...filled_data}` into ONE flat payload per card — every key once, no `root`.

The old per-tab dialect union (canon set: `flat_asset | widgets_envelope | column_row | shared_context`) is **demoted**: it is no longer what Layer 2 emits per card. It survives ONLY as the **DATA-FILL frame schema** — the mapper-input target shape the worker fills (see §6). The METADATA dialect dissolves into per-card `exact_metadata` payloads (`HeatmapViewModel`/`RailViewModel`/the 5 HPQ `HpqPresentation` blocks).

Cross-cutting conventions (apply to all contracts):
- `card_id` is an **integer** (the `cmd_catalog.cards.id` PK). It is NOT a slug.
- `page_key` is a **slug** (`page_specs.page_key`, e.g. `panel-overview-shell/real-time-monitoring`).
- `handling_class` vocab is the rebuilt set: `single_asset_series | single_asset_derived | panel_aggregate | asset_3d | narrative_ai | topology_sld | nav_index`.
- `payload_shape` normalizes to one of the 10 `payload_shapes` names: `TilePayload | SeriesPayload | RadarPayload | SankeyPayload | HeatmapPayload | TablePayload | TextPayload | ProgressPayload | PqDiagnosisPayload | PqEventStatsPayload`. **OPEN (V48_BUILD_SPEC_REVIEW.md G10, pending user):** live `card_data_recipe.payload_shape` also carries `composite` (the Approach-B combo case — must NOT collapse to a single shape) and `sld` (topology) values that have no entry in these 10 and are not yet mapped.
- `$id` / `$ctx` are the shared_context binding tokens (an atom's `$ctx` MUST equal some `shared_context.$id` on the same page).
- `data_fill_shape` (the renamed former `frame_dialect`) is the DATA-FILL/mapper-input frame the worker targets: `flat_asset | widgets_envelope | shared_context`. It describes the **DATA source shape only** — it does NOT describe what the AI emits per card, and it is NOT the morphable METADATA. **OPEN (per `V48_BUILD_SPEC_REVIEW.md` G4/G5, pending user):** this enum is missing the 4th `column_row` (column/queue) dialect the `individual-feeder-meter-shell/*` V&C cards emit (FOLDER lists `frames/column_row.py`), and `data_fill_shape` has **no `cmd_catalog` column** — its derivation from `render_shell`/`backend_strategy`/`handling_class` is not yet specified. Treat the 3-value enum below as provisional until those fixes land.

---

### §B4 invariants — the build rules every emit must satisfy

These are not advisory; they are the acceptance contract and are repeated wherever an emit is defined.

1. **ONE payload per card.** A card is a pure function of one flat object. After the helper fills DATA, `{...exact_metadata, ...filled_data}` is ONE namespace.
2. **Every key EXACTLY once.** No duplicate `title`/`sections`/`contractKw`. A second `root` object was the exact bug that bred duplicates — it is forbidden, and the dead duplicates (`sections`, per-section `contractKw`) are gone and locked by `@ts-expect-error` in `morphPayloadTypes.test.ts`.
3. **No `root`.** `{data:{...}, metadata:{...}}` is the right *mental* split, but the emit FLATTENS both into one namespace.
4. **Byte-identical default.** Every `exact_metadata` field's default = today's rendered bytes; only a prompt-driven mutation moves a render. Defaults are copied from the card's static config/token registries (`HEATMAP_CARD_TITLE`, `METRIC_DEFS`, `STATUS_COLORS`, `SECTION_HEADER_CHROME`, `RT_DIR_PRESETS`, `FOCUS_META`, `DEFAULT_HPQ_LIMITS`, …) — those constants REMAIN as the default source, just not read in JSX.
5. **Producer always populates.** Every `exact_metadata` field is REQUIRED and always filled by Layer 2 (`data.X ?? CONST` is morphable only if the producer always fills X).
6. **New renderers opt-in default-OFF** (e.g. `showLegend:false`) — a default-ON addition that changes the resting render is rejected.
7. **Zero design-system chrome on the payload.** Pixel geometry, fonts, Card/SegmentedControl markup, grid → tokens/primitives, NEVER on the payload. Functions / ReactNode / 3D handles are re-attached host-side, never on the payload.
8. **LIVE acceptance gate.** Verification is the LIVE Storybook sentinel: mutate ONE `exact_metadata` field at :6008 and read the card DOM. Green RTL tests + byte-identical defaults HID 3 real RTM gaps — golden-payload comparison alone is insufficient.

---

### 1. Pipeline input  *(UNCHANGED — carried forward verbatim)*

The harness fires on a frontend prompt. `PIPELINE_ASSET_ID` is the asset-picker round-trip override (set on the re-run after the user picks from `candidate_list`); when present, 1b SKIPS resolution and pins it (`how="user-choice"`, mirrors V47).

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "v48/pipeline_input",
  "title": "PipelineInput",
  "type": "object",
  "required": ["prompt", "run_id"],
  "additionalProperties": false,
  "properties": {
    "prompt": { "type": "string", "minLength": 1, "description": "Verbatim frontend prompt text." },
    "run_id": { "type": "string", "description": "Unique id for this run; logs land in logs/ai_<run_id>.jsonl." },
    "env": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "PIPELINE_ASSET_ID": {
          "type": ["integer", "null"],
          "description": "lt_mfm.id pinned by the AssetPicker round-trip. When set, 1b skips asset resolution and emits asset.how='user-choice'. null/absent = first pass."
        },
        "DB_TARGET": {
          "type": "string",
          "enum": ["live", "test"],
          "default": "live",
          "description": "Which data DB the Layer-2 worker queries to FILL the DATA tier: live=lt_panels/lt_panels_db, test=the test DB fixture (identical Snapshot shape, interchangeable at the mapper boundary)."
        },
        "CMD_CATALOG_DB": { "type": "string", "default": "cmd_catalog" },
        "LLM_URL": { "type": "string", "default": "http://localhost:8200/v1/chat/completions" },
        "MODEL": { "type": "string", "default": "Qwen/Qwen3.6-35B-A3B-FP8" }
      }
    }
  }
}
```

---

### 2. 1a output — storytelling router (Template + per-card story)  *(UNCHANGED — carried forward verbatim)*

1a picks the page that TELLS THE STORY BEST (not asset/metric match), emits a per-card analytical story, carries the DB layout/size refs through verbatim, and hands the deterministic Step-0 interdependency partition to Layer 2. `page_key` is copied verbatim from `page_specs`. The morph does NOT touch 1a — it emits page/metric/intent + story, never a card payload.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "v48/layer1a_output",
  "title": "Layer1aOutput",
  "type": "object",
  "required": ["page_key", "metric", "intent", "story", "cards", "interdependency_groups"],
  "additionalProperties": false,
  "properties": {
    "page_key": { "type": "string", "description": "page_specs.page_key, verbatim. status='live'." },
    "page_title": { "type": "string", "description": "page_specs.title." },
    "shell": { "type": "string", "description": "page_specs.shell (asset class)." },
    "module": { "type": "string", "description": "page_specs.module." },
    "metric": { "type": "string", "description": "Dominant measured quantity, e.g. current|voltage|power|energy|thd|pf|frequency|temperature. Default 'power'." },
    "intent": { "type": "string", "enum": ["trend", "distribution", "snapshot", "table", "events"], "default": "trend" },
    "story": { "type": "string", "description": "Page-level analytical narrative this page should tell for THIS prompt; seeded from page_specs.analytical_theme + reusable_answers." },
    "layout": {
      "type": "object",
      "description": "Verbatim from page_specs — placement is from the DB, positions never move.",
      "additionalProperties": false,
      "properties": {
        "layout_primitive": { "type": "string" },
        "grid_template_columns": { "type": "string" },
        "grid_template_rows": { "type": "string" },
        "layout_gap": { "type": ["string", "null"] },
        "layout_padding": { "type": ["string", "null"] },
        "layout_shape": { "type": ["string", "null"] },
        "render_shell": { "type": ["string", "null"] }
      }
    },
    "cards": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["card_id", "title", "analytical_story"],
        "additionalProperties": false,
        "properties": {
          "card_id": { "type": "integer", "description": "cmd_catalog.cards.id (PK)." },
          "title": { "type": "string", "description": "cards.title (real card title)." },
          "analytical_story": {
            "type": "string",
            "description": "Prompt-specific analytical angle for THIS card wrt its role/function. Distinct from static DB card details. Constrains Layer-2 swaps."
          },
          "role_in_story": { "type": "string", "description": "How this card serves the page story (from cards.analytical_role / page_specs.card_roles)." },
          "slot": {
            "type": "object",
            "description": "Verbatim from page_layout_cards (the slot map). Slot = EMS cell; never moves.",
            "additionalProperties": false,
            "properties": {
              "slot_order": { "type": "integer" },
              "cell": { "type": ["string", "null"] },
              "region": { "type": ["string", "null"] },
              "area": { "type": ["string", "null"] },
              "col_span": { "type": ["integer", "null"] },
              "row_span": { "type": ["integer", "null"] },
              "tab": { "type": ["string", "null"] },
              "combo_id": { "type": ["integer", "null"], "description": "card_combo.id if this card rolls up into a combo." },
              "combo_role": { "type": ["string", "null"] }
            }
          },
          "size": {
            "type": "object",
            "description": "From card_grid_size (only 116/145 cards have a row; missing → defaulted+logged).",
            "additionalProperties": false,
            "properties": {
              "viewport": { "type": "string", "default": "1920x1080" },
              "width_px": { "type": ["integer", "null"] },
              "height_px": { "type": ["integer", "null"] },
              "size_source": { "type": "string", "enum": ["card_grid_size", "defaulted"], "default": "card_grid_size" }
            }
          }
        }
      }
    },
    "interdependency_groups": {
      "type": "array",
      "description": "Deterministic Step-0 partition handed to Layer 2: transitively-connected cards (card_link / cards.interdependency prose / card_combo / selection_dimension). Cards absent from every group are standalone. UNCHANGED by the morph — the morph only refines what each group/standalone card OUTPUTS (per-card exact_metadata), not the partition.",
      "items": {
        "type": "object",
        "required": ["group_id", "card_ids"],
        "additionalProperties": false,
        "properties": {
          "group_id": { "type": "string", "description": "e.g. 'rtm-combo'. Becomes interdependency_group on the page frame and the $id stem of its shared_context." },
          "card_ids": { "type": "array", "items": { "type": "integer" }, "minItems": 1 },
          "combo_id": { "type": ["integer", "null"], "description": "card_combo.id when the group is a render-as-one composite." },
          "coupling": {
            "type": "array",
            "description": "Looked up from cmd_catalog, NOT AI-invented. One entry per edge. Union of prose cards.interdependency + card_link (the documented gotcha: card_link ALONE orphans the lone time-bucket card, so prose links must be unioned).",
            "items": {
              "type": "object",
              "required": ["src_card", "dst_card", "dimension"],
              "additionalProperties": false,
              "properties": {
                "src_card": { "type": "integer" },
                "dst_card": { "type": "integer" },
                "dimension": { "type": "string", "description": "selection_dimension.dimension, e.g. time-bucket|metric|feeder|section|event-type." },
                "link_type": { "type": "string", "description": "card_link.link_type: shared-selection|drill-down|cross-highlight|master-selector|control-selector|visual-highlight." },
                "src_effect": { "type": ["string", "null"] },
                "dst_effect": { "type": ["string", "null"] },
                "trigger": { "type": ["string", "null"] },
                "scope": { "type": ["string", "null"] },
                "bidirectional": { "type": "boolean", "default": false },
                "wired": { "type": "boolean" }
              }
            }
          }
        }
      }
    }
  }
}
```

---

### 3. 1b output — asset resolve + card-agnostic column basket  *(UNCHANGED — carried forward verbatim)*

1b runs in parallel with 1a; it is prompt-driven and card-agnostic. Either `asset.how='AI'|'user-choice'` (confident pin) or `candidate_list` is non-empty (ambiguous → AssetPicker round-trip, like V47 `asset_choice.json`). The `column_basket` is the GENEROUS `feasible`+`probable` set — ALL plausibly-relevant tables/columns, NOT template-scoped. The morph does NOT touch 1b — under the morph the column basket becomes the INPUT to Layer 2's `data_instructions`, but 1b's own output shape is untouched.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "v48/layer1b_output",
  "title": "Layer1bOutput",
  "type": "object",
  "required": ["asset", "candidate_list", "column_basket"],
  "additionalProperties": false,
  "properties": {
    "asset": {
      "type": ["object", "null"],
      "description": "The pinned asset when confident (or user-choice). null when ambiguous (see candidate_list).",
      "additionalProperties": false,
      "properties": {
        "mfm_id": { "type": "integer", "description": "lt_mfm.id." },
        "name": { "type": "string", "description": "lt_mfm.name." },
        "table": { "type": "string", "description": "lt_mfm.table_name — join key into lt_panels time-series. Empty=NO-DATA." },
        "panel_id": { "type": ["string", "null"], "description": "lt_mfm.panel_id — the time-series WHERE key." },
        "mfm_type_id": { "type": "integer", "description": "lt_mfm.mfm_type_id." },
        "class": { "type": "string", "enum": ["LT Panel", "Transformer", "HT Panel", "UPS", "APFC", "Diesel Generator"], "description": "lt_mfm_type.name." },
        "load_group": { "type": ["string", "null"] },
        "how": { "type": "string", "enum": ["AI", "user-choice"], "description": "AI=confident resolve; user-choice=pinned via PIPELINE_ASSET_ID." }
      },
      "required": ["mfm_id", "name", "table", "mfm_type_id", "class", "how"]
    },
    "candidate_list": {
      "type": "array",
      "description": "Non-empty ONLY when ambiguous (asset=null). Feeds the frontend AssetPicker; user picks → re-run with PIPELINE_ASSET_ID. Same shape as V47 asset_choice.json candidates.",
      "items": {
        "type": "object",
        "required": ["mfm_id", "name", "class", "has_data"],
        "additionalProperties": false,
        "properties": {
          "mfm_id": { "type": "integer" },
          "name": { "type": "string" },
          "class": { "type": "string", "enum": ["LT Panel", "Transformer", "HT Panel", "UPS", "APFC", "Diesel Generator"] },
          "load_group": { "type": ["string", "null"] },
          "panel_id": { "type": ["string", "null"] },
          "has_data": { "type": "boolean", "description": "false when lt_mfm.table_name is empty (NO-DATA flag)." }
        }
      }
    },
    "column_basket": {
      "type": "object",
      "description": "Card-agnostic, prompt-driven. The GENEROUS feasible+probable set across the resolved asset's table(s). Includes derived/const columns so non-raw metrics are covered. This is the INPUT vocabulary Layer 2's data_instructions binds each field's metric→column against.",
      "required": ["tables", "columns"],
      "additionalProperties": false,
      "properties": {
        "tables": { "type": "array", "items": { "type": "string" }, "description": "lt_panels table names in scope (usually the asset's table; topology siblings for panel/aggregate concepts)." },
        "columns": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["table", "column", "kind", "has_data"],
            "additionalProperties": false,
            "properties": {
              "table": { "type": "string", "description": "Owning lt_panels table. For kind=derived, the table whose base_columns satisfy the formula. For kind=const, '' (nameplate)." },
              "column": { "type": "string", "description": "Real verbatim column name (raw) | derived_metrics.metric_key (derived) | nameplate_config key (const). Anti-hallucination: must exist." },
              "metric": { "type": ["string", "null"], "description": "Normalized metric concept this column binds (the join key Layer 2 matches recipe fields against)." },
              "label": { "type": ["string", "null"] },
              "unit": { "type": ["string", "null"] },
              "kind": { "type": "string", "enum": ["raw", "derived", "const", "event"], "description": "raw=lt_panels col; derived=derived_metrics; const=nameplate_config; event=event-count col." },
              "has_data": { "type": "boolean" },
              "rank": { "type": ["integer", "null"], "description": "From the probable ranking (best-first); null for feasible-only entries." },
              "why": { "type": ["string", "null"], "description": "Why this column could serve the prompt (probable entries)." },
              "base_columns": { "type": ["array", "null"], "items": { "type": "string" }, "description": "For kind=derived: the reconciled real lt_panels columns the formula reads (derived_metrics.base_columns ∩ live schema)." }
            }
          }
        },
        "unmappable": {
          "type": "array",
          "description": "Concepts the prompt implied but no real column serves (logged, never fabricated).",
          "items": { "type": "object", "additionalProperties": false, "properties": { "concept": { "type": "string" }, "reason": { "type": "string" } } }
        }
      }
    }
  }
}
```

---

### 4. Layer 2 per-card INPUT

Each Layer-2 card-run is assembled deterministically: 1a's per-card story + 1b's asset & basket + the card's `cmd_catalog` row + (for group cards only) the read-only shared buffer reference. This is what the AI sees per fan-out unit. `catalog_row.contract.payload_schema_json` is the **per-card METADATA tier the AI authors into `exact_metadata`**; `catalog_row.recipe.fields` + `catalog_row.contract.data_fill_shape` are what the AI threads into `data_instructions`.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "v48/layer2_card_input",
  "title": "Layer2CardInput",
  "type": "object",
  "required": ["run_id", "card_id", "page_key", "is_group_card", "story", "asset", "column_basket", "catalog_row"],
  "additionalProperties": false,
  "properties": {
    "run_id": { "type": "string" },
    "card_id": { "type": "integer" },
    "page_key": { "type": "string" },
    "is_group_card": { "type": "boolean", "description": "true if this card belongs to an interdependency_group; then shared_ctx_ref is set and the worker has already built shared_context. Group cards point DATA at $ctx; they STILL author their own exact_metadata." },
    "group_id": { "type": ["string", "null"], "description": "interdependency_groups[].group_id when is_group_card." },
    "shared_ctx_ref": {
      "type": ["object", "null"],
      "description": "READ-ONLY pointer to the group's shared_context (built ONCE in Move 1). The atom reads DATA via $ctx; it never copies the buffer. It does NOT read METADATA from here — per-card METADATA lives on the atom itself.",
      "additionalProperties": false,
      "properties": {
        "$id": { "type": "string", "description": "Equals the shared_context.$id the atom will bind ($ctx)." },
        "buffer_keys": { "type": "array", "items": { "type": "string" }, "description": "Available buffers[].key (multi-buffer support)." },
        "interaction_seeds": { "type": "array", "items": { "type": "string" }, "description": "Scalar/enum seed names available (cursor, selection, metric, selectedBucket, …)." }
      }
    },
    "story": {
      "type": "object",
      "description": "From 1a — the constraint set for this card's swap + payload.",
      "required": ["page_story", "analytical_story"],
      "additionalProperties": false,
      "properties": {
        "page_story": { "type": "string", "description": "Layer1aOutput.story." },
        "analytical_story": { "type": "string", "description": "This card's Layer1aOutput.cards[].analytical_story — a swap target MUST match this angle." },
        "metric": { "type": "string" },
        "intent": { "type": "string", "enum": ["trend", "distribution", "snapshot", "table", "events"] },
        "template_card_ids": { "type": "array", "items": { "type": "integer" }, "description": "1a's chosen card set; a swap MUST NOT duplicate any of these (no-dup invariant)." }
      }
    },
    "asset": { "$ref": "v48/layer1b_output#/properties/asset" },
    "column_basket": { "$ref": "v48/layer1b_output#/properties/column_basket" },
    "catalog_row": {
      "type": "object",
      "description": "The full per-card cmd_catalog detail set, all keyed by card_id.",
      "required": ["card_id", "handling_class", "recipe", "contract"],
      "additionalProperties": false,
      "properties": {
        "card_id": { "type": "integer" },
        "title": { "type": "string" },
        "handling_class": { "type": "string", "enum": ["single_asset_series", "single_asset_derived", "panel_aggregate", "asset_3d", "narrative_ai", "topology_sld", "nav_index"], "description": "card_handling.handling_class." },
        "resolver_scope": { "type": "string", "enum": ["meter", "panel", "asset", "site", "none"], "description": "card_handling.resolver_scope." },
        "payload_family": { "type": ["string", "null"], "description": "card_handling.payload_family — the surviving DATA-FILL dialect analog (flat_series/tiles/scene/rail_sources_consumers/…); names the backend-frame shape the worker targets, NOT the render payload." },
        "backend_strategy": { "type": ["string", "null"], "description": "card_handling.backend_strategy — REFERENCE ONLY (aggregation relocates into V48 workers; NOT a backend2 reuse target). The worker REUSES EMS semantics (energy_delta/now_expr) verbatim, not the Django path." },
        "recipe": {
          "type": "object",
          "description": "card_data_recipe — the unresolved data recipe Layer 2 RESOLVES into data_instructions.",
          "additionalProperties": false,
          "properties": {
            "payload_shape": { "type": "string", "description": "Normalized to one of the 10 payload_shapes names. Tells which DATA tier the helper fills." },
            "orientation": { "type": ["string", "null"], "enum": ["entity", "time", "snapshot", null] },
            "entity_dim": { "type": ["string", "null"] },
            "selection_dim": { "type": ["string", "null"] },
            "selection_role": { "type": ["string", "null"] },
            "fields": {
              "type": "array",
              "description": "card_data_recipe.reconciled_fields if present, else fields. Each = an UNRESOLVED data-recipe field (the AI's intent). Layer 2 resolves metric→column + decides agg/source to produce data_instructions.fields.",
              "items": {
                "type": "object",
                "required": ["kind", "role"],
                "additionalProperties": false,
                "properties": {
                  "kind": { "type": "string", "enum": ["raw", "derived", "const", "text", "event", "segment"] },
                  "role": { "type": "string", "enum": ["kpi", "column", "series", "narrative", "cell", "line", "spoke", "tile", "segment", "row"] },
                  "label": { "type": ["string", "null"] },
                  "metric": { "type": ["string", "null"], "description": "Binding key into column_basket (raw col / derived_metrics.metric_key / nameplate key)." },
                  "unit": { "type": ["string", "null"] }
                }
              }
            }
          }
        },
        "contract": {
          "type": "object",
          "description": "card_contract_binding → contract_components — the render target + the per-card payload schema. payload_schema_json IS the METADATA tier the AI authors into exact_metadata.",
          "additionalProperties": false,
          "properties": {
            "component": { "type": "string", "description": "contract_components.name (the bound contract)." },
            "host_cmd_component": { "type": ["string", "null"], "description": "The actual CMD_V2 component (→ components.name). null = not host-renderable." },
            "canonical_shape": { "type": ["string", "null"], "description": "→ payload_shapes.name (the canonical render-payload contract; sparsely set — only a minority of the 280 components carry one)." },
            "payload_schema_json": { "type": ["object", "null"], "description": "The exact one-payload-per-card shape this component consumes — the AUTHORITATIVE source for the card's METADATA tier (the keys the AI fills in exact_metadata) AND the DATA tier the helper fills. e.g. RealTimeHeatmapSection = {metric, buckets[{label,feeders[],totalKw,totalKvar}], contractKw, selectedSampleIndex}." },
            "data_fill_shape": { "type": "string", "enum": ["flat_asset", "widgets_envelope", "shared_context"], "description": "RENAMED from frame_dialect. The DATA-FILL/mapper-input frame the WORKER targets when filling DATA — NOT what the AI emits per card. Describes the data source shape only." }
          }
        },
        "capabilities": {
          "type": "array",
          "description": "contract_capabilities — per-component metric support; gates swap feasibility.",
          "items": { "type": "object", "additionalProperties": false, "properties": { "metric": { "type": "string" }, "supported": { "type": "boolean" } } }
        },
        "controls": {
          "type": "object",
          "description": "card_controls — retained interactivity (date-sync / cross-select); seeds the tabs/segments/time-options the AI authors into exact_metadata, plus the interaction seeds the hook owns.",
          "additionalProperties": false,
          "properties": {
            "time_mode": { "type": ["string", "null"] },
            "time_options": { "type": ["array", "null"] },
            "sampling_options": { "type": ["array", "null"] },
            "segmented_tabs": { "type": ["array", "null"] },
            "defaults": { "type": ["object", "null"] }
          }
        },
        "feasibility": {
          "type": "object",
          "description": "card_feasibility — failure-logging input. Only verdict='render_real' admitted to the swap pool.",
          "additionalProperties": false,
          "properties": {
            "family": { "type": ["string", "null"] },
            "verdict": { "type": "string", "description": "e.g. render_real." },
            "required_topology": { "type": ["boolean", "null"] },
            "required_mesh": { "type": ["boolean", "null"] },
            "reason": { "type": ["string", "null"] }
          }
        }
      }
    },
    "swap_candidates": {
      "type": "array",
      "description": "card_grid_size ±15% pool, off-page, card_feasibility.verdict='render_real', NOT in story.template_card_ids. Max 6 closest.",
      "items": {
        "type": "object",
        "required": ["card_id", "title"],
        "additionalProperties": false,
        "properties": {
          "card_id": { "type": "integer" },
          "title": { "type": "string" },
          "page_key": { "type": "string" },
          "width_px": { "type": "integer" },
          "height_px": { "type": "integer" },
          "analytical_role": { "type": ["string", "null"] },
          "card_purpose": { "type": ["string", "null"] },
          "visualization": { "type": ["string", "null"] }
        }
      }
    }
  }
}
```

---

### 5. Layer 2 per-card OUTPUT — `{ exact_metadata, data_instructions }` (the morph contract)

**This is the heart of the morph.** Per card, Layer 2 emits ONE object: `{ card_id, $ctx?, render_slot, swap_decision, analytical_story, exact_metadata, data_instructions, conforms }`. There is no `atom`/`frame` branch and no per-tab dialect on the output — **every card carries `exact_metadata` (the AI-authored METADATA tier) and `data_instructions` (the parseable recipe the helper parses to FILL DATA)**, regardless of whether it is a group atom or standalone.

- `$ctx` distinguishes DATA-residence, not metadata-residence: when set, the card's DATA lives in `shared_context` (the helper projects the right slots of the shared buffer) and `data_instructions.fields[].source` points at `$ctx`; when null, the helper fills DATA inline from `live`/`test-db`. **`exact_metadata` is present and full in BOTH cases** — that IS the morphability.
- `render_slot` is where the card mounts (from `page_layout_cards.cell`/`region` + `combo_role`), e.g. `composite_card.body | composite_card.footer | rail_card`.
- The deterministic gate honors a swap only if `action='swap'` AND `confidence>=0.9` AND the criterion is non-vague AND the target is in the offered pool AND not a duplicate of any template/already-chosen card.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "v48/layer2_card_output",
  "title": "Layer2CardOutput",
  "type": "object",
  "required": ["card_id", "render_slot", "swap_decision", "analytical_story", "exact_metadata", "data_instructions", "conforms"],
  "additionalProperties": false,
  "properties": {
    "card_id": { "type": "integer", "description": "The FINAL card id (post-swap). swap_decision.origin tells if it changed." },
    "$ctx": {
      "type": ["string", "null"],
      "description": "Set iff this card is an interdependency-group member. MUST equal a shared_context.$id on the same page frame. Selects DATA-residence ($ctx buffer vs inline); it does NOT gate exact_metadata, which is present either way."
    },
    "render_slot": { "type": "string", "description": "Where the card mounts, e.g. composite_card.body | composite_card.footer | rail_card. From page_layout_cards.cell/region + combo_role." },
    "analytical_story": { "type": "string", "description": "Per-card analytical story wrt the prompt (Layer 2's own, validated against 1a's angle)." },

    "swap_decision": {
      "type": "object",
      "required": ["action", "origin"],
      "additionalProperties": false,
      "properties": {
        "action": { "type": "string", "enum": ["keep", "swap"], "description": "KEEP is the default; 0 swaps is healthy." },
        "origin": { "type": "string", "enum": ["kept", "swapped", "must_swap"], "description": "Resolved by the deterministic gate." },
        "swap_to_id": { "type": ["integer", "null"], "description": "Final id if swapped; must be in the offered pool, off-page, not a duplicate, not in template_card_ids." },
        "swap_to_title": { "type": ["string", "null"] },
        "confidence": { "type": ["number", "null"], "minimum": 0, "maximum": 1, "description": "Swap honored only if >= 0.9." },
        "criterion": { "type": ["string", "null"], "description": "Named criterion; vague values (better/relevant/nicer/…) are rejected by _criterion_ok." },
        "reason": { "type": ["string", "null"] },
        "cascade": {
          "type": "array",
          "description": "All-or-nothing combo cascade for coupled (master-selector/shared-selection/cross-highlight) cards.",
          "items": { "type": "object", "additionalProperties": false, "properties": { "slot_card_id": { "type": "integer" }, "swap_to_id": { "type": "integer" }, "swap_to_title": { "type": "string" }, "why": { "type": "string" } } }
        }
      }
    },

    "exact_metadata": {
      "type": "object",
      "description": "THE AI-AUTHORED METADATA TIER of the card's one payload — the morphable half. A flat block of the card's METADATA keys (labels · units · colours · rosters · order · thresholds · contracts · badges · tabs) for this card's payload_schema_json, every key once, byte-identical defaults, zero design-system chrome. PRESENT AND FULL on EVERY card (group atom or standalone). The stitcher flattens this with the helper-filled DATA into the ONE payload. Shape is per-card (HeatmapViewModel METADATA keys / RailViewModel METADATA keys / the matching HpqPresentation.<card> block); additionalProperties:true because the key set is card-specific. The two 'AI-default, data-overridable' slots (RTM sectionContracts; HPQ signature.spokes/selectedName) live HERE as the default, and the worker MAY overwrite from the frame.",
      "additionalProperties": true,
      "minProperties": 1
    },

    "data_instructions": {
      "type": "object",
      "description": "THE PARSEABLE RECIPE the hook/helper parses to FILL the DATA tier. Essentially a RESOLVED card_data_recipe.fields: each field carries the recipe's kind/role/metric/label/unit PLUS the L3/L6-equivalent resolution delta (column, agg, source, sql_fragment/base_columns/edge/value), wrapped in the per-card binding envelope the helper needs to FILL without re-deriving. Layer 2 NEVER fills data here — it specifies HOW to fill.",
      "required": ["fields", "orientation", "entity_dim"],
      "additionalProperties": false,
      "properties": {
        "payload_shape": { "type": "string", "description": "card_data_recipe.payload_shape — which DATA tier the helper fills." },
        "orientation": { "type": "string", "enum": ["time", "entity", "snapshot"], "description": "Row shape the helper fills (time=series, entity=roster, snapshot=single). From recipe.orientation." },
        "entity_dim": { "type": "string", "description": "What each row/series/cell IS, e.g. feeder | panel | bucket. From recipe.entity_dim." },
        "selection_dim": { "type": ["string", "null"], "description": "recipe.selection_dim." },
        "selection_role": { "type": ["string", "null"], "enum": ["both", "produces", "consumes", "emits", "none", null], "description": "Interdependency role (provisional — frontend interdependency in progress)." },
        "binding": {
          "type": ["object", "null"],
          "description": "Resolved ONCE (L3-equivalent), shared by all live-bound fields. Absent/null for a pure-$ctx atom (DATA from shared buffer) or a pure-const card.",
          "additionalProperties": false,
          "properties": {
            "asset_id": { "type": ["integer", "null"], "description": "lt_mfm.id (single-asset) or the panel mfm_id (aggregate)." },
            "table": { "type": ["string", "null"], "description": "lt_panels table name." },
            "ts_col": { "type": ["string", "null"], "description": "Timestamp column (first ts col)." },
            "panel_id": { "type": ["string", "null"], "description": "lt_mfm.panel_id — the time-series WHERE key (panels share tables; partition is panel_id NOT table)." },
            "nameplate_scope": { "type": "string", "default": "default", "description": "Drives :NAME literals (mfm_type:hv → V_NOM=11000, else default V_NOM=415)." }
          }
        },
        "window": {
          "type": ["object", "null"],
          "description": "Window/sampling seed. Re-slice = re-bind only (the helper binds :start/:end/:bucket; time is NEVER literal). Absent for snapshot-only cards.",
          "additionalProperties": false,
          "properties": {
            "lookback": { "type": ["string", "null"], "description": "e.g. today | yesterday | last-7-days | this-month | shift-8h." },
            "sampling": { "type": ["string", "null"], "description": "e.g. hourly | by-shift | raw." },
            "time_mode": { "type": ["string", "null"], "description": "choice | fixed (from card_controls.time_mode)." }
          }
        },
        "fields": {
          "type": "array",
          "description": "One RESOLVED field per data slot. The spine of data_instructions: a resolved card_data_recipe.fields. kind/role/metric/label/unit/filters_table come from the recipe; column/agg/source/sql_fragment/base_columns/edge/value are the resolution delta.",
          "minItems": 1,
          "items": {
            "type": "object",
            "required": ["kind", "role", "metric", "source"],
            "additionalProperties": false,
            "properties": {
              "slot": { "type": ["string", "null"], "description": "Named DATA key this field writes into (e.g. kw, iUnbalance, sag). The helper writes the filled value at this slot of the payload's DATA tier." },
              "kind": { "type": "string", "enum": ["raw", "derived", "const", "text", "event", "segment"], "description": "From the recipe. Encodes the agg/fill strategy." },
              "role": { "type": "string", "enum": ["kpi", "column", "series", "narrative", "cell", "line", "spoke", "tile", "segment", "row"] },
              "metric": { "type": "string", "description": "Normalized metric concept (the column_basket join key)." },
              "column": { "type": ["string", "null"], "description": "RESOLVED: real lt_panels column (raw/event) | derived_metrics.metric_key (derived) | nameplate key (const) | label column (text). Guard-railed to the meter's real dictionary; null for pure $ctx-projected or computed-only slots." },
              "label": { "type": ["string", "null"], "description": "From the recipe (verbatim)." },
              "unit": { "type": ["string", "null"], "description": "From the recipe (verbatim)." },
              "agg": { "type": ["string", "null"], "enum": ["avg", "last", "sum", "count", "derived", null], "description": "RESOLVED fill strategy (encodes kind): derived→derived_metrics.sql_fragment with :NAME from nameplate_config; count/sum on *_event_active→rising-edge COUNT(*) FILTER; *_energy_import/export_*→MAX-MIN odometer; else AVG. null for const/text." },
              "source": { "type": "string", "enum": ["live", "test-db", "const", "$ctx"], "description": "live=socket frame/fetch_live; test-db=CI fixture in the IDENTICAL Snapshot shape (interchangeable at mapper boundary); const=baked literal, never queried; $ctx=projected from the shared buffer (group atoms). OPEN (V48_BUILD_SPEC_REVIEW.md G2, pending user): the $ctx FORM is unresolved — this bare-token enum disagrees with the dotted $ctx.<key>/$ctx.buffers.<key> form used in §5a/§6/§7 and in PROMPTS/SIGNATURES (the helper needs the buffer name). When resolved, either make this a pattern (^\\$ctx(\\.[a-z_]+)?$) or add a sibling buffer_key, and align all four files." },
              "value": { "type": ["number", "string", "null"], "description": "For kind=const: the baked literal (e.g. IEEE_519_LIMIT=5.0). NOT queried." },
              "base_columns": { "type": ["array", "null"], "items": { "type": "string" }, "description": "For kind=derived: the reconciled real lt_panels columns the formula reads." },
              "sql_fragment": { "type": ["string", "null"], "description": "For kind=derived: the derived_metrics formula with :NAME nameplate placeholders." },
              "nameplate_refs": { "type": ["array", "null"], "items": { "type": "string" }, "description": "For kind=derived: the :NAME literals to substitute from nameplate_config (scoped by binding.nameplate_scope)." },
              "edge": { "type": ["string", "null"], "enum": ["rising", "falling", null], "description": "For kind=event: edge semantics for the COUNT(*) FILTER." },
              "filters_table": { "type": ["string", "boolean", "null"], "description": "From reconciled_fields — the lt_panels table the live fill queries / a filter flag." },
              "selects": { "type": ["string", "null"], "description": "From the recipe (e.g. 'node' for table cells)." },
              "color": { "type": ["string", "null"], "description": "Per-field colour when the recipe carries one (e.g. series line colour). NOTE: presentation colours generally belong in exact_metadata; only data-bound per-series colour rides here." },
              "has_data": { "type": ["boolean", "null"], "description": "L3 resolution result: false when the resolved column has no data in window (honest-degrade input)." }
            }
          }
        }
      }
    },

    "controls": {
      "type": ["object", "null"],
      "description": "Carried-through interactivity from card_controls (time/sampling/segmented) — retained as in EMS. The hook owns the live cells; this is the seed/default set.",
      "additionalProperties": true
    },
    "conforms": { "type": "boolean", "description": "false on an honest gap (no data in window, unwired component, no aggregate builder) — LOGGED, never fabricated. No reloop/re-route. The DATA slot degrades honestly; exact_metadata still emits." },
    "failure": {
      "type": ["object", "null"],
      "description": "Set when conforms=false. Exact error + details for the failure log; the DATA slot is left unfilled (exact_metadata stands).",
      "additionalProperties": false,
      "properties": {
        "stage": { "type": "string", "enum": ["asset", "columns", "swap", "aggregate", "emit"] },
        "reason": { "type": "string" },
        "detail": { "type": ["string", "null"] }
      }
    }
  }
}
```

---

### 5a. The per-card MERGED PAYLOAD — what the component consumes (RTM heatmap worked example)

After Layer 2 emits `{ exact_metadata, data_instructions }` and the helper PARSES `data_instructions` to FILL the DATA tier, the stitcher merges the two into **ONE flat payload, every key EXACTLY once, no `root`, zero chrome** — this is what the component renders. This object is NOT a Layer-2 output; it is the post-fill result (`{...exact_metadata, ...filled_data}`).

For the RTM heatmap card (component `RealTimeHeatmapSection`, producer `buildHeatmapViewModel`), the merged `HeatmapViewModel` payload:

```jsonc
{
  // ── DATA tier (helper FILLED from data_instructions.fields — source=live OR test-db) ──
  "history": [ /* HistorySample[] — AUTHORITATIVE roster + ORDER; each sample.sections[].feeders[]
                  carries kw/kvar/kva/pf/voltage/current (raw) + iUnbalance/loadPct (derived)
                  + statuses{} per MetricKey. HeatmapSection[] derived ON DEMAND, never stored. */ ],
  // initial interaction state — DATA tier, but HOOK-SEEDED (read-only seed, NOT Layer-2-authored;
  // the helper seeds these from shared_context.interaction / card_controls.defaults):
  "metric": "all",
  "selectedSampleIndex": 11,
  "liveMode": true,
  "selectedSectionId": null,
  "selectedFeederId": null,

  // ── METADATA tier (Layer 2 AUTHORED in exact_metadata — byte-identical defaults shown) ──
  "title": "Real Time Monitoring",
  "metricTabs": [ {"key":"all","label":"All Metrics"}, {"key":"kw","label":"kW"}, /* … METRIC_ORDER */ ],
  "metricAxisLabels": { /* ALL_METRICS_AXIS_LABELS */ },
  "statusColors": { "low":"…", "normal":"…", "moderate":"…", "high":"…", "critical":"…" },
  "statusLegend": [ {"status":"normal","label":"Normal"}, /* … STATUS_LEGEND */ ],
  "units": { "power": "kW", "percent": "%", "reactive": "kVAr" },
  "descriptors": { "supplied": "supplied", "contract": "contract" },
  "selectionColors": { "highlight": "<brand.500>", "rowLabel": "<warm.700>" },
  "bandThresholds": { "stops": { /* per MetricKey */ },
                      "divisors": { "kw":250, "kvar":150, "current":400, "iUnbalance":15,
                                    "voltageNominal":415, "voltageSlope":4 } },
  // AI-default, DATA-OVERRIDABLE: Layer 2 authors SECTION_CONTRACT_KW; the worker overwrites
  // from snapshot.config.sectionContracts when the frame carries it ({...AI_DEFAULT, ...backend}):
  "sectionContracts": { "incomers": 2700, "ups": 1500, "bpdb": 600, "hhf": 600 }
}
```

Notes on the example (grounded in `realtime-monitoring/types.ts`, `heatmapMetrics.ts:225-261`):
- The footer is a SUB-COMPONENT reading `data.heatmap.*` — there is NO separate "footer" payload. The heatmap card = this one `HeatmapViewModel`.
- `statusColors`/`bandThresholds`/`metricTabs`/`statusLegend`/`units`/`descriptors`/`selectionColors`/`title` are `exact_metadata` (NOT `data_instructions`).
- `IEEE_519_LIMIT`-style limit lines, when present on a card, are `kind:const` `data_instructions.fields` with a baked `value` — they fill a DATA slot but are never queried.
- For the group case, the heatmap atom's `data_instructions.fields[].source="$ctx"` and `binding=null` (DATA projected from `shared_context.buffers.history`); the `exact_metadata` block above is STILL emitted in full on the atom.

The rail card (component producer `buildRailViewModel`) is the SECOND payload of the same group: same pattern — `exact_metadata` = `{title, subtitle, statusBadge.dsTone, supply.{title,unit,deltaColor,deltaGlyph,breakdown,consumedHint}, trend.{title,lineColor,areaOpacity,bottomStats}, quickStats[], quickStatsLayout}`; DATA = all numeric leaves (value/denominator/delta/series/breakdown.value) the helper computes per selection from the SAME shared `history` buffer.

---

### 6. DATA-FILL frame schema — the mapper-input target (demoted from "Layer-2 output")

**This is NOT what Layer 2 emits per card.** It is the **DATA-fill frame** the WORKER/HELPER fills and the FE `*Mapper.ts` consumes (the only place the per-tab "dialect" survives). The live socket frame (`ws/mfm/{id}/{screen}/`) has this shape; the test-DB fixture produces the IDENTICAL shape so live and fixture are interchangeable at the mapper boundary. The helper reads `data_instructions` and produces one of these shapes, which the mapper turns into the DATA tier of the card payload. Selected by `data_fill_shape` (the renamed `frame_dialect`), driven by `card_handling.payload_family`. **OPEN (V48_BUILD_SPEC_REVIEW.md G4/G6, pending user):** the `oneOf` below has only 3 branches — the 4th `column_row` (column/queue) frame for `individual-feeder-meter-shell/*` cards is still missing, and the `payload_family → data_fill_shape` crosswalk that makes "driven by `card_handling.payload_family`" concrete is not yet specified (two overlapping dialect vocabularies, no mapping table).

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "v48/data_fill_frame",
  "title": "DataFillFrame",
  "description": "Mapper-input DATA frame the worker fills (NOT a Layer-2 per-card output). One of three backend-frame shapes; demoted from the old frame.oneOf union.",
  "oneOf": [
    {
      "title": "FlatAssetFillFrame",
      "description": "Asset tabs (DG / transformer / UPS). History arrays at top level alongside snapshot. data_fill_shape='flat_asset'; payload_family≈flat_series.",
      "type": "object",
      "required": ["type", "snapshot"],
      "properties": {
        "type": { "type": "string", "enum": ["snapshot", "update", "tick"] },
        "asset_id": { "type": ["integer", "null"] },
        "asset_name": { "type": ["string", "null"] },
        "asset_type": { "type": ["string", "null"] },
        "page": { "type": ["string", "null"] },
        "ts": { "type": ["string", "null"] },
        "snapshot": { "type": "object", "description": "e.g. ThermalLifeSnapshot / UpsNativeSnapshot — domain DATA values only; the METADATA/render-shaping is the per-card payload (§5/§5a), not here." }
      },
      "additionalProperties": true
    },
    {
      "title": "AggregateFillFrame",
      "description": "electrical / lt-pcc panel-overview. Discriminator isAggregateEnvelope: has widgets, no queue/buckets/enqueue. data_fill_shape='widgets_envelope'; payload_family≈scene/rail_sources_consumers. Built by the V48 aggregate worker (panel_members + ems_aggregate).",
      "type": "object",
      "required": ["type", "mfm_id", "widgets"],
      "additionalProperties": false,
      "properties": {
        "type": { "type": "string", "enum": ["snapshot", "tick", "widget_update"] },
        "mfm_id": { "type": "integer" },
        "mfm_name": { "type": "string" },
        "panel_id": { "type": "string" },
        "mfm_type": { "type": "string" },
        "page": { "type": "string" },
        "ts": { "type": "string" },
        "widgets": { "type": "object", "description": "Keyed widget DATA shapes, e.g. {cumulative, live_power, energy_trend, demand_profile} or {config, header, incomers, consumers, sankey, ai_summary}. DATA only — the morphable chrome is per-card exact_metadata." }
      }
    },
    {
      "title": "SharedContextFillFrame",
      "description": "Interdependency-group buffer fill. data_fill_shape='shared_context'. The DATA buffer (history/periods) the worker fills ONCE into shared_context.buffers; group atoms project slots from it via $ctx. This is the RTM real-time-monitoring aggregate (widgets.feeders[].queue[] → HistorySample[]) / HPQ periods envelope.",
      "type": "object",
      "required": ["type", "buffers"],
      "additionalProperties": true,
      "properties": {
        "type": { "type": "string", "enum": ["snapshot", "tick"] },
        "mfm_id": { "type": ["integer", "null"] },
        "ts": { "type": ["string", "null"] },
        "buffers": { "type": "object", "description": "Keyed typed DATA arrays (history: HistorySample[] | periods: PQPeriod[] | …) + apiExtras passthrough. The single shared DATA buffer." }
      }
    }
  ]
}
```

---

### 7. shared_context — single DATA buffer + interaction seeds + truly-shared config

Built ONCE per interdependency group by the Move-1 worker (relocated L6.2). It holds **only**: the single DATA buffer(s) (one copy, the SEED — the socket stays the live-merge owner), the host-owned interaction seeds, and the truly-shared group config. **Per-card METADATA does NOT live here** — each atom carries its own `exact_metadata` (§5). `buffers` generalizes the single `history[]` to N independently-windowed buffers. Functions NEVER appear here (invariant #7).

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "v48/shared_context",
  "title": "SharedContext",
  "type": "object",
  "required": ["$id", "asset", "buffers", "interaction", "config"],
  "additionalProperties": false,
  "properties": {
    "$id": { "type": "string", "description": "Binding token, e.g. 'rtm_ctx'. An atom's $ctx must equal this. Derived from interdependency_groups[].group_id." },
    "asset": {
      "type": "object",
      "required": ["mfm_id"],
      "additionalProperties": false,
      "properties": {
        "mfm_id": { "type": "integer" },
        "panel_label": { "type": ["string", "null"], "description": "e.g. 'PCC-1A'." },
        "table": { "type": ["string", "null"] },
        "panel_id": { "type": ["string", "null"], "description": "Time-series WHERE key (panels share tables; partition is panel_id NOT table)." }
      }
    },
    "buffers": {
      "type": "array",
      "description": "N windowed DATA buffers — the SINGLE DATA copy for the group. Single-buffer RTM = one entry keyed 'history'. Each buffer keeps its OWN socket as the live-merge owner; the seeded array is the SEED, not the sole source. Filled by the worker from the SharedContextFillFrame (§6).",
      "minItems": 1,
      "items": {
        "type": "object",
        "required": ["key", "history", "socket_owner"],
        "additionalProperties": false,
        "properties": {
          "key": { "type": "string", "description": "Buffer name, e.g. history | periods | batteryHistory | autonomyHistory. Atoms read via $ctx.buffers.<key> (or $ctx.history for the canonical one)." },
          "history": {
            "type": "array",
            "description": "The EXACT typed array the FE hook consumes (e.g. HistorySample[] / PQPeriod[]). Drop-in seed. Carry the whole typed snapshot incl apiExtras.",
            "items": { "type": "object" }
          },
          "range": { "type": ["string", "null"], "description": "Window seed, e.g. Today | Last month." },
          "sampling": { "type": ["string", "null"], "description": "Per-buffer sampling seed." },
          "socket_owner": { "type": "boolean", "default": true, "description": "true = a live socket owns live-merge for this buffer (required for byte-identical live behavior)." }
        }
      }
    },
    "interaction": {
      "type": "object",
      "description": "Host-state SEEDS — the hook's UI-selection state (the THIRD class, owned by neither Layer 2 nor the worker). ANY host-owned plain scalar/enum is a seed from <seed>.initial. Functions never travel here. One emit → one hook setter → every atom's payload recomputes consistently (Approach B). The atom payload carries only a read-only SEED of these.",
      "additionalProperties": false,
      "properties": {
        "cursor": { "type": ["object", "null"], "properties": { "dimension": { "type": "string" }, "initial": {}, "live_default": { "type": "boolean" } } },
        "selection": { "type": ["object", "null"], "properties": { "dimension": { "type": "string" }, "initial": {} } },
        "metric": { "type": ["object", "null"], "properties": { "dimension": { "type": "string" }, "domain": { "type": "array", "items": { "type": "string" } }, "initial": { "type": "string" } } },
        "scalars": {
          "type": "object",
          "description": "Open map of any other host-owned scalar/enum seed (selectedLabel, selectedPeriod, selectedBucket, selTime, series, tab, compositeView, sampling, liveMode, …). Each value = { initial: <scalar/enum> }.",
          "additionalProperties": { "type": "object", "properties": { "initial": {}, "domain": { "type": ["array", "null"] } } }
        },
        "couplings": {
          "type": "array",
          "description": "Looked up from cmd_catalog (card_link + selection_dimension). AI validates, never invents.",
          "items": {
            "type": "object",
            "required": ["dimension"],
            "additionalProperties": false,
            "properties": {
              "dimension": { "type": "string" },
              "unit": { "type": ["string", "null"], "description": "selection_dimension.unit, e.g. mfm_id | label | route_path." },
              "socket_command": { "type": ["string", "null"], "description": "selection_dimension.socket_command, e.g. select_feeder | select_section." },
              "is_navigation": { "type": ["boolean", "null"] },
              "host_wired": { "type": ["boolean", "null"] },
              "src_card": { "type": ["integer", "null"] },
              "dst_card": { "type": ["integer", "null"] },
              "link_type": { "type": ["string", "null"] }
            }
          }
        }
      }
    },
    "config": {
      "type": "object",
      "description": "TRULY-SHARED group-level static config from card_controls.defaults (sample counts, tick intervals). NOTE: per-card METADATA does NOT belong here. The 'AI-default, data-overridable' slots (section_contract_kw, HPQ signature spokes/selectedName) are per-card METADATA carried on each atom's exact_metadata, NOT shared config (Open Decision D resolved: atom-carried).",
      "additionalProperties": true,
      "properties": {
        "sample_count": { "type": ["integer", "null"] },
        "tick_interval_ms": { "type": ["integer", "null"] }
      }
    },
    "apiExtras": { "type": ["object", "null"], "description": "Whole-typed-boundary passthrough — e.g. H&PQ priorityRows/signature. Carried as DATA, not a hand-picked subset." }
  }
}
```

---

### 8. Page frame envelope

The per-page emit. Interdependent groups emit `{ shared_context, cards:[ per-card outputs ] }` (each card carrying its own `exact_metadata` + `$ctx`-bound `data_instructions`). Standalone pages emit per-card outputs whose `data_instructions` fill DATA inline. A page can carry multiple groups (one `shared_context` each) plus standalone cards; `$ctx`↔`$id` resolution is by the deterministic stitcher, which then runs the DATA fill and merges each card to its one payload.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "v48/page_frame_envelope",
  "title": "PageFrameEnvelope",
  "type": "object",
  "required": ["page_key", "data_fill_shape", "cards"],
  "additionalProperties": false,
  "properties": {
    "page_key": { "type": "string" },
    "data_fill_shape": {
      "type": "string",
      "enum": ["shared_context", "flat_asset", "widgets_envelope"],
      "description": "RENAMED from frame_dialect. Describes the DATA-FILL source shape (§6) only — NOT the per-card render payload. shared_context=interdependent groups; flat_asset=asset tabs; widgets_envelope=panel-overview aggregates. Every card on the page still carries its own exact_metadata regardless of this value."
    },
    "layout": { "$ref": "v48/layer1a_output#/properties/layout", "description": "Verbatim placement carried through from 1a." },

    "shared_contexts": {
      "type": ["array", "null"],
      "description": "Present when any group on the page is interdependent (data_fill_shape='shared_context'). One per interdependency group (multi-group pages allowed). Each $id is unique on the page. Holds the single DATA buffer + interaction seeds + shared config; NO per-card METADATA.",
      "items": { "$ref": "v48/shared_context" }
    },
    "interdependency_group": { "type": ["string", "null"], "description": "Set when a single group dominates the page (e.g. 'rtm-combo')." },
    "cards": {
      "type": "array",
      "description": "Every emitted card on the page (Layer2CardOutput). Each carries exact_metadata (always) + data_instructions. Group members set $ctx (DATA from a shared_contexts[].$id buffer); standalone cards leave $ctx null (DATA filled inline). The stitcher runs the helper fill and merges {...exact_metadata, ...filled_data} into the one payload per card.",
      "items": { "$ref": "v48/layer2_card_output" }
    },

    "config_endpoint": {
      "type": ["object", "null"],
      "description": "Side payload for GET /api/mfm/{id}/config/ (rated_kw nameplate) — y-axis auto-scale, NOT in the WS frame. V48 must populate it.",
      "additionalProperties": false,
      "properties": {
        "mfm_id": { "type": "integer" },
        "panel_id": { "type": ["string", "null"] },
        "mfm_type": { "type": ["string", "null"] },
        "config_table": { "type": ["string", "null"] },
        "config": { "type": "object", "description": "e.g. { rated_kw: <number> }." }
      }
    }
  },
  "allOf": [
    { "if": { "properties": { "data_fill_shape": { "const": "shared_context" } } },
      "then": { "required": ["shared_contexts"] } }
  ]
}
```

---

### 9. Orchestrator state object

The single mutable state threaded across the harness (1a ∥ 1b → join → Layer 2 partition → Move 1/2/3 → assemble). Mirrors V47's run state but with no reloop/re-route fields — failures only accumulate in `failures[]`.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "v48/orchestrator_state",
  "title": "OrchestratorState",
  "type": "object",
  "required": ["run_id", "input", "phase"],
  "additionalProperties": false,
  "properties": {
    "run_id": { "type": "string" },
    "input": { "$ref": "v48/pipeline_input" },
    "phase": {
      "type": "string",
      "enum": ["routing", "awaiting_asset_choice", "layer2_partition", "layer2_fanout", "assembling", "done", "failed"],
      "description": "awaiting_asset_choice = 1b ambiguous; harness wrote asset_choice.json and returns until PIPELINE_ASSET_ID re-run."
    },
    "layer1a": { "type": ["object", "null"], "$ref": "v48/layer1a_output", "description": "Set when 1a completes." },
    "layer1b": { "type": ["object", "null"], "$ref": "v48/layer1b_output", "description": "Set when 1b completes; if candidate_list non-empty, phase→awaiting_asset_choice." },
    "asset_choice": {
      "type": ["object", "null"],
      "description": "Written when 1b is ambiguous; consumed by the frontend AssetPicker. Mirror of V47 asset_choice.json.",
      "additionalProperties": false,
      "properties": {
        "needs_asset_choice": { "type": "boolean", "const": true },
        "prompt": { "type": "string" },
        "mention": { "type": ["string", "null"] },
        "candidates": { "$ref": "v48/layer1b_output#/properties/candidate_list" }
      }
    },
    "partition": {
      "type": ["object", "null"],
      "description": "Step-0 result (deterministic). Group/standalone split from cmd_catalog couplings — UNCHANGED by the morph.",
      "additionalProperties": false,
      "properties": {
        "groups": { "$ref": "v48/layer1a_output#/properties/interdependency_groups" },
        "standalone_card_ids": { "type": "array", "items": { "type": "integer" } }
      }
    },
    "shared_contexts": {
      "type": "array",
      "description": "Move-1 worker outputs, one per group, keyed by $id. Built BEFORE the per-card fan-out. Single DATA buffer + interaction seeds + shared config; NO per-card METADATA.",
      "items": { "$ref": "v48/shared_context" }
    },
    "card_outputs": {
      "type": "array",
      "description": "Move-2 fan-out results, one per card (parallel). Each = {exact_metadata, data_instructions, …}. Keyed by final card_id.",
      "items": { "$ref": "v48/layer2_card_output" }
    },
    "page_frame": { "type": ["object", "null"], "$ref": "v48/page_frame_envelope", "description": "Move-3 stitched + DATA-filled + assembled final emit (one merged payload per card)." },
    "failures": {
      "type": "array",
      "description": "Accumulated; NEVER triggers reloop/re-route (unlike V47). Each = exact error + details.",
      "items": {
        "type": "object",
        "required": ["stage", "reason"],
        "additionalProperties": false,
        "properties": {
          "stage": { "type": "string", "enum": ["routing", "asset", "columns", "partition", "shared_context", "swap", "aggregate", "emit"] },
          "card_id": { "type": ["integer", "null"] },
          "group_id": { "type": ["string", "null"] },
          "reason": { "type": "string" },
          "detail": { "type": ["string", "null"] }
        }
      }
    },
    "log_path": { "type": "string", "description": "logs/ai_<run_id>.jsonl — every :8200 LLM call logged via the ai_log urlopen monkeypatch." }
  }
}
```

---

Consistency notes (the invariants every consumer depends on):
- `card_id` is the integer `cards.id` in **every** schema; `page_key` is the slug in every schema. The card→page_spec bridge is `card_handling.page_key` / `page_layout_cards`, never `cards.page` (which keys on `pages.area`).
- **Layer 2 per-card OUTPUT = `{ card_id, $ctx?, render_slot, exact_metadata, data_instructions }`** — there is no `atom`/`frame` branch and no per-tab dialect on the output. `exact_metadata` (the AI-authored METADATA tier) is present and full on EVERY card; `data_instructions` is the parseable recipe the helper parses to FILL the DATA tier.
- The merged **one payload per card** = `{...exact_metadata, ...helper_filled_data}` — flat, every key once, no `root`, zero chrome (§5a). It is the post-fill result, not a Layer-2 output.
- The three dialects are **DATA-FILL frames only** (§6, `DataFillFrame`), the mapper-input target the worker fills — NOT what the AI emits per card. `data_fill_shape` (renamed from `frame_dialect`) selects among them and lives in `catalog_row.contract` (4) and the page envelope (8); it describes the DATA source shape, never the morphable METADATA.
- `atom.$ctx` (5) ↔ `shared_context.$id` (7) ↔ `interdependency_groups[].group_id` (2) are the same identity chain, resolved by the stitcher (8). `$ctx` selects DATA-residence (`shared_context` buffer vs inline), NOT metadata-residence — `exact_metadata` rides on the card either way.
- `column_basket.columns[].column` + `.metric` (3) are the binding keys that `data_instructions.fields[].column`/`.metric` (5) and `catalog_row.recipe.fields[].metric` (4) match against — one vocabulary end-to-end.
- `shared_context` (7) holds the single DATA buffer + interaction seeds + truly-shared config ONLY. **Per-card METADATA does NOT belong in `shared_context`** — each atom carries its own `exact_metadata`. The 'AI-default, data-overridable' slots (RTM `sectionContracts`; HPQ `signature.spokes`/`selectedName`) are per-card METADATA on the atom (Open Decision D = atom-carried), defaulted by the AI and overwritten by the worker when the frame carries them.
- `handling_class ∈ {panel_aggregate, topology_sld}` (4) is the gate that fires the aggregate worker (Move 1, `panel_members` + `ems_aggregate`, verified topology direction: outgoing→source, incoming→consumer) to FILL the DATA tier; everything else (`single_asset_*`) is fetch+list. This gates DATA fill only — `exact_metadata` is authored the same way regardless. **OPEN (V48_BUILD_SPEC_REVIEW.md G9, pending user):** the DATA-fill routing does not yet branch a `narrative_ai` atom that lives inside a `panel_aggregate`/`shared_context` group (e.g. combo-member AiSummary) — its `exact_metadata` is authored normally, but its DATA-fill scope case is unspecified.
- **§B4 invariants are build rules** (see the §B4 section): one payload per card, every key once, no `root`, byte-identical default, producer-always-populates, new renderers opt-in default-OFF, zero chrome, LIVE Storybook-sentinel acceptance gate. The acceptance gate is a LIVE mutate-one-`exact_metadata`-field-and-read-the-DOM check, NOT golden-payload comparison alone.
- **Buildable-today scope (provisional):** the one-payload `{exact_metadata, data_instructions}` contract is **VALIDATED-grounded** on RTM + panel-overview HPQ (the §B4 reference templates — copy `HeatmapViewModel`/`RailViewModel`/`HpqPresentation` directly). Per canon MORPH STATUS (live-verified via the Storybook §B4 sentinel, `V48_STORYBOOK_MORPH_VERIFICATION.md`), the morph is **WIDESPREAD, not RTM/HPQ-only** — ~36/59 EMS cards are strongly/moderately payload-driven across ALL panels (incl. Energy & Power, Voltage & Current, Power Quality), so most surfaces DO have a per-card METADATA payload to author into. The remaining **~23 weak/zero cards are the punch-list** (e.g. V&C Phase Rows / Deviation Band + the `Max:430KW` unit bug, some aggregate cards): for those there is not yet a clean METADATA payload, so V48 either waits for the CMD V2 morph on that sub-card or emits DATA-only + accepts hardcoded chrome. (The OLD "only ~7 cards / 2 tabs" framing, from the stale `PAYLOAD_AUDIT_ALL`, is SUPERSEDED.) Frontend interdependency wiring (Approach B atom `exact_metadata` on the shared-buffer atoms) is STILL IN PROGRESS — mark provisional, grounded on the RTM `useRealTimeMonitoringData` hook.
- No reloop/re-route anywhere: `conforms=false` + `failure`/`failures[]` is the only failure path (5, 9). On a DATA gap the slot degrades honestly; `exact_metadata` still emits.