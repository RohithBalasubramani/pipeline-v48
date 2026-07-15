PART 2 — MORPH-MAP EMIT (VARIANT contract — replaces the full exact_metadata retype; item 18, OFFLINE until certified).
For the FINAL card (post-swap) you do NOT retype the metadata tier. The card's exact METADATA SHAPE + byte-identical
STATIC-CONFIG DEFAULTS are shown to you in the user message exactly as before — but every one of those defaults ALREADY
SHIPS byte-identical automatically. Your ONLY metadata output is `morphs`: a flat map of the FEW leaf paths the
prompt/story explicitly drives, each with its new value. Everything you do not name ships as the byte-identical default
by construction — you cannot omit a key, you cannot drift a byte, and there is nothing to re-copy.

== OUTPUT ENVELOPE (STRICT JSON, nothing else) ==
{"morphs": {"<metadata.leaf.path>": <value>, ...},
 "data_instructions": { ...exactly the PART-3 recipe, unchanged rules... },
 "answerability": "full" | "partial" | "none",
 "data_note": null | "<one user-facing sentence>"}
- `morphs` — `{}` when the defaults already serve the story (THE COMMON CASE). One entry per changed METADATA leaf.
- `data_instructions` / `answerability` / `data_note` — authored under the SAME rules as the full-emit contract
  (PART 3): resolved recipe, real basket columns, honest-blank + the five physical walls, best-effort declarations.
  UNCHANGED here: R2-DECLARE (every intentionally-blanked leaf ALSO listed in `data_instructions._honest_blanked` as
  "<slot>: <reason>", never a silent '—'), R10-SEED (no default-payload seed literal survives — fill it from a real
  column or honest-blank+declare it), R8-ROLE (a rail-qualified bypass/mains/utility/grid/incoming/output/battery leaf
  the meter does not sense → honest-blank+declare), and the kind=time discipline (kind=time ONLY on the x/time-axis
  leaf; NEVER on a value/marker/scale leaf like maxLine/minLine/expectedMax).
- There is NO `exact_metadata` key and NO `_morphed` list in this contract: naming a path in `morphs` IS the
  declaration. An undeclared change is impossible — you never author the other leaves at all.

== morphs — RULES (the SAME morph law as the full contract, addressed per-path) ==
- PATH SYNTAX: the leaf's exact path in the METADATA SHAPE block, dotted with [i] indices — e.g.
  "title", "kpi.title", "metricTabs[0]", "sections[2].label". COPY the path segments VERBATIM from the shape shown;
  an invented path does not resolve and is rejected (the leaf then ships its default).
- MORPH ONLY THE STORY-DRIVEN FEW — the handful the prompt/page story EXPLICITLY drives: lead with the asked metric
  (tab order), re-title, tighten/loosen a flagged threshold, re-roster to the asked entity. Every morph must be
  justifiable by a word from the page story / this card's story angle. WHEN IN DOUBT, EMIT NO MORPH — the default
  ships untouched automatically.
- ★ HARDCODED / STATIC ITEMS ARE LOCKED — never morph fixed CONFIG: legends (statusLegend), colour tokens / palettes /
  statusColors / selectionColors, axis labels (metricAxisLabels), units, descriptors, vocab, playback glyphs,
  shade/legend rows, badge labels. A morph on a locked item is a defect (the byte-identity gate reverts it).
- ★ THE ONE EXCEPTION TO LOCKED UNITS — A DECLARED SAME-QUANTITY-FAMILY PROXY MUST MORPH ITS DISPLAY METADATA.
  THE CANONICAL PROXY RULE is unchanged: a substitute is legal ONLY within the slot's physical-quantity family
  (bound column `qty=` EQUAL to the slot's `expected_qty=`). SAME family: bind it + declare it in `data_note` + put
  every caption/label/window leaf that DESCRIBES that slot into `morphs` with its truthful new value (e.g.
  `sourceInputCaption`: "MEMBER IMPORT", a window caption "today"→"this week"). A declared proxy whose display leaves
  are NOT in `morphs` is gate-DROPPED (the leaf honest-blanks). A CROSS-QUANTITY PROXY IS FORBIDDEN, morphed or not —
  the QUANTITY WALL blanks it regardless; when no same-quantity source exists the slot is HONEST-BLANK.
- ★ PERIOD LABELS MUST MATCH THE FILL WINDOW — a period-declaring leaf (`periodLabel`, `range`, a "Monthly"/"Today"
  caption; NOT a picker's rangeOptions list) must agree with the window/range your data_instructions declare. Either
  declare the range the default label promises, or put the label leaf in `morphs` with the fetched window's truth —
  an incoherent leaf is deterministically morphed/blanked by the gate (policy `gates.window_label_policy`).
- SEED ROSTERS ARE FIXTURES, NOT CONFIG — metadata leaves that LIST entity identifiers (panel/feeder display names,
  meter table ids) came from the Storybook fixture. When the run's ASSET / PANEL MEMBERS facts name the real members,
  morph each identifier leaf to the verbatim real name (one `morphs` entry per leaf). If the real member set is not in
  your facts (or differs in size), do NOT invent names — emit no roster morphs and SAY SO in `data_note`.
  ★ PANEL READING SIDE — the PANEL MEMBERS facts mark ONE side ▶ PRIMARY (the direction the prompt asked: OUTGOING
  fed-feeders/bays by default, INCOMER/supply only when the prompt says 'incomer'/'supply'/'source'/'HT side'). Morph
  roster identifier leaves to the ▶ PRIMARY members ONLY; never re-roster to the 'context only' side. The executor's
  member fan-out already reads the PRIMARY side, so the labels must match it.
  ★ aka IS DISPLAY, CANONICAL IS DATA — when a member/asset facts line carries `aka=<human alias>` you MAY morph a
  DISPLAY-label leaf to that alias (it is the plant's human name, declared in `morphs`); every data-addressing string
  (table ids, entity keys, roster data keys) stays the CANONICAL name — mixing them breaks the fill.
  ★ THRESHOLDS MAY GROUND BAND MORPHS — a band/threshold metadata leaf may be morphed ONLY to a boundary quoted
  VERBATIM from the RTM STATUS BANDS facts line (a stored consts.rtm_* row, declared in `morphs`); any other
  threshold number is a guess and is gate-rejected.
- ★ DATA LEAVES ARE NEVER MORPHS (HARD WALL — the #1 defect) — a path ON / INSIDE / ABOVE a DATA leaf (the typed
  0 / [] / null placeholders in the shape) is REJECTED by the producer: DATA fills LIVE from the frame, NEVER from you.
  A rejected data-leaf morph is a CARD FAILURE, not a no-op — so NEVER name one. Morph ONLY true METADATA, and a leaf
  is METADATA only if it is a label the eye reads: title / label / caption / unit / descriptor / a threshold-CONFIG
  number / a roster IDENTIFIER string / a tab-order entry. A NUMBER OR ARRAY THE CHART PLOTS IS DATA, NOT METADATA.
- ★ DATA-LEAF NEVER-MORPH LIST — a path whose LAST segment (or any segment above the leaf) matches ANY of these value
  shapes is DATA; it is FORBIDDEN in `morphs` regardless of what the story says:
    · anything ending `.value` or `.values`      (a plotted magnitude / series array — e.g. `history.data.maxLine.value`)
    · anything ending `.markerPct` / `.pct` / `.percent` / `.ratio`   (a data-fed gauge/axis marker — e.g. `capacity.readyMarkerPct`)
    · a `.maxLine.*` / `.minLine.*` / `.avgLine.*` / `.threshold.*` NUMERIC leaf (an axis reference line fed by data)
    · `metrics[i].value`, `series[i].values`, `panels[i].<qty>`, `tiles[i].value`, `rows[i].<qty>`, `points[i].*`
    · any leaf UNDER a `.data.` / `.series` / `.dataset` / `.frame` container whose default is a number, [] or null
    · any AXIS MARKER / DOMAIN bound / gauge needle / bar height / cell value that the live frame supplies.
  If the story wants such a magnitude to change, that is a DATA request — put the column in `data_instructions.fields`
  (or honest-blank it), NEVER in `morphs`. When unsure whether a leaf is a label or a plotted number, treat it as DATA
  and DO NOT morph it.
<!--DIET_MORPH_SHAPE:ON:BEGIN-->
- ★ CONCRETE VIOLATION (the #1 observed failure — never do this): a morph whose VALUE is an object or array carrying
  measured keys (`h3`/`h5`/`h7`/`kw`/`pf`/`iThd`/`vThd`/`kFactor` grids, `periods[*].panels` matrices, per-member
  reading rows) is a wholesale DATA re-type — every such path is rejected and the tokens are pure waste. A shape shown
  as `<<DATA: N element(s)…>>` is the executor's territory: emit NOTHING for it, in `morphs` or anywhere else.
<!--DIET_MORPH_SHAPE:ON:END-->
- ZERO CHROME — no pixel geometry, fonts, markup, functions, handlers, "rgba(" tokens in a morphed value. A
  chrome-bearing morph is rejected and the default ships.
- ADDRESS LEAVES, NOT SUBTREES — one entry per changed leaf ("sections[2].label": "…"), never a whole object/array
  replacement (a subtree value that drifts undeclared leaves is reverted leaf-by-leaf by the gate).
- DUAL-OWNED SLOTS ('AI-default, data-overridable') — leave them OUT of `morphs` unless the story drives them; the
  default ships and the worker MAY overwrite from the live frame, exactly as before.
- NEW RENDERERS OPT-IN DEFAULT-OFF — a renderer toggle (e.g. showLegend) stays at its resting default; morph it ON
  only when the prompt explicitly asks.
