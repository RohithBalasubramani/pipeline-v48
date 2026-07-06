> Part of the V48 build-spec, generated 2026-06-23; **REWRITTEN 2026-06-29 to the CMD V2 payload-morph model** (commit dfded69, CLAUDE.md §B4 "one payload per card"). See V48_BUILD_SPEC.md for the index, and V48_PAYLOAD_MORPH_CORRECTION.md for the full re-grounding this file enacts.

All columns confirmed against the live DB. The morph rewrite changes ONLY Layer 2 (and the Move-1 worker call): Layer 2's per-card output is now **`{ exact_metadata, data_instructions }`** — the AI authors the FINISHED, byte-identical METADATA block and emits a PARSEABLE data-fill recipe; the helper/worker parses the recipe and fills the DATA tier. 1a (storytelling router) and 1b (asset-resolve + card-agnostic column basket + candidate list) are **unchanged by the morph** and carry forward verbatim.

## Per-layer prompts

> V48 has **3 pure-AI layers (1a, 1b, 2)** plus **one AI call inside the Layer-2 Move-1 worker** (the DATA-fill aggregation-spec call). All four are Qwen 3.6 calls. The prompts below are concrete and paste-ready — they adapt the verified V47 prompts (`pipeline_v47/pipeline.py:route_l1`, `column_resolve.py:ASSET_SYSTEM`/`SYSTEM`, `layer2_swap.py:SYSTEM`, `l6_2.py:card_config`) and emit exactly the §1–§8 contracts. Filter `cmd_catalog` to `status='live'` in every read.

### THE CORRECTED CARD CONTRACT (the rule every Layer-2 prompt enforces)

A card is a **pure function of ONE flat payload object `{data + metadata}`**, every key EXACTLY once, no second `root`, **zero design-system chrome**, **byte-identical defaults** (CLAUDE.md §B4:201–218). The payload carries two tiers; a third never does:

```
Card payload (ONE flat object, every key once):
  ── DATA tier ────────── numbers + initial interaction state  → the WORKER/HELPER fills (from data_instructions)
  ── METADATA tier ────── labels · units · colours · rosters · order · thresholds
                          · contracts · badges · tabs           → LAYER 2 authors (exact_metadata), AI-morphs per prompt
  ── (DESIGN-SYSTEM CHROME) pixel geometry · fonts · Card/SegmentedControl markup · grid
                          → tokens/primitives, NEVER on the payload (by design)
```

Layer 2's per-card OUTPUT splits these by ownership: **`{ exact_metadata, data_instructions }`** (Decision A, hybrid).
- **`exact_metadata`** = the FINISHED METADATA block the AI authors (every label/unit/roster/order/threshold/contract/colour/badge/tab), with **byte-identical defaults copied from the card's static config**, morphed per the prompt + 1a story. This IS the per-card one-payload METADATA tier (`HeatmapViewModel`/`RailViewModel` METADATA keys for RTM; the matching `HpqPresentation.<card>` block for HPQ).
- **`data_instructions`** = a PARSEABLE recipe (NOT data, NOT SQL): a *resolved* `card_data_recipe.fields` — each field carries the recipe's `kind/role/metric/label/unit/selects/filters_table` PLUS the resolution delta (`column/agg/source/sql_fragment/base_columns/nameplate_refs/edge/value/has_data`) + a per-card envelope (`payload_shape/orientation/entity_dim/selection_dim/selection_role/binding/window`; fill `source` is per-field). The HOOK/HELPER functions parse it and FILL the DATA tier, and keep owning live state + interactivity + interdependency.

The per-tab "dialect" survives ONLY as the **DATA-fill (mapper-input) shape** the helpers target — NOT as a Layer-2 output. The canonical `data_fill_shape` enum (CONTRACTS §6) is `flat_asset | widgets_envelope | shared_context`. `data_instructions.{payload_shape, orientation}` (+ per-field `fields[].source`) tells the helper which fill shape to read. (OPEN, pending user — build-spec review fix #4: the 4th `column_row` DATA-fill dialect, for the `individual-feeder-meter-shell/*` single-meter family, is NOT yet in the CONTRACTS enum; do not treat it as a surviving dialect until it is added.)

§B4 invariants every emit must satisfy (build rules):
- ONE payload per card, every key once, **no `root`**, no duplicate `title`/`sections`/`contractKw`.
- **byte-identical default** — every metadata default = today's rendered bytes; only a mutation moves a render.
- every metadata field **REQUIRED and always populated by the producer** (`data.X ?? CONST` is morphable only if the producer always fills X).
- new renderers **opt-in default-OFF** (e.g. HPQ `showLegend:false` — a default-ON legend was rejected for changing the resting render).
- **zero chrome** on the payload (functions/ReactNode/3D/onClick are attached downstream, never emitted).
- **LIVE Storybook-sentinel verification** (mutate ONE metadata field at :6008, read the card DOM) is the acceptance gate — green RTL tests + byte-identical defaults HID 3 real RTM gaps.

### Shared Qwen call convention (all four calls — paste once)

Every AI call in V48 uses the identical convention (copied verbatim from every V47 layer). Per the atomic-structure rule this lives in its own file, e.g. `layers/_shared/llm.py`, and `loads_lenient` (the truncation-salvage parser) stays in its own file `layers/_shared/json_salvage.py` (ported verbatim from `column_resolve.py:46-103`).

```python
# layers/_shared/llm.py  — one dedicated file, imported by all four AI calls
import json, re, urllib.request
LLM_URL = "http://localhost:8200/v1/chat/completions"   # env override: LLM_URL
MODEL   = "Qwen/Qwen3.6-35B-A3B-FP8"                     # env override: MODEL

def qwen(system, user, *, timeout=120, salvage=True):
    """The ONE Qwen 3.6 call shape for V48. temp 0, json_object, thinking OFF.
    FAIL-OPEN: a dead/slow LLM degrades exactly ONE card/layer-unit, never crashes the run."""
    payload = {"model": MODEL, "temperature": 0,
               "response_format": {"type": "json_object"},
               "chat_template_kwargs": {"enable_thinking": False},
               "messages": [{"role": "system", "content": system},
                            {"role": "user",   "content": user}]}
    req = urllib.request.Request(LLM_URL, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    d = json.load(urllib.request.urlopen(req, timeout=timeout))      # ai_log monkeypatch logs this to logs/ai_<run_id>.jsonl
    txt = re.sub(r"<think>.*?</think>", "", d["choices"][0]["message"]["content"], flags=re.DOTALL)
    if salvage:
        from .json_salvage import loads_lenient
        return loads_lenient(txt), d.get("usage", {}).get("prompt_tokens", 0)
    m = re.search(r"\{.*\}", txt, re.DOTALL)
    return (json.loads(m.group(0)) if m else {}), d.get("usage", {}).get("prompt_tokens", 0)
```

Per-call settings table (the only knobs that vary):

| AI call | timeout | parse | FAIL-OPEN default |
|---|---|---|---|
| 1a storytelling router | 120s | `re.search` (small JSON) | `{page_key: keys[0], metric:"power", intent:"trend", story:"", cards:[], interdependency_groups:[]}` |
| 1b asset-resolve | 60s | `re.search` | ambiguous → all has-data candidates of inferred class |
| 1b column-basket | 120s | `loads_lenient` (truncation-prone) | `{column_basket:{tables:[],columns:[],unmappable:[]}}` |
| **Layer 2 per-card (exact_metadata + data_instructions)** | 120s | `loads_lenient` (metadata blocks are large + truncation-prone) | `conforms=false` + `failure{stage:"emit"}` (slot left unfilled, logged) |
| **Move-1 DATA-fill aggregation-spec** | 90s | `re.search` (small config JSON) | deterministic default spec (`window="today", group_by="load_group", subset=null`) |

---

## Layer 1a — storytelling router (`layers/layer1a/`) — UNCHANGED BY THE MORPH

> The payload-morph is an **intra-card OUTPUT-shape** change at Layer 2; 1a never emits a card payload. Verified against `pipeline_v47/pipeline.py:route_l1` — pure prompt→`{page, metric, intent}` + per-card story, no card-payload coupling, nothing for the morph to touch. Carried forward verbatim.

Files: `prompt_system.txt`, `db_reads.py`, `user_builder.py`, `parser.py`, `output_schema.json`. Adapts `route_l1` but upgrades it from "router" to "storytelling router + per-card story" and carries the DB layout/size refs + the Step-0 partition through.

### (a) SYSTEM prompt (`prompt_system.txt`)

```
You are LAYER 1a, the STORYTELLING ROUTER of an EMS dashboard-composition pipeline. Your single
job is to choose the ONE page whose card set TELLS THE PROMPT'S STORY BEST, then write the
analytical story that page — and each of its cards — should tell for THIS specific prompt.

You are NOT an asset matcher and NOT a keyword matcher. A different layer (1b) resolves which
physical meter/asset the prompt is about; you must IGNORE asset identity entirely and route purely
on which page's ANALYTICAL NARRATIVE answers the prompt. Routing by keyword overlap is the most
common mistake: a page may NAME a metric in a card title yet be unable to TELL the story the prompt
asks (e.g. an overview lists 'voltage' but cannot narrate 'voltage SAGS over time'). Judge each
page only by whether its purpose + theme + card set can actually SERVE the prompt's analytical
question.

The PAGES are grouped by '## SHELL' (asset class). Each page block gives: page_key, title
[archetype], purpose (what it answers + the engineer triage scenario), theme (the 'X not Y'
analytical contrast it draws), answers (the questions it resolves), and its real card titles with
their analytical role. FIRST pick the SHELL/asset class the story lives in, THEN the ONE page whose
CARD SET best narrates the prompt.

WHAT YOU EMIT:
1. page_key — copied VERBATIM from the list. Never invent or normalize one.
2. metric — the dominant measured quantity the prompt is about
   (current | voltage | power | energy | thd | pf | frequency | temperature | …). Default 'power'.
3. intent — the analytical SHAPE: trend | distribution | snapshot | table | events. Default 'trend'.
4. story — ONE short paragraph: the page-level analytical narrative this page should tell for THIS
   prompt. Ground it in the page's theme (the 'X not Y' contrast) and its answers — it is the
   storyline, not a list of cards. State what question the page resolves and what a reader concludes.
5. cards[] — for EVERY card on the chosen page, a PER-CARD analytical story. For each card emit:
   - card_id (the integer id printed for the card — copy it exactly),
   - analytical_story — the prompt-specific angle THIS card contributes to the page story, wrt its
     own role/function. This is a NEW, prompt-specific story, DISTINCT from the static card details;
     say what THIS card reveals about the prompt that the others do not.
   - role_in_story — how the card serves the page narrative (lead/context/drill-down/evidence/…),
     grounded in its analytical_role.

RULES:
- Route on the STORY, never on asset identity or surface word overlap.
- Emit a per-card story for EVERY card listed on the chosen page — do not skip cards, do not invent
  cards that are not listed.
- A card's metric/intent comes from its role/purpose, not its title alone.
- Output STRICT valid JSON only — escape inner double-quotes, no literal newlines inside strings.

JSON only, exactly this shape:
{"page_key":"<exact>","metric":"","intent":"","story":"","cards":[{"card_id":0,"analytical_story":"","role_in_story":""}]}
```

If a re-run carries an avoid-context (kept ONLY for the rare frontend "this page was wrong" hint — V48 has no automatic reloop), append the V47 re-route clause verbatim:

```
RE-ROUTE — the page(s) listed below were rejected for this prompt. Choose a DIFFERENT page whose
cards can tell the SAME story for the SAME metric+intent. Keep metric and intent identical — only the
page changes.
```

### (b) USER-message template (`user_builder.py`) — context + cmd_catalog reads

Reads (all `status='live'`):
- `page_specs`: `select page_key, coalesce(title,''), coalesce(shell,''), coalesce(module,''), coalesce(purpose,''), coalesce(analytical_theme,''), coalesce(reusable_answers,''), coalesce(archetype,''), layout_primitive, grid_template_columns, grid_template_rows, layout_gap, layout_padding, layout_shape, render_shell from page_specs where status='live' order by shell, page_key` (the routing surface + the layout refs carried through to output `layout`).
- card titles + roles per page (the card-story seed) — bridge through `page_layout_cards`/`card_handling`, **never** `cards.page`:
  `select pl.page_key, c.id, c.title, coalesce(c.analytical_role,''), coalesce(c.card_purpose,'') from page_layout_cards pl join cards c on c.id=pl.card_id where pl.card_id is not null and c.status='live' group by … order by pl.page_key, pl.slot_order` (string_agg the per-card lines per page, capped like V47's `[:160]` per card line).

The user message text:

```
PAGES:

## SHELL: <shell>
- <page_key>  | <title>  [<archetype>]
    purpose: <purpose>
    theme: <analytical_theme>
    answers: <reusable_answers>
    cards:
      [<card_id>] <title> — role: <analytical_role>
      [<card_id>] <title> — role: <analytical_role>
      ...
## SHELL: <next shell>
...

PROMPT: '<verbatim prompt>'
JSON:
```

### (c) Deterministic carry-through after the AI (`parser.py` → `Layer1aOutput` §2)

The AI emits only `{page_key, metric, intent, story, cards:[{card_id, analytical_story, role_in_story}]}`. The parser then **deterministically** (not AI):
1. Validates `page_key ∈ live keys`; else substring-match else `keys[0]` (V47 fallback).
2. Joins `page_specs` → fills `page_title, shell, module, layout{layout_primitive, grid_template_columns, grid_template_rows, layout_gap, layout_padding, layout_shape, render_shell}` verbatim.
3. Per card, joins `page_layout_cards` → `slot{slot_order, cell, region, area, col_span, row_span, tab, combo_id, combo_role}` and `card_grid_size` → `size{viewport, width_px, height_px, size_source}` (`size_source="defaulted"` + `failures[]` log when no row — 29/145 lack one, ids 117–176 are the deferred gap).
4. Builds `interdependency_groups[]` **from the DB, not the AI**: read `card_link` (`where page_key=… and wired`), `cards.interdependency` prose ("Linked cards on this page"), `card_combo`/`card_combo_member`, `selection_dimension`; **UNION** the prose links with the structured `card_link` table (the documented gotcha — `card_link` ALONE orphans the lone time-bucket card); transitively connect; one group per connected component, `coupling[]` = the edge rows verbatim (`src_card, dst_card, dimension, link_type, src_effect, dst_effect, trigger, scope, bidirectional, wired`). Cards in no group are standalone. (OPEN, pending user — build-spec review fix #7: the Heatmap-Footer card 160 still detaches from `rtm_ctx` because partition is "UNCHANGED by the morph"; the `page_control.affects_cards` + combo-region co-membership fallback that would re-attach it is not yet wired.)

This matches `Layer1aOutput` (§2) exactly: AI fills `page_key/metric/intent/story/cards[].analytical_story/role_in_story`; deterministic code fills `layout/slot/size/interdependency_groups`. The `interdependency_groups[].group_id` seeds the identity chain Layer 2 consumes (group → `shared_context.$id` → atom `$ctx`).

### (d) Qwen call: `qwen(system, user, timeout=120, salvage=False)` (small JSON, `re.search`).

---

## Layer 1b — asset resolve + card-agnostic column basket (`layers/layer1b/`) — UNCHANGED BY THE MORPH

> Verified against `column_resolve.py:resolve_asset` + the `recipe_fields=None` path of `resolve_columns`: pure prompt→`{asset, candidate-list}` and prompt→`{feasible, probable[]}` real-column basket, no card-payload coupling. The basket becomes the INPUT to Layer 2's `data_instructions` recipe, but `resolve_columns`'s own output shape is untouched. Carried forward verbatim.

Files: `prompt_asset_system.txt`, `prompt_basket_system.txt`, `db_reads.py`, `user_builder.py`, `parser.py`, `output_schema.json`. Runs in parallel with 1a. **Two AI calls** (asset, then basket), as in V47, but the basket is **card-agnostic** (no `recipe_fields`).

### 1b-(i) Asset resolver — SYSTEM (`prompt_asset_system.txt`)

Ported verbatim from `ASSET_SYSTEM` (`column_resolve.py:106-138`) — it is already pure-AI confident/ambiguous/empty with class-from-subject inference and the 6-class discriminator:

```
You are the L1b ASSET RESOLVER for an energy-monitoring system. Identify the EXACT meter(s) the user
means from the lt_mfm registry, returning their registry id(s).
INPUT: a candidate list (one per line, 'id<TAB>name<TAB>class<TAB>load_group<TAB>flag') — class is the
equipment class from the registry (LT Panel | Transformer | HT Panel | UPS | APFC | Diesel Generator);
flag='NO-DATA' means that meter has no readings table — plus the full user PROMPT and the extracted
ASSET MENTION.
HOW TO MATCH (semantic, not literal):
- The registry names equipment differently than people speak. Resolve by what the asset IS, not by
  string overlap: equipment class (transformer / AHU / incomer / DG / feeder / panel / VCB),
  unit/feeder number, role and load_group. Examples of the SAME asset under different names:
  'Transformer 1' = 'Incomer-1 (TF-01)'; 'AHU 5' = 'AHU-5'; 'DG 2' = 'Diesel Generator 2'. A high
  string overlap with the WRONG unit number is a WRONG match — the discriminating number/role must agree.
- USE THE CLASS COLUMN as the class discriminator (do NOT infer class from the name string): e.g.
  'HT transformer' must be class=Transformer, NOT class=HT Panel. Prefer the candidate whose class AND
  unit/role both agree with the mention; avoid a NO-DATA meter unless the prompt explicitly names it.
- INFER THE CLASS FROM THE SUBJECT/METRIC, even when the class word is not spoken: battery backup /
  autonomy / backup time → UPS; fuel level / genset / diesel / DG running → Diesel Generator; tap
  position / winding / oil temperature / HV-LV → Transformer; power-factor correction / capacitor bank
  / kVAR comp → APFC; 11kV / HV incomer → HT Panel; feeder / outgoing / busbar / LT incomer → LT Panel.
  A prompt almost ALWAYS implies at least one class — treat 'no class at all' as the rare exception.
OUTPUT — JSON only. DECIDE confidence:
- CONFIDENT (one meter): if the prompt pins exactly ONE meter — its class AND a unit number / feeder /
  role — return {"ids":[<id>],"confident":true}. Several ids with confident:true ONLY when the prompt
  clearly names several assets or one unambiguous group.
- AMBIGUOUS (the DEFAULT when no single unit is pinned): a bare or implied class with NO unit/role
  discriminator (e.g. 'UPS', 'a transformer', 'battery autonomy'), OR several meters equally plausible,
  OR you are not sure which ONE. DO NOT GUESS an arbitrary instance, and DO NOT return an empty list —
  return {"confident":false,"candidates":[<ALL plausible meter ids of the inferred class>]}.
- EMPTY only as a last resort: {"ids":[],"confident":true} ONLY when the prompt references no asset and
  no equipment class whatsoever.
Respond with ONLY this JSON object: {"ids":[...],"confident":true|false,"candidates":[...]}
```

USER template (reads `lt_panels_db`, the load-bearing index contract `[id,name,table_name,mfm_type_id,load_group,class]`):
```
CANDIDATES (id<TAB>name<TAB>class<TAB>load_group<TAB>flag):
<id>\t<name>\t<class>\t<load_group>\t<NO-DATA if table_name empty>
...

PROMPT: '<prompt>'
ASSET MENTION: '<mention>'
JSON:
```
SQL: `select m.id, m.name, m.table_name, m.mfm_type_id, coalesce(m.load_group,''), coalesce(t.name,'') from lt_mfm m left join lt_mfm_type t on t.id=m.mfm_type_id order by m.id`.

**Caller wiring (`parser.py`):** if `env.PIPELINE_ASSET_ID` is set → skip the call, pin that `lt_mfm.id`, emit `asset.how="user-choice"`. Else confident → `asset.how="AI"`, `candidate_list=[]`. Ambiguous → `asset=null`, fill `candidate_list[]` ({mfm_id, name, class, load_group, panel_id, has_data}) → orchestrator sets `phase="awaiting_asset_choice"`, writes `asset_choice.json`, returns (frontend AssetPicker re-runs with `PIPELINE_ASSET_ID`). Mirrors V47.

### 1b-(ii) Column basket — SYSTEM (`prompt_basket_system.txt`)

Adapts `SYSTEM` (`column_resolve.py:199-223`) but **drops the per-card recipe block** so the basket is card-agnostic and GENEROUS — exactly the V47 "breathing-space probable list, with no `recipe_fields`":

```
You are the L1b COLUMN-BASKET RESOLVER. From the resolved asset's REAL column dictionary (and the
derived/const metrics computable from it), assemble the COMPLETE basket of every table+column that
could PLAUSIBLY answer this prompt. The basket is CARD-AGNOSTIC and PROMPT-DRIVEN: you do NOT know
which cards or page will use it, so be GENEROUS — cover every angle the prompt and obvious follow-ups
could need. This basket is the single column vocabulary every downstream card draws from.

Bind ONLY real columns — every raw column name you return must be copied VERBATIM from a column_name
in the dictionary. NEVER invent, guess, or normalize a name; if no real column serves a concept, put
it in `unmappable` (the pipeline reports the gap honestly — a fabricated column is worse than a
missing one). For DERIVED concepts (event COUNTS, imbalances, deviations, efficiencies) return the
derived metric KEY and its real BASE columns — never a column named after the metric. For CONST
references (nameplate/rated/threshold) return the nameplate key with kind='const'.

INPUT: the PROMPT, the resolved ASSET (name + class + table), one line per column
('column_name | label | kind | unit | has_data(Y/N)'), the available DERIVED METRICS (with base
columns), and the NAMEPLATE CONSTANTS.

RETURN one entry per column you admit, with:
- table  : the lt_panels table that owns it (for derived, the table whose base_columns satisfy the
           formula; for const, '' ).
- column : the real verbatim column_name (raw) | derived_metrics.metric_key (derived) |
           nameplate key (const).
- metric : the normalized metric concept this column binds (the join key cards match recipe fields on).
- label, unit.
- kind   : raw | derived | const | event.
- has_data: Y/N.
- For PROBABLE (best-first) entries also give rank (1-based) and why (one short reason it fits).
  feasible-only entries (could-serve but not ranked) carry rank=null, why=null.
- base_columns: for kind=derived, the real lt_panels columns the formula reads.

Be GENEROUS within feasibility: include R/Y/B phases, per-feeder variants, avg/min/max statistics,
today/this-week forms — so any card and any follow-up prompt has breathing room. But EVERY column
must be real and must genuinely serve the prompt.

JSON only:
{"columns":[{"table":"","column":"","metric":"","label":"","unit":"","kind":"raw|derived|const|event",
"has_data":true,"rank":1,"why":"","base_columns":[]}],
"unmappable":[{"concept":"","reason":""}]}
```

USER template — reads:
- column dictionary: `select column_name,name,kind,coalesce(unit,'') from lt_parameter where mfm_type_id=<type> order by column_name` (lt_panels_db); has-data via `latest_nonnull(table)` against `lt_panels`.
- derivable metrics: `_derivable_metrics` over `derived_metrics` (cmd_catalog) whose `base_columns` are ALL in this dictionary — **reconcile** drift (e.g. `active_energy_today_kwh` → live `active_energy_import_kwh`) before listing; mismatches go to `unmappable`/log.
- nameplate consts: `select scope,key,value,unit from nameplate_config` (cmd_catalog).

```
PROMPT: '<prompt>'
ASSET: <name>  (class=<class>, table=<table_name>)

COLUMNS (column_name | label | kind | unit | has_data):
<col> | <label> | <kind> | <unit> | Y
...

DERIVED METRICS available (compute FROM base columns — resolve base columns, never invent a metric column):
  <metric_key> (<unit>) — <label> [base columns: <a, b>]
  ...

NAMEPLATE CONSTANTS (kind=const):
  <scope>/<key> = <value> <unit>
  ...
JSON:
```

**Anti-hallucination harness (carry verbatim from V47, deterministic post-LLM):** keep only `column ∈ real`; drop → `layer35_correct` (fuzzy `difflib.get_close_matches` cutoff 0.82 + `_same_family` gate, else `_retry_one` LLM at 0.72) → corrected real column (rank 99) or `unmappable`. `_same_family` rejects cross-metric swaps (`voltage_neutral→voltage_avg`). The parser then fills `column_basket.tables` (distinct tables) and merges the asset block from 1b-(i) → emits `Layer1bOutput` (§3).

### (d) Qwen calls: asset `qwen(…, timeout=60, salvage=False)`; basket `qwen(…, timeout=120, salvage=True)` (probable lists truncate).

---

## Layer 2 — per-card swap + MORPH-EMIT `{ exact_metadata, data_instructions }` (`layers/layer2/`) — REWRITTEN FOR THE MORPH

> **This is the layer the morph changes.** Layer 2's per-card output is now `{ exact_metadata, data_instructions }`: the AI authors the FINISHED, byte-identical METADATA block (the per-card one-payload METADATA tier) AND emits a parseable DATA-fill recipe; the helper/worker parses the recipe and fills the DATA tier, owning live state + interactivity + interdependency. The keep/swap gate is unchanged; the EMIT half is fully rewritten.

Files: `prompt_system.txt`, `partition.py` (deterministic Step-0, consumes 1a's `interdependency_groups`), `worker/` (Move-1 builders, ported from `ems_aggregate.py`/`panel_resolve.py`/`l6_2.py` — the DATA-fill helpers), `move1_spec_prompt.txt` (below), `user_builder.py`, `parser.py`, `stitcher.py`, `output_schema.json`. One AI fan-out call per card (parallel). Adapts `layer2_swap.py:SYSTEM` for the keep/swap gate and **replaces** the V47 L5 frame-emit with the morph `{exact_metadata, data_instructions}` emit, and adds the **1a-story constraint** + **no-dup**.

### (a) SYSTEM prompt (`prompt_system.txt`)

```
You are LAYER 2 of a dashboard-composition pipeline, deciding ONE card at a time (you run in parallel,
once per card). Layer 1a already chose the page, wrote the page STORY, and assigned THIS card its
analytical story; Layer 1b resolved the asset and the column basket. The page, the slot positions, and
the sizes are FIXED — you never change them. There is NO reloop and NO re-route: your verdict is
strictly KEEP or SWAP for this slot, then you EMIT this card's ONE PAYLOAD as two halves.

THE CARD CONTRACT YOU EMIT INTO (read this first):
A card is a pure function of ONE flat payload {data + metadata}, every key EXACTLY once, no second
'root', ZERO design-system chrome. Two tiers ride that payload and you own only ONE of them:
- METADATA tier — labels, units, colours, rosters, ORDER, thresholds, contracts, badges, tabs. This
  is the AI-morphable half. YOU AUTHOR IT, finished and exact, as `exact_metadata`.
- DATA tier — the numbers + initial interaction state. A deterministic helper fills it. YOU DO NOT
  WRITE DATA; you only emit the RECIPE for it, as `data_instructions`.
- DESIGN-SYSTEM CHROME — pixel geometry, fonts, Card/SegmentedControl markup, functions, ReactNode,
  3D objects, onClick handlers. NEVER on the payload. NEVER emitted by you.

PART 1 — KEEP / SWAP. Decide whether the card now in this slot is the right one to tell its assigned
analytical story, or whether one of this slot's SWAP CANDIDATES (same footprint, ±15% in width AND
height) tells that story clearly better and should be swapped in.

SCOPE: you judge RELEVANCE-TO-THE-STORY + COHERENCE only. The decisive test is the card's STORY ANGLE
from Layer 1a — does the card's analytical job match the angle this slot was assigned? You do NOT
judge whether the data exists or the query will succeed (the data_instructions + the helper handle
fillability).

RULES — be CONSERVATIVE. On a page 1a chose well, KEEP is the default; 0 swaps is a correct, healthy
answer. A swap is honored ONLY if ALL THREE hold:
1. STORY-ANGLE RELEVANCE — the candidate's role/purpose/visualization serves THIS slot's assigned
   analytical_story (from 1a) MORE DIRECTLY than the current card, and you can quote the specific
   word/phrase from the story angle that proves it. A tie or a vague 'better fit' is a KEEP.
2. LISTED — the candidate is one of THIS slot's printed SWAP CANDIDATES (the only size-equivalent,
   render_real options). A card listed elsewhere or not at all is NOT a valid target.
3. NO DUPLICATE — the swap target must be NEW to the page. NEVER swap to a card already on the page,
   already in 1a's TEMPLATE CARD SET (template_card_ids), or already chosen as another slot's target.
   1a's chosen cards are sacred — a swap may never duplicate one.

INTERDEPENDENCY: if this card prints link_type master-selector / shared-selection / cross-highlight it
is COUPLED — it may be swapped ONLY as an all-or-nothing COMBO, naming every linked partner's matching
swap in `cascade`; if any partner has no valid listed candidate, KEEP the whole set.

Set action='swap' ONLY when all three rules hold AND confidence >= 0.9 AND `criterion` NAMES the
concrete story-angle word the candidate serves better (vague criteria — 'better','more relevant',
'nicer','good fit' — score below 0.9 and become a KEEP).

PART 2 — MORPH-EMIT. For the FINAL card (post-swap) emit its ONE payload as the two halves below. The
card's exact METADATA SHAPE is given to you as `metadata_shape` (the per-card one-payload METADATA
tier — e.g. an RTM HeatmapViewModel/RailViewModel metadata block, or an HPQ HpqPresentation.<card>
block). Author EVERY key of that shape.

== exact_metadata (the FINISHED METADATA block — you author it exact) ==
Author the COMPLETE METADATA tier for this card, one key per `metadata_shape` field, BYTE-IDENTICAL to
the card's static-config default UNLESS the prompt + 1a story justify a morph. Rules:
- BYTE-IDENTICAL DEFAULT — copy each default verbatim from the card's STATIC CONFIG block shown to you
  (titles, metricTabs, statusColors, statusLegend, units, descriptors, selectionColors, bandThresholds,
  HPQ tiles/segments/columns/vocab/palette, …). The resting render must not move; only a deliberate
  morph moves a pixel.
- MORPH PER PROMPT + STORY — re-title, re-order, re-roster, re-threshold, re-label, retint, or toggle a
  tab/badge/legend ONLY to serve the 1a story angle (e.g. lead with the metric the prompt asks about,
  reorder tabs to put 'voltage' first, tighten a threshold the prompt flags). Every morph must be
  traceable to a word in the page story or this card's story angle.
- EVERY METADATA FIELD IS REQUIRED AND ALWAYS POPULATED — never omit a key; an omitted key is a render
  regression. No nulls where the shape needs a value.
- NEW RENDERERS OPT-IN DEFAULT-OFF — any toggle a renderer reads (e.g. showLegend) defaults to its
  resting value (false), never on, unless the prompt explicitly asks for it.
- ZERO CHROME — no pixel geometry, no fonts, no Card/grid markup, no functions. Metadata is data-shaped
  scalars/enums/arrays/hex-strings only.
- The TWO DUAL-OWNED SLOTS ('AI-default, data-overridable') — author your DEFAULT and mark it: RTM
  `sectionContracts` ({incomers:2700,ups:1500,bpdb:600,hhf:600}) and HPQ signature `spokes`/`selectedName`.
  The worker MAY overwrite these from a live frame; you still emit the default so the resting render is
  byte-identical.

== data_instructions (the parseable DATA-fill RECIPE — the helper fills the DATA from it) ==
Emit a recipe the helper parses to FILL the DATA tier — NOT data, NOT SQL, NOT numbers. It is a
RESOLVED recipe: one resolved field per data slot, plus the per-card fill envelope. Bind every field
to a REAL column from the COLUMN BASKET by the field's `metric` — never bind every tile to the same
column (the 'every tile = active_power' bug). Shape:
- payload_shape — which DATA tier to fill (the card's payload_shape).
- orientation — time | entity | snapshot (the row shape).
- entity_dim / selection_dim — what each row/series IS and what selection drives it.
- selection_role — the card's interdependency role (both|produces|consumes|emits|none) — provisional.
- binding — { asset_id, table, ts_col, panel_id, nameplate_scope } (from 1b's resolved asset). Null for a
  pure-$ctx group atom (DATA from the shared buffer) or a pure-const card. (There is NO top-level `source`
  on data_instructions — fill source is PER-FIELD `fields[].source`; do NOT hardcode 'mock'.)
- window — { lookback, sampling, time_mode } from the card controls (re-slice = re-bind only).
- fields[] — one resolved field per data slot, each:
    { slot, kind(raw|derived|const|text|event), role(series|kpi|column|line|cell|tile|row|spoke),
      metric, column, label, unit, agg(avg|last|sum|count|derived), source(live|test-db|const|$ctx),
      value?(const only), base_columns?/sql_fragment?/nameplate_refs?(derived only), edge?(event only),
      filters_table, has_data }
  Rules per kind:
  - raw → bind `column` to the real basket column for this field's metric; agg avg/last/sum.
  - derived → `column` is the derived metric_key; carry base_columns + (if known) sql_fragment; agg=derived.
  - event → `column` is the boolean *_event_active flag; agg=count; edge='rising'.
  - const → a baked literal (threshold/limit line / status placeholder); set value, source='const',
    NEVER a column. (IEEE_519 limit, rated/contracted lines, etc.)
  - text → a label/narrative column; bind the real column or mark source per controls.
- DO NOT put metadata in data_instructions — statusColors/bandThresholds/metricTabs/IEEE limit
  THRESHOLD VALUES that are chrome belong in exact_metadata, not here. (A const LIMIT LINE the chart
  PLOTS is a data field; the threshold colour/legend is metadata.)

DATA-RESIDENCE — set `$ctx` (told to you as is_group_card). There is NO emit_mode/atom-vs-frame branch:
the SAME output shape carries EVERY card; `$ctx` only selects where the DATA lives, and exact_metadata
is authored in full EITHER way.
- GROUP card → set `$ctx` to the page's shared_context.$id and emit a LEAN ATOM: data_instructions holds
  NO baked data — its `source` points at the shared buffer (the $ctx buffer reference) and each field
  carries `selection_role` (produces|consumes|emits|both). The atom STILL carries its OWN FULL
  exact_metadata block (that IS the morphability) AND its own data_instructions.fields[] (so the helper
  knows which slots of the shared buffer to project). Interaction seeds you reference must exist in
  shared_context.interaction. FUNCTIONS NEVER travel.
- STANDALONE card → leave `$ctx` null; data_instructions.source is live/test-db and binds to the resolved
  asset/table; the helper fills the DATA tier from the live ws/mfm frame OR the test-DB fixture in the
  identical Snapshot shape.

If you cannot serve the card (no real column for a required field, unwired component, no data), set
conforms=false and fill `failure{stage,reason,detail}` — the card is LOGGED and left unfilled. NEVER
fabricate a column, a number, a metadata key, or a frame field.

Output STRICT valid JSON only matching the Layer2CardOutput schema (below). Escape inner quotes; no
literal newlines in strings.
```

### (b) USER-message template (`user_builder.py`) — the `Layer2CardInput` (§4) assembled deterministically

Per card, interpolated from: 1a's `story.page_story` + this card's `analytical_story` + `template_card_ids`; 1b's `asset` + `column_basket`; the card's `catalog_row` (all keyed by `card_id`); and (group cards only) `shared_ctx_ref`. **New for the morph:** the `metadata_shape` (the per-card one-payload METADATA tier) and its **STATIC-CONFIG defaults** are read and shown so the AI authors byte-identical exact_metadata. cmd_catalog reads:
- `card_handling` → `handling_class, resolver_scope, payload_family, backend_strategy` (backend_strategy + payload_family are REFERENCE-ONLY — payload_family is the surviving DATA-FILL dialect, NOT a Layer-2 output).
- `card_data_recipe` → `payload_shape` (normalized to the 10 `payload_shapes`), `orientation, entity_dim, selection_dim, selection_role`, `coalesce(reconciled_fields, fields)` as `fields[]` (the unresolved recipe the data_instructions resolves). (OPEN, pending user — build-spec review fix #9: live `payload_shape` also carries `composite` (combo groups — must NOT collapse to one shape) and `sld`, which are NOT among the 10; their mapping is unresolved.)
- `card_contract_binding ⋈ contract_components` → `component, host_cmd_component, canonical_shape`, and **`payload_schema_json`** = the **metadata_shape** (the per-card one-payload METADATA tier the AI authors into — e.g. `RealTimeHeatmapSection` = `{metric, buckets[...], contractKw, selectedSampleIndex}`; for RTM/HPQ this is the `HeatmapViewModel`/`RailViewModel`/`HpqPresentation.<card>` metadata keys).
- `card_controls` → `time_mode, time_options, sampling_options, segmented_tabs, defaults` (the tabs/labels/order/defaults the AI authors into exact_metadata + the `window` of data_instructions).
- `contract_hardcodes` + `contract_capabilities` → the **STATIC-CONFIG defaults** (byte-identical default source: titles, status palettes, legends, units, descriptors, thresholds, vocab) shown verbatim so exact_metadata starts byte-identical.
- `card_feasibility` → `{family, verdict, required_topology, required_mesh, reason}`.
- `swap_candidates[]` from `card_grid_size` ±15% (`size_candidates`), off-page, `card_feasibility.verdict='render_real'`, **NOT in `template_card_ids`**, max 6 closest — each with `analytical_role, card_purpose, visualization`.

```
RUN: <run_id>   CARD: <card_id>   PAGE: <page_key>
GROUP CARD: <true|false>   GROUP: <group_id or none>

PAGE STORY (Layer 1a): <story.page_story>
THIS CARD'S STORY ANGLE (Layer 1a): <story.analytical_story>   [your morph + a swap target MUST serve this angle]
METRIC: <metric>   INTENT: <intent>
TEMPLATE CARD SET (1a's chosen ids — NEVER swap to one of these): <template_card_ids>

ASSET (Layer 1b): <name> (class=<class>, table=<table>, panel_id=<panel_id>, nameplate_scope=<scope>)
COLUMN BASKET (column | metric | kind | unit | has_data | rank):
  <col> | <metric> | raw | A | Y | 1
  ...

THIS CARD (cmd_catalog row):
  title: <title>
  handling_class: <handling_class>   resolver_scope: <resolver_scope>   payload_family: <payload_family> [REF-ONLY: DATA-fill dialect]
  contract: component=<component> host_cmd_component=<host_cmd_component> shape=<canonical_shape>
  recipe (unresolved — resolve into data_instructions.fields): shape=<payload_shape> orientation=<orientation>
    entity_dim=<entity_dim> selection_dim=<selection_dim> fields=[{kind,role,label,metric,unit}, ...]
  controls: time_mode=<…> sampling_options=<…> segmented_tabs=<…> defaults=<…>
  capabilities (metric:supported): kw:true, kvar:true, ...
  feasibility: verdict=<verdict> required_topology=<…> reason=<…>
  link_type: <…>   interdependency: <…>

METADATA SHAPE (author EVERY key as exact_metadata — this is the card's one-payload METADATA tier):
  <payload_schema_json metadata keys, e.g. for RTM heatmap:>
  { title, metricTabs[], metricAxisLabels, statusColors, statusLegend[], units{power,percent,reactive},
    descriptors{supplied,contract}, selectionColors{highlight,rowLabel}, bandThresholds{stops,divisors},
    sectionContracts  [AI-default, data-overridable] }

STATIC-CONFIG DEFAULTS (byte-identical default source — copy verbatim unless the story justifies a morph):
  title = "Real Time Monitoring"
  metricTabs = [{all:"All Metrics"},{kw:"kW"},{kvar:"kVAr"},{pf:"PF"},{voltage:"Voltage"},{current:"Amps"},{iUnbalance:"I Unbalance"}]
  statusColors = {low:…, normal:…, moderate:…, high:…, critical:…}
  units = {power:"kW", percent:"%", reactive:"kVAr"}
  bandThresholds.divisors = {kw:250, kvar:150, current:400, iUnbalance:15, voltageNominal:415, voltageSlope:4}
  sectionContracts = {incomers:2700, ups:1500, bpdb:600, hhf:600}   [DUAL-OWNED]
  ... (all keys of metadata_shape, verbatim from contract_hardcodes/contract_capabilities)

SWAP CANDIDATES (±15% size, render_real, off-page, not in template) — closest <n>:
  - cand <card_id> "<title>" [<page_key>] <w>x<h> | role:<analytical_role> | purpose:<card_purpose> | viz:<visualization>
  ...

[group cards only]
SHARED CONTEXT REF (read-only; built once in Move 1; data_instructions.source points HERE, never copies it):
  $id: <ctx $id>   buffer_keys: [history, ...]   interaction_seeds: [cursor, selection, metric, ...]
  Your atom holds NO data — data_instructions.fields[].source = "$ctx.<key>"; binds/selection_role from
  interaction_seeds. You STILL author your own full exact_metadata block.

Decide keep/swap (rules 1-3 + interdependency + confidence>=0.9 + named criterion), then MORPH-EMIT:
author exact_metadata (byte-identical default, morph per story) + data_instructions (resolved recipe,
real basket columns, fill envelope). JSON:
```

### (c) Output schema — `Layer2CardOutput` (§5) — the morph shape

The AI emits one object per card. The keep/swap block is unchanged; the emit half is the morph `{ exact_metadata, data_instructions }`:

```jsonc
{
  "card_id": 0,
  "$ctx": null,                                 // null=STANDALONE (DATA filled inline); "<ctx-id>"=GROUP member (DATA from shared_context.$id buffer). Selects DATA-residence only; exact_metadata rides on the card either way. NO atom/frame branch.
  "render_slot": "",                            // where the card mounts (page_layout_cards.cell/region + combo_role)
  "analytical_story": "",                       // the AI's own, validated against 1a's angle
  "swap_decision": {                            // PART 1 — unchanged gate
    "action": "keep | swap",
    "origin": "kept",                           // kept | swapped | must_swap — resolved by the deterministic gate
    "swap_to_id": null, "swap_to_title": "",
    "confidence": 0.0,
    "criterion": "",                            // MUST name the concrete story-angle word
    "reason": "",
    "cascade": []                               // all-or-nothing combo partners (coupled cards)
  },

  // PART 2 — THE MORPH: the FINAL card's ONE payload, authored as two halves.
  "exact_metadata": {                           // the FINISHED METADATA tier — every metadata_shape key,
    // ... one key per metadata_shape field ...  // byte-identical default unless the story justifies a morph.
    // RTM heatmap example:
    "title": "Real Time Monitoring",
    "metricTabs": [/* ... */],
    "statusColors": {/* ... */}, "statusLegend": [/* ... */],
    "units": {"power":"kW","percent":"%","reactive":"kVAr"},
    "descriptors": {"supplied":"supplied","contract":"contract"},
    "selectionColors": {"highlight":"#…","rowLabel":"#…"},
    "bandThresholds": {"stops": {/* ... */}, "divisors": {"kw":250,"kvar":150,"current":400,"iUnbalance":15,"voltageNominal":415,"voltageSlope":4}},
    "sectionContracts": {"incomers":2700,"ups":1500,"bpdb":600,"hhf":600},   // AI-default, data-overridable
    "_morphed": ["metricTabs"]                  // OPTIONAL: which keys were morphed off-default (audit/log)
  },

  "data_instructions": {                        // the parseable DATA-fill RECIPE — helper fills DATA from it
    "payload_shape": "HeatmapPayload",
    "orientation": "entity",                    // time | entity | snapshot
    "entity_dim": "feeder", "selection_dim": "metric",
    "selection_role": null,                     // both|produces|consumes|emits|none (provisional) — NO top-level `source` here; fill source is per-field
    "binding": { "asset_id": 115, "table": "mfm_lt_115", "ts_col": "ts", "panel_id": "...", "nameplate_scope": "default" },
    "window": { "lookback": "today", "sampling": "2s", "time_mode": "live" },
    "fields": [
      { "slot": "kw", "kind": "raw", "role": "cell", "metric": "active_power_total_kw",
        "column": "active_power_total_kw", "label": "Feeder kW", "unit": "kW",
        "agg": "avg", "source": "live", "filters_table": false, "has_data": true },
      { "slot": "iUnbalance", "kind": "derived", "role": "cell", "metric": "iUnbalance",
        "column": "iUnbalance", "label": "Current Unbalance %", "unit": "%", "agg": "derived",
        "base_columns": ["current_r","current_y","current_b"],
        "sql_fragment": "…", "nameplate_refs": [], "source": "live", "has_data": true },
      { "slot": "status", "kind": "const", "role": "cell", "metric": "status",
        "label": "Status", "value": null, "source": "const" }
    ]
  },

  // GROUP member ($ctx set): each data_instructions.fields[].source becomes the shared-buffer reference ($ctx) + carries selection_role;
  // exact_metadata is STILL fully authored on the atom.
  // OPEN (pending user): the exact $ctx-source form — dotted "$ctx.<key>" vs bare "$ctx" + sibling buffer_key — is
  // unresolved across CONTRACTS (bare enum) and SIGNATURES/PROMPTS (dotted); align once the user decides.

  "controls": { /* time_mode/segmented defaults echoed for the helper if needed */ },
  "conforms": true,
  "failure": null                               // {stage,reason,detail} when conforms=false (slot left unfilled, logged)
}
```

The deterministic gate (`parser.py`, ported from `layer2_swap.run`) then:
1. **Keep/swap gate (unchanged):** honors a swap ONLY if `action='swap' AND confidence>=0.9 AND _criterion_ok (rejects the VAGUE set) AND target in the offered pool AND not a duplicate of slot_set ∪ template_card_ids ∪ chosen`, with all-or-nothing `cascade` integrity. Resolves `swap_decision.origin` (kept/swapped/must_swap).
2. **exact_metadata gate (new):** every `metadata_shape` key is present (no omissions); each defaulted key is byte-identical to the STATIC-CONFIG default unless flagged in `_morphed`; any new-renderer toggle is default-OFF; reject + log if any chrome (function string / pixel geometry) leaked in.
3. **data_instructions gate (new):** every `fields[].column` ∈ the 1b basket (or `kind=const` with a `value`); a **SAFE column-override** snaps each binding to its recipe-metric column only when that metric is unique on the card (guards "every tile = active_power"); event fields carry `edge`, derived carry `base_columns`; `source ∈ {live,test-db,const,$ctx}` (never literal 'mock'; `$ctx` only on group-atom fields).
4. **stitcher (`stitcher.py`):** hands the worker the `data_instructions` to FILL the DATA tier, then merges `{...exact_metadata, ...filled_data}` into ONE flat payload per card — every key once, no `root` (the `HOST_RENDERABLE` backstop guarantees `host_cmd_component` is mountable; `collapse_combos` ensures no combo member is emitted twice).

### (d) Qwen call: `qwen(system, user, timeout=120, salvage=True)` (exact_metadata blocks are large + truncation-prone).

---

## Move-1 worker AI call — DATA-fill aggregation-spec (`layers/layer2/worker/spec_prompt.txt`)

Fires ONCE per interdependency group (and once per aggregate standalone card, `handling_class ∈ {panel_aggregate, topology_sld}`) BEFORE the per-card fan-out. **This call authors a DATA-fill spec only — it NEVER touches exact_metadata (the per-card AI owns metadata).** The AI authors a SMALL spec; the deterministic worker (`aggregate_shape` / the `ems_aggregate` builders — the DATA-fill helpers) does the labour, filling the DATA tier in the same Snapshot shape a live frame would. It upgrades V47's `l6_2.card_config` from a hardcoded config to an AI seam. **The AI never authors SQL or metadata** — only strategy/window/grouping/subset/which derived fields + the shared-buffer seeds.

### (a) SYSTEM prompt (`spec_prompt.txt`)

```
You are the V48 DATA-FILL AGGREGATION-SPEC author. A panel/aggregate card (or an interdependent
group's shared buffer) needs DERIVED DATA-tier values the database does not store raw — loss %,
share %, efficiency, a multi-layer sankey, per-feeder demand, a windowed history buffer. You author
ONLY the DATA-fill recipe knobs; you do NOT author labels/units/colours/order (that METADATA is the
per-card layer's job, emitted separately as exact_metadata), you do NOT write SQL, and you do NOT
compute anything. A deterministic worker reads your spec, queries the raw lt_panels rows for the
resolved panel's members, and fills the DATA tier (the same Snapshot shape a live frame produces, so
live and test-DB are interchangeable). Your only job is to set the prompt-driven knobs the worker
cannot infer alone.

INPUT: the PROMPT, the resolved PANEL (mfm_id + label), the target COMPONENT (its frozen contract
component + payload shape), the available windows, the panel's MEMBERS (sources/consumers with class +
load_group), and — for an interdependent group — the shared_context buffer(s) to seed.

DECIDE:
- window — the time window the prompt implies: today | this_week | this_month (default today).
- group_by — how to group consumers for the breakdown: load_group (default) | feeder | source_group.
- subset — null (all members), or a named member/feeder/group the prompt focuses on (drill-down).
- metrics — which DERIVED DATA fields the prompt asks to foreground (e.g. loss_pct, share_pct,
  efficiency_pct, demand peaks, sankey). Leave broad unless the prompt narrows it.
- For a SHARED CONTEXT buffer also set: buffer key(s), sample_count, sampling, and the interaction
  seeds (cursor/selection/metric/scalar) the host owns — drawn from the card controls, never invented.
  These are DATA-tier INITIAL interaction state (hook-seeded), NOT metadata. FUNCTIONS NEVER appear in
  the spec; only plain scalar/enum seeds.

Ground every choice in the prompt + the listed members/controls. If the prompt gives no signal for a
knob, use its default. Author NOTHING the worker can't execute against real rows, and NOTHING that
belongs to exact_metadata (labels/units/colours/thresholds are not yours).

JSON only:
{"window":"today","group_by":"load_group","subset":null,"metrics":["loss_pct","share_pct","sankey"],
"buffers":[{"key":"history","sample_count":12,"sampling":"2s"}],
"interaction_seeds":{"cursor":"latest","selection":{"kind":"panel"},"metric":"all"}}
```

### (b) USER template (`user_builder.py`) — reads

- panel members via the verified topology gotcha (`panel_resolve.panel_members`): `WHERE to_mfm=<panel>`, `edge_kind='outgoing'`→source (incomers — Transformer 1/2, solar), `edge_kind='incoming'` (minus `from_name ILIKE 'spare%'`)→consumer (UPS/BPDB/HHF), enriched from `lt_mfm` (panel_id = the time-series WHERE key, NOT table — PCC 1A=174 and 1B=185 share `mfm_lt_115`) + capacity from `lt_config_value`.
- target component + shape: `card_component(card_id)` over `card_contract_binding` + the card's `payload_shape`.
- controls/seeds: `card_controls.defaults`/`segmented_tabs` for the group (e.g. RTM `sample_count=12, tick_interval_ms=2000`).

```
PROMPT: '<prompt>'
PANEL: <panel_label> (mfm_id=<panel_mfm_id>)
COMPONENT: <component>   PAYLOAD SHAPE: <payload_shape>
WINDOWS: today | this_week | this_month

MEMBERS:
  SOURCES (incomers): <name> [class=<class>, cap_kw=<…>]; ...
  CONSUMERS (feeders): <name> [class=<class>, load_group=<…>, cap_kw=<…>]; ...

[group only] SHARED CONTEXT to seed: buffers=[history], controls defaults=<…>, interaction dims=<card_link/selection_dimension>
JSON:
```

### (c) Output / downstream

The AI emits the small DATA-fill config `{window, group_by, subset, metrics, buffers, interaction_seeds}`. The deterministic worker (`aggregate_shape(card_id, panel_mfm_id, window, prompt, focus)`) runs the matching `ems_aggregate` builder (`energy_distribution`/`panel_overview`/`demand_profile`/`current_distribution`/`feeder_pq`/`other_panels_events`), reusing EMS semantics verbatim (energy = `active_energy_import_kwh value@end − value@start` via two at-or-before probes — NOT max−min; `now_expr`=`max(ts)` anchor; consumers grouped by `load_group`; `capacity_kwh = rated_kw × window_hours`), `validate()`s it (real structure + non-null data), and produces either:
- the standalone aggregate **DATA tier** (the `widgets{…}` or flat Snapshot the FE mapper consumes — the worker fills DATA, the per-card AI's `exact_metadata` supplies the chrome; stitcher merges), or
- the group's `SharedContext` (§6: `$id, asset, buffers[{key, history:HistorySample[], range, sampling, socket_owner:true}], interaction{cursor, selection, metric, scalars, couplings (from card_link/selection_dimension)}, config, apiExtras`).

Honest-degrade: unwired component → `(None,False,why)` → `conforms=false` + `failures[stage:"aggregate"|"shared_context"]`, no reloop; panel-TOTAL cards correctly fall back to single-asset L6 (the panel's own meter IS the total — only per-FEEDER breakdowns need a builder). The worker also owns live re-slice at the reslice endpoint (`/reslice`, the EMS `sendSelectedPeriod`/`sendSelectedPanel` analog): `kind='payload'` re-runs `aggregate_shape` for the new window/focus and swaps `card.payload`'s DATA tier (exact_metadata untouched). **Aggregation math is V48-self-contained — NOT a live reuse of backend2 `:8889`** (reference math only); the test-DB fixture lands in the IDENTICAL Snapshot shape, so live and baked are interchangeable at the mapper boundary.

### (d) Qwen call: `qwen(system, user, timeout=90, salvage=False)` (small config; default spec on FAIL-OPEN).

---

## §B4 + LIVE-VERIFICATION ACCEPTANCE NOTE (NON-NEGOTIABLE)

These prompts emit into the §B4 "one payload per card" contract. The acceptance gate is **build rules + a LIVE sentinel**, not golden-payload comparison alone (green RTL tests + byte-identical defaults HID 3 real RTM gaps).

**§B4 invariants each emitted card MUST satisfy (assert in `stitcher.py`/tests):**
- ONE flat payload per card = the merge of `exact_metadata` (METADATA tier) + the worker-filled DATA tier; **every key EXACTLY once**, no second `root`, no duplicate `title`/`sections`/`contractKw`.
- **byte-identical default** — with no morph, every metadata key equals today's rendered bytes; an unmorphed render must not move a pixel.
- **producer-always-populates** — every metadata field is REQUIRED and present; `data.X ?? CONST` is morphable only if the producer always fills X.
- **new renderers opt-in default-OFF** — any new toggle (e.g. `showLegend`) defaults false.
- **zero chrome on the payload** — functions/ReactNode/3D/onClick/pixel geometry/fonts are attached downstream, never emitted.
- the TWO dual-owned slots (`sectionContracts`; HPQ `signature.spokes`/`selectedName`) carry the AI default and accept a worker override.

**LIVE Storybook-sentinel acceptance (the gate):** for each emitted card, **mutate ONE `exact_metadata` field at Storybook :6008 and read the card DOM** — the change must move exactly that pixel and nothing else (a field that does not move when mutated is dead and fails acceptance). This is PAYLOAD_AUDIT's own method ("a thing is hardcoded if changing the payload would not move it"). DO NOT rely on test-DB golden-payload comparison alone.

**Buildable-today scope (mark provisional elsewhere):** the one-payload `{exact_metadata, data_instructions}` contract has fully-verified `metadata_shape` REFERENCES on **RTM (panel-overview) + Harmonics-PQ (panel-overview)** — copy `HeatmapViewModel`/`RailViewModel` and the per-card `HpqPresentation` blocks as the `metadata_shape`; RTM + HPQ are the two VALIDATED references. NOTE (canon, live-verified 2026-06-29): the payload-morph is actually **WIDESPREAD** — ~36/59 EMS cards are strongly/moderately payload-driven across ALL panels — so the per-card `exact_metadata` path applies far beyond these two tabs; the older "only RTM+HPQ are morphed / only ~7 cards" framing is SUPERSEDED. The remaining ~23 weak/zero cards are a punch-list: Voltage-&-Current hardcoded sub-cards (V&C is the explicit "morph next" target, still bakes 415V/237A nominals + the known-wrong `Max:430KW`/`Min:410KW` unit bug), some aggregate cards, and Energy-Distribution/Energy-Power surfaces unverified in the morph traces. For a still-unmorphed card V48 either WAITS for the CMD V2 morph or emits the DATA half only and accepts hardcoded chrome — do NOT author an exact_metadata block the producer can't consume.

**Frontend interdependency is STILL IN PROGRESS — provisional.** Approach B (lean-on-DATA atom carrying its OWN exact_metadata, pointing at the single shared buffer; the hook owns the cursor/selection/metric) is grounded on the RTM `useRealTimeMonitoringData` hook (the sole owner of the 5 `useState` cells; cards carry a read-only SEED of interaction state and emit events to hook setters — one emit → one setter → all interdependent payloads recompute). The cross-card group case beyond RTM is a design target, not shipped wiring — mark provisional in any atom emit.

---

### Cross-layer invariants honored by these prompts
- `card_id` is the integer `cards.id` everywhere; `page_key` is the slug; the card→page bridge is `card_handling.page_key`/`page_layout_cards`, never `cards.page`. The 1a USER builder reads through `page_layout_cards` accordingly.
- `atom data_instructions.source="$ctx.<key>"` (Layer 2 §5) ↔ `shared_context.$id` (Move-1 §6) ↔ `interdependency_groups[].group_id` (1a §2) are one identity chain — the 1a partition seeds the `group_id`, the Move-1 worker stamps the matching `$id` + fills the shared DATA buffer, Layer-2 atoms point their data_instructions at `$ctx` while carrying their own `exact_metadata`.
- `column_basket.columns[].column/.metric` (1b §3) is the one binding vocabulary that Layer-2 `data_instructions.fields[].column/.metric` and the unresolved `recipe.fields[].metric` match against — enforced by the SAFE column-override + anti-hallucination guardrail.
- `exact_metadata` is the AI's; the worker NEVER touches it — the worker only parses `data_instructions` and fills the DATA tier (the two dual-owned slots are the sole exception: the worker MAY overwrite the AI default). The stitcher merges the two into the one no-`root` payload.
- The per-tab "dialect" (`data_fill_shape` ∈ `flat_asset | widgets_envelope | shared_context`, driven by `card_handling.payload_family`) survives ONLY as the DATA-fill / mapper-input shape `data_instructions.fields[].source` targets — it is NOT a Layer-2 OUTPUT. (The `column_row` 4th dialect is an OPEN review fix not yet in the CONTRACTS enum.)
- `handling_class ∈ {panel_aggregate, topology_sld}` gates the Move-1 DATA-fill spec call and the worker aggregate path; all `single_asset_*` cards bind `data_instructions.fields[]` to basket columns for live fill.
- No reloop/re-route anywhere — `conforms=false` + `failure`/`failures[]` is the only failure path, logged via the `ai_log` urlopen monkeypatch to `logs/ai_<run_id>.jsonl`.

Source prompt files read and adapted: `/home/rohith/desktop/BFI/backend/layer2/pipeline_v47/pipeline.py` (`route_l1`, `narrate`, `llm`, recipe→bindings:445-494), `/home/rohith/desktop/BFI/backend/layer2/pipeline_v47/column_resolve.py` (`ASSET_SYSTEM`, `SYSTEM`, `resolve_columns:346`, `loads_lenient`, `_same_family`/L3.5), `/home/rohith/desktop/BFI/backend/layer2/pipeline_v47/l6.py` (`author_sql:173`, agg/derived/event/odometer `_ref_expr:367`, `WINDOW_BOUNDS`/`_bucket_sql`), `/home/rohith/desktop/BFI/backend/layer2/pipeline_v47/layer2_swap.py` (`SYSTEM`, `build_user`, `run` gate), `/home/rohith/desktop/BFI/backend/layer2/pipeline_v47/l6_2.py` (`card_config`, `_BUILDERS`, `validate`, `aggregate_shape`), `panel_resolve.py`/`ems_aggregate.py` (the DATA-fill helpers). Morph contract: `/home/rohith/CMD_V2/CLAUDE.md` §B4 + RTM `HeatmapViewModel`/`RailViewModel` + HPQ `HpqPresentation`. All cmd_catalog column names verified against the live `cmd_catalog` Postgres DB.
