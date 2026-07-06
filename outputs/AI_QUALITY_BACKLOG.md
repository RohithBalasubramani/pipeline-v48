# AI QUALITY BACKLOG — synthesized from the 4-axis review (2026-07-06)

Synthesis of the four read-only axis reviews (AXIS-1 PROMPTS, AXIS-2 INPUTS, AXIS-3 EXTRACTION, AXIS-4 DB-CONFIG;
full findings recovered from the workflow journal `wf_a928d308-13e/journal.jsonl` — 34 findings, deduplicated here
into 22 backlog items). Ground truth behind every number: `outputs/logs/ai_r_*.jsonl` (85 L2 emit calls / 20 runs),
`outputs/_log_archive/**` (18,023 logged :8200 calls, 6,812 parsed L2 emits), `failures_r_*.jsonl`,
live `cmd_catalog.app_config` SELECTs.

**Ownership fence (why WHEN matters):** two fix workflows are editing concurrently and own
`layer2/**` (gates/prompts/emit), `ems_exec/**`, `grounding/**`, `host/web/**` + `host/server.py`.
→ **SAFE-NOW** = DB row inserts/edits + docs + this file. **NEXT-ROUND** = repo code/prompt edits, formatted at the
bottom as ready-to-paste `residuals` for `scripts/wf_fast_loop_round.js`.

---

## 0. Ranked summary (impact ÷ effort)

| # | Item | Axis | Impact class | Effort | WHEN |
|---|------|------|--------------|--------|------|
| 1 | `_morphed` contract fix (prompt + producer telemetry) | EXTR+PROMPTS | defect: restores a DEAD feature surface (2/6,812 compliance) | S | next-round |
| 2 | ONE canonical proxy / quantity-wall rule (kill 4 conflicting statements) | PROMPTS | defect: closes a PROVEN cross-quantity fabrication driver | S | next-round |
| 3 | Truncation no-retry inside `llm/client.py` + system+user budget preflight | EXTR | latency: kills the doubled multi-minute hang | S | next-round |
| 4 | `answerability` fail-open → `partial` + nested-key rescue | EXTR | defect: ~700 cards/sweep stop claiming "full" by code default | S | next-round |
| 5 | panel_aggregate + roster_spec third branch in user_message | INPUTS | defect: resolves a measured 12/23 behavioral coin-flip | S | next-round |
| 6 | Mirror-drift one-liners (3 files, one token each) | DB | defect-prevention (DB-outage divergence) | XS | next-round |
| 7 | Seed the missing byte-equal config rows (SQL below) | DB | defect-prevention + discoverability; behavior-neutral | XS | **SAFE-NOW** |
| 8 | Delete orphaned `data_quality_policy` `page_tail_alias.*` rows | DB | defect-prevention (two-homes drift trap) | XS | **SAFE-NOW** (after 5-min grep) |
| 9 | `vocab.time_label_patterns` + relative-offset pattern | INPUTS | tokens: −3.6K tok on card 71, −2.3K card 58 | XS | **SAFE-NOW** (coordinate) |
| 10 | User-message token-cut bundle (★/✗ tokens, slot suffix, dead fields, endpoint vocab→system) | INPUTS | tokens: ~1.0–1.3K tok/call | M | next-round |
| 11 | RECOVERY LIBRARY per-card filter + conditional ROSTER section | INPUTS | tokens: ~1.5–2K tok/call + removes illegal-fn temptation | S | next-round |
| 12 | NAMEPLATE + DATA-WINDOW fact lines in the ASSET block | INPUTS | defect: targets 255 `no_reading` blanks + invented-rating consts | S | next-round (dep: nameplate re-seed) |
| 13 | Prompt text corrections (const/source contradiction, FOUR→FIVE walls, PART 3, filename ref, RTM fixtures) | PROMPTS | defect: removes guaranteed nondeterminism sources | S | next-round |
| 14 | Serve `data_note` + L2 answerability to the FE | EXTR | defect: honesty channel visible end-to-end (1,369 notes currently dropped) | S | next-round (fe) |
| 15 | `stage=` telemetry on basket/asset_resolve/stories call sites | EXTR | observability: 84 outage entries stop bucketing as `stage='-'` | S | next-round |
| 16 | qty-classifier ancestor-bleed + chrome-key fixes (card 19/17 wrong walls) | INPUTS | defect: wrong `expected_qty` walls blank correct binds | M | next-round |
| 17 | guided_json rollout: 1b asset → 1b basket → 1a stories → L2 emit | EXTR+PROMPTS | defect: makes 4 violation classes unrepresentable (81/1,931 basket hallucinations) | M | next-round (staged) |
| 18 | Morph-map-only emit contract (AI emits `{path: value}`, producer owns skeleton) | EXTR | latency: ~10× completion cut — the biggest lever on the 141 emit timeouts | M | next-round (after #1) |
| 19 | System-prompt restructure: numbered HARD RULES top + checklist bottom, ≤30K | PROMPTS | defect+tokens: ~6K tok/call attention dilution removed | L | next-round (after #2/#13, A/B'd) |
| 20 | Dead contract fields trim (`conforms/failure/render_slot/controls/card_id/$ctx`) | EXTR | tokens (completion) + contract honesty | S | next-round (with #17) |
| 21 | 1a catalog compression (−45%) + 1b label dedup | PROMPTS | tokens: 14.8K→~8K router; ~1–1.4K/call 1b | M | next-round (low prio) |
| 22 | Hygiene: cast-integrity test, role_scrub docstring, parse-hardening, vLLM service audit | DB+EXTR | defect-prevention, ops | S | next-round / ops |

---

## 1. SAFE-NOW (apply today: DB rows + docs; zero repo-file overlap)

### 1.1 Byte-equal config seeding — behavior-neutral by construction (item 7)

All accessors already exist in code; each INSERT mirrors the code default exactly, so nothing changes until someone
edits a row. Fixes the "SELECT on `quantity.%` misleadingly suggests the whole vocabulary is seeded" trap (3 of 6
quantity vocabularies were missing) and brings the newest executor layer up to the V48 rule
*every knob = cmd_catalog row + accessor with code-default fallback*.

```sql
-- psql (cmd_catalog DSN per config/databases.py)
INSERT INTO app_config (key, value, data_type, section, note) VALUES
 -- quantity vocabularies (code mirrors: layer2/quantity_class.py:96, layer2/gates.py:305, layer2/gates.py:332)
 ('quantity.dimensional_classes', '["voltage","current","power","energy","frequency","temperature"]', 'json', 'quantity',
  'dimension-bearing classes for compatible() dimension-breach half (card-42 %-slot-fed-raw-kW gate) — code mirror layer2/quantity_class.py:96'),
 ('quantity.axis_slot_tokens', '["ymin","ymax","miny","maxy"]', 'json', 'quantity',
  'axis-bound slot tokens (card-40 yMin<-loadFactorWindowPct rule) — code mirror layer2/gates.py:305'),
 ('quantity.expectation_slot_tokens', '["expected","forecast","predicted"]', 'json', 'quantity',
  'expectation-slot tokens (card-42 actual==expected rule) — code mirror layer2/gates.py:332'),
 -- post-fill executor/display policy family (code mirrors verified this session)
 ('xaxis.derive_labels', 'on', 'text', 'xaxis', 'x-axis label derivation valve — code mirror ems_exec/executor/xaxis.py:_enabled (default on)'),
 ('xaxis.clock_patterns', '["^\\d{1,2}:\\d{2}(:\\d{2})?$"]', 'json', 'xaxis', 'clock-label regexes — code mirror ems_exec/executor/xaxis.py:_clock_patterns'),
 ('xaxis.label_format', '%H:%M', 'text', 'xaxis', 'derived x-label strftime — code mirror ems_exec/executor/xaxis.py:_fmt'),
 ('view.auto_select', 'on', 'text', 'view', 'view auto-select valve — code mirror ems_exec/executor/view_select.py:21'),
 ('reasons.max_roster_records', '80', 'int', 'reasons', 'roster-gap record cap (sibling of seeded reasons.max_unbound_records=60) — code mirror ems_exec/executor/roster_gaps.py:24'),
 ('chart.yscale_ticks', '5', 'int', 'chart', 'y-scale tick count — code mirror ems_exec/executor/yscale.py:33 (_DEFAULT_TICK_COUNT=5)'),
 ('vocab.delta_projection_keys', '["delta","deltaText","deltaTone"]', 'json', 'vocab', 'delta projection keys — code mirror ems_exec/executor/display.py:55'),
 -- rtm severity knobs (code mirror ems_exec/renderers/_story/real_time_monitoring.py:24-28) — seed-only variant of item DB-5;
 -- the collapse onto band.*/event_threshold stays a next-round decision (needs visual sign-off: 85 vs 90 load-warn, 65/75 vs 45/55 busbar C)
 ('rtm.load_warn_pct', '85', 'number', 'rtm', 'RTM load warn %% — code mirror real_time_monitoring.py; NEAR-DUP of band.overview.kw_load_pct.hi=90 (see backlog item 7/DB-5 before retuning)'),
 ('rtm.load_crit_pct', '100', 'number', 'rtm', 'RTM load crit %%'),
 ('rtm.pf_floor', '0.9', 'number', 'rtm', 'RTM PF floor — dup of event_threshold TRUE_PF below 0.9'),
 ('rtm.pf_warn', '0.95', 'number', 'rtm', 'RTM PF warn'),
 ('rtm.voltage_dev_warn_pct', '5', 'number', 'rtm', 'RTM voltage deviation warn %% — dup of band.overview.voltage_dev_pct.hi=5'),
 ('rtm.voltage_dev_crit_pct', '10', 'number', 'rtm', 'RTM voltage deviation crit %%'),
 ('rtm.current_unbal_warn_pct', '10', 'number', 'rtm', 'RTM current unbalance warn %% — dup of event_threshold I_UNBAL above 10'),
 ('rtm.busbar_temp_warn_c', '65', 'number', 'rtm', 'RTM busbar temp warn C — NEAR-DUP of band.overview.busbar_temp_c.hi=55 (numbers intentionally differ? decide in item DB-5)'),
 ('rtm.busbar_temp_crit_c', '75', 'number', 'rtm', 'RTM busbar temp crit C')
ON CONFLICT (key) DO NOTHING;   -- deliberate: do not clobber rows the concurrent fixers may have since inserted
```

Prep-only rows (INERT until their reader lands next-round — insert now or with the code, either is safe):

```sql
INSERT INTO app_config (key, value, data_type, section, note) VALUES
 ('panel_aggregate.member_columns', '["active_power_total_kw","reactive_power_total_kvar","apparent_power_total_kva","kpi_true_pf","power_factor_total","voltage_avg","current_avg","current_neutral","kpi_neutral_to_phase_ratio_pct","pf_gap_vs_full_load","harmonic_5th_pct","harmonic_7th_pct","thd_current_r_pct","thd_current_y_pct","thd_current_b_pct","thd_voltage_r_pct","thd_voltage_y_pct","thd_voltage_b_pct","neutral_stress_event_active","current_unbalance_pct"]', 'json', 'panel_aggregate', 'per-member column set — code mirror ems_exec/renderers/panel_aggregate.py:_MEMBER_COLS (reader lands in next-round item 6c)'),
 ('panel_aggregate.sum_columns', '["active_power_total_kw","reactive_power_total_kvar","apparent_power_total_kva","current_avg","current_neutral"]', 'json', 'panel_aggregate', 'extensive (SUM) columns — code mirror panel_aggregate.py:_SUM_COLS; all others reduce by mean'),
 ('panel_aggregate.event_neutral_column', 'neutral_stress_event_active', 'text', 'panel_aggregate', 'neutral-stress event register — code mirror panel_aggregate.py:_EVT_NEUTRAL'),
 ('display.rate_key_pattern', 'delta.*per.*min|dkwdt|deltapermin', 'text', 'display', 'rate-key regex — code mirror ems_exec/executor/display.py:58 _RATE_KEY_RE (needs the cfg accessor from next-round item 6d)')
ON CONFLICT (key) DO NOTHING;
```

- Impact: defect-prevention (dead-row / two-homes drift class) + row-tunability; zero behavior change.
- Risk: none (byte-equal); `ON CONFLICT DO NOTHING` protects against racing the concurrent fixers.
- Follow-up (next-round, layer2/emsexec fences): mirror the same INSERTs into `db/seed_quantity_class.sql` and a new
  `db/seed_executor_display_policy.sql` so a fresh DB seeds identically.

### 1.2 Delete the orphaned alias rows (item 8)

`data_quality_policy` rows `page_tail_alias.harmonics-pq` / `page_tail_alias.overview-sld-3d`
(seeded by `db/seed_endpoint_resolve_policy.sql:7-10`) have ZERO readers — the documented consumer
`grounding/endpoint_resolve.py` does not exist; the live policy is the app_config json row `routes.page_tail_alias`
(read by `layer2/emit/data/consumer_binding/screen_map.py:12` and `layer1a/parse/granularity_reconcile.py:41-43`).
Editing the dq rows is a silent no-op today — a classic drift trap.

- Pre-step (5 min, read-only): grep pipeline_v45/v46 + CMD_V2 backend trees for `page_tail_alias` (v47+v48 already
  verified clean) per the verify-before-dead rule.
- Then: `DELETE FROM data_quality_policy WHERE key LIKE 'page_tail_alias.%';` and (next-round, db-seeds fence)
  retire `db/seed_endpoint_resolve_policy.sql:7-10`.
- Impact: defect-prevention. Risk: near-zero after the grep.

### 1.3 Time-bucket label patterns row edit (item 9) — behavior-changing, COORDINATE

Add a relative-offset pattern to the `vocab.time_label_patterns` app_config row (json list; consumed by
`layer2/emit/slot_catalog.py:73-82 time_bucket_label_key()`):
append `"^-\\d{1,3}\\s*(h|d|m|w|min)$"`.

- Why: labels `-23h…-0h` / `-29d…-0d` defeat the `[*]` compression → card 71 ships 96 near-identical sibling slot
  lines (13,552 chars), card 58 ships 60 (8,360 chars). Both cards sit under the 36K oversize budget so
  `_compact_catalog` never fires either.
- Impact: tokens — card 71 −3.6K tok (23K→~19.4K), card 58 −2.3K tok. Pattern requires ALL labels to match, so a
  genuine entity list cannot be wrongly collapsed.
- Risk: LOW, but it changes live prompt bytes → tell the running fix workflows before applying (their A/B baselines
  shift). The `'Apr 15','16','21 (Today)'` family (card 17) is NOT pattern-solvable — it rides with next-round item 16.

### 1.4 Docs (this file) — done.

---

## 2. NEXT-ROUND — fix-group backlog (feed to `scripts/wf_fast_loop_round.js`)

Each item below lists exact files, impact, risk. The paste-ready `residuals` array is in §3.
Sequencing inside the round(s): **A (text/one-liners) → B (client + consumption) → C (token cuts) → D (structural,
A/B-gated)**. Do NOT run D in the same round as A–C (D's A/B needs a stable baseline).

### Batch A — small diffs, high certainty

**A1. `_morphed` contract fix (item 1)** — group: layer2
- Files: `layer2/prompts/metadata.md:20` (OPTIONAL/"audit only" → *"REQUIRED — the ONLY channel through which an
  authored change ships; an undeclared morph is reverted to the default; a declared proxy whose caption morph is
  undeclared is gate-dropped"*); `layer2/prompts/data_instructions.md:263` (add `"_morphed":[]` inside the
  `exact_metadata` contract exemplar); `layer2/emit/metadata/producer.py:64-92` (diff AI metadata vs stored skeleton,
  record `_undeclared_morphs` count as telemetry — do NOT auto-promote yet).
- Evidence: producer applies ONLY declared morphs; `_morphed` present in **2 of 6,812** emits → all AI metadata
  authoring (proxy captions, re-rostering, retitles) is a silent no-op today; 1,369 emits wrote a data_note yet ~zero
  morphs ever shipped.
- Impact: defect — restores the entire morph feature surface; prerequisite for item 2's proxy path to be completable.
- Risk: prompt-only + telemetry = none; auto-promotion is explicitly deferred (byte-identity seam).

**A2. Canonical proxy / quantity-wall rule (item 2)** — group: layer2
- Files: `layer2/prompts/metadata.md:7`, `layer2/prompts/data_instructions.md:188-198` (delete the self-contradicting
  "different-quantity column … you may bind it" sentence), `:240`, `layer2/emit/user_message.py:213-215` (append the
  missing SAME-QUANTITY qualifier — the laxest restatement sits closest to the data and is the one the model followed),
  `layer1b/prompts/column_system.md:14` (align vocabulary so 1b never seeds a cross-family `substitute_for`).
- Canonical wording (state ONCE): *"A substitute/proxy is legal ONLY within the slot's physical-quantity family
  (column `qty=` must equal slot `expected_qty=`). Same family: bind + declare in data_note + morph the describing
  caption leaves (list in `_morphed`). Different family: OMIT the field — no data_note legitimizes it; the gate blanks it."*
- Evidence: PROVEN violation — run `r_f3b19721cb` calls 6+10 (card 76, transformer thermal-life) bound
  `fn=loadFactorPct/active_power_total_kw` into `timeline.tempAxis.*` slots marked `expected_qty=temperature`, with a
  data_note that verbatim-echoes the prompt's own unqualified substitute instruction. The policy exists in 4
  conflicting forms today.
- Impact: defect — closes the demonstrated cross-quantity fabrication door + the gate-blanking noise it creates.
- Risk: keep the same-quantity proxy path explicitly legal (export-register-for-dead-import, week-for-today) or
  partial-answerability cards regress to blanks.

**A3. Truncation no-retry + budget preflight in `llm/client.py` (item 3)** — group: other (llm/ — no fence overlap)
— **DONE 2026-07-06**: (a) `llm.no_retry_kinds` (same row+default as emit.py) now breaks the parse-retry loop;
(b) `finish=="length"` classified BEFORE the parse-success return (a truncated-but-balanced reply never ships);
(c) preflight `(len(system)+len(user))//4` vs `llm.prompt_budget_tok` (row seeded =45000, code default mirrors,
0=off) → kind `over_budget`, call never sent; a GROWN retry prompt over budget skips the doomed retry keeping the
real kind. NOTE: fail-fast chosen over compaction per the campaign mandate (never send a doomed call). Files:
`llm/client.py`, `db/seed_llm_client_budget.sql` (applied), `tests/test_llm_truncation_budget.py` (10 tests).
- Files: `llm/client.py:126-142`: (a) after classifying `err_kind`, `if err_kind in cfg('llm.no_retry_kinds'): break`
  — the emit-level rule (`layer2/emit/emit.py:77-78`) is currently bypassed by the inner parse-retry loop; (b) move
  the `finish=="length"` check BEFORE the parse-success return so a truncated-but-balanced reply can never ship
  unmarked; (c) preflight: if `(len(system)+len(user))//4 + completion floor (~20K)` exceeds the model window,
  compact the user message BEFORE sending (the `emit.prompt_char_budget` machinery exists but counts user-only —
  budget must count system+user).
- Evidence: `ai_r_f9787f915f.jsonl` — 3 length-truncated emits, retry prompt GREW (46,438→46,589 ptok),
  total_tokens pinned at 65,536; the retry deterministically truncates again with FEWER completion tokens.
- Impact: latency — removes the doubled multi-minute hang on every oversized emit (c24-family recurrence at the
  client layer); defect — closes the no-retry-deterministic gap (the v48 gotcha rule, again).
- Risk: a genuinely-transient garbled 'truncated' reply loses its one retry — the data shows truncation here is
  always deterministic.

**A4. answerability fail-open (item 4)** — group: layer2
- Files: `layer2/build.py:403`: absence → `"partial"` (absence of a declaration is not a declaration of full); read
  `raw['data_instructions'].get('answerability'/'data_note')` as fallback before defaulting (rescues 29 nested cases).
- Evidence: 730 of 6,812 emits (10.7%) omit top-level answerability/data_note; build.py defaults them to `"full"`.
- Impact: defect — ~700 cards/sweep stop claiming full by code default; honest-note channel stops losing the nested 29.
- Risk: dashboards' "full" count drops until the schema fix (item 17) lands — that is the honest number.

**A5. panel_aggregate roster_spec third branch (item 5)** — group: layer2
- Files: `layer2/emit/user_message.py:255-282` — add the branch `handling_class=panel_aggregate AND roster_spec` →
  *"ROSTER CARD: emit data_instructions.roster conforming to roster_spec + fields:[] + the endpoint your consumer
  needs; answerability reflects member coverage"*; stop the `★ NO-FIELDS CARD … OMIT ems_backend … answerability=full`
  chrome text from reaching roster cards. Write the new text against what `layer2/build.py`'s gate ACTUALLY accepts.
- Evidence: 23 affected calls carry both "roster MUST conform" and "OMIT the ems_backend block"; measured 12/23
  emitted the block, 11 omitted (coin flip under identical instruction); card 18 dropped its roster entirely.
- Impact: defect — deterministic behavior on the panel-overview family (also the biggest prompts, 22–24K tok).
- Risk: low; must match the gate's real acceptance, not intent.

**A6. Mirror-drift one-liners (item 6)** — groups: layer2 + emsexec
- (a) `layer2/emit/user_message.py:19-20`: add `"panel_aggregate"` to the `gates.fields_optional_classes` code default
  (currently 4-of-5, contradicting its own docstring; on DB outage the prompt and gate DISAGREE exactly for
  panel_aggregate cards). Better: hoist ONE accessor (`config/gates_vocab.py`) imported by `layer2/build.py:383-385`,
  `user_message.py`, `validate/build.py:54-55` (+ the two test literals).
- (b) `host/display_dash.py:68`: code default `["kw","kwh"]` → `["kw","kwh","kva","kvar"]` (the row was extended by a
  concurrent fixer; on DB outage kva/kvar honest-nulls would skip the dash and re-crash the card boundary — the PCC-4
  fmt(null) family).
- (c) `ems_exec/executor/roster.py:80`: flip the code default `"off"` → `"on"` for `roster.interpreter_enabled` (row
  = 'on' is the settled production state; today an outage silently disables the whole roster fill path for the
  member-scope cards).
- Impact: defect-prevention (DB-outage parity — the exact failure mode the shared-row design exists to prevent).
- Risk: none while the DB is reachable; each is a one-token change.

### Batch B — consumption + observability

**B1. Serve `data_note` + L2 answerability (item 14)** — group: fe
- Files: `host/server.py:312-347` `_enrich_card`: add `data_note` and `l2_answerability` (distinct key —
  `validate/render_verdict` stays the verdict source of truth); `host/web/src/cmd/registry.tsx:157-165`: render
  data_note beside the gap-chip (or fold into `_gap_note`, server.py:68, so proxy notes participate in `render.reason`
  even when verdict='render').
- Evidence: prompt promises *"saved and shown to the user"* (`data_instructions.md:246`); 1,369 of 6,812 emits carried
  a data_note; grep of host/web finds NO consumer of `notes` — e.g. card 70's "power factor as a proxy for
  availability" note is invisible while the card renders as an unqualified reading.
- Impact: defect — the zero-fabrication/honest-degrade mandate at the last mile.
- Risk: none functional; purely additive.

**B2. `stage=` telemetry + per-stage timeouts on the untagged call sites (item 15)** — group: other (layer1a/1b — no fence overlap)
- Files: `layer1b/basket/column_basket.py:62` (stage='basket', retry_once + `llm_failed` surfaced via
  `contract_problems`), `layer1b/resolve/asset_resolve.py:99` (stage='asset_resolve'),
  `layer1a/story_builder.py:33-37` (stage='stories' + `record('layer1a','stories_llm_failed')` — today an outage sets
  every story='' silently and that empty story rides into every L2 emit). Replace literal `timeout=120/60` with
  `llm.timeout.<stage>` rows.
- Evidence: 5× `stage=- timed out` + 79× `stage=- URLError Errno 111` unattributable failures.
- Impact: observability + honest degradation signaling. Risk: none (success path unchanged).

### Batch C — token/latency cuts (measure with one A/B run per bundle)

**C1. User-message boilerplate bundle (item 10)** — group: layer2
- Files: `layer2/emit/user_message.py:39-45` (★/✗ per-line prose → `| RAW★` / `| ✗FAIL` tokens + one header sentence;
  −129,580 + −12,376 chars across the run set, ~440 tok/call); `layer2/emit/slot_catalog.py:255-261` (trim the
  55-char qty parenthetical to `| expected_qty=X`; header already states the rule; ~155 tok/call — do together with
  PROMPTS item so exactly THREE wall statements remain: numbered rule + schema header + machine tokens);
  `user_message.py:34-36,210` (drop the never-populated `metric`/`rank` fields — 4,540/4,540 lines empty; ~87 tok/call);
  `user_message.py:56-65` (cap the title-case-label + why-prose in RELEVANT COLUMNS to substitute rows conf<1.0;
  ~325 tok/call); `user_message.py:168-174,229-232` + `layer2/prompts/data_instructions.md` (move the run-constant
  endpoint closed-set/retired-list/choose-by paragraph ONCE into the system ems_backend section; keep only the
  per-card natural-endpoint line; ~215-255 tok/call, 95,319 chars/sweep).
- Impact: tokens ~1.0–1.3K/call (~85 calls/run); restores completion headroom on the 22–24K-tok cards.
- Risk: low — every cut is a verbatim duplicate of a retained statement; one A/B run to confirm RAW★ still suppresses
  the wrap-in-fn defect ([emit-correctness R1] provenance).

**C2. RECOVERY LIBRARY filter + conditional ROSTER (item 11)** — group: layer2
- Files: `layer2/emit/emit.py:24-46` — pass `card_in` into `_recovery_library_block()`; drop every fn whose
  `base_columns` are not all in `card_in['column_basket']` (keep nameplate-denominator fns only when the nameplate row
  is populated); ALWAYS append the trailer `"(N fns hidden: base columns not on this meter)"` and keep the
  honest-degrade line. `layer2/prompts/data_instructions.md:212-232` — include `## ROSTER` only when the card has
  `recipe.roster_spec` or `handling_class=panel_aggregate` (28 of 85 calls need it).
- Impact: tokens ~1.5–2K/call; removes the illegal-fn temptation surface (DG fuel fns shown to panel voltage cards).
- Risk: over-filtering silently removes legal recoveries — the trailer + a unit test on fn counts guards it.
  NOTE: this makes the system prompt per-card-variable at the TAIL — the long shared prefix stays byte-identical, so
  vLLM prefix caching is preserved (verify the flag — see item 22d).

**C3. NAMEPLATE + DATA-WINDOW fact lines (item 12)** — group: layer2 (DEPENDENCY: the fixed nameplate re-seed —
`asset_nameplate` still holds 209 fabricated class_default ratings per the render-guarantee memory; print only
real-source rows or this LICENSES fabrication with prompt authority)
- Files: `layer2/emit/user_message.py:198-199` — two fact rows in the ASSET block:
  `NAMEPLATE: rated_kva=600 | rated_current_a=— | contracted_kw=—` via `config/nameplates.py` with
  *"— ⇒ any fn/const needing it is unbindable — omit (honest-blank)"*; `DATA WINDOW: first=<ts> last=<ts> (age Nd) —
  anchor ranges to last, not wall-clock` from describe/validate stats; extend
  `layer2/emit/panel_members_block.py` member lines with `last=<ts>`.
- Evidence: the two rules the AI most often violates depend on facts it is never given — 255 per-leaf
  `no_reading` blanks (28/38 window emits chose range='today' over a historical dataset); card 69 `const I_RATED
  value=131` and card 40 `ratedKw=600` consts emitted on faith.
- Impact: defect — converts the two most-violated rules from guesswork into checkable facts, at ~40–80 chars/call.
- Risk: the fabricated-nameplate dependency above; otherwise low.

### Batch D — structural (A/B- or benchmark-gated; run as its own round)

**D1. Morph-map-only emit contract (item 18)** — group: layer2 (after A1 telemetry confirms compliance)
- Change the contract so the AI emits ONLY `{path: value}` morphs and the producer owns the full skeleton — the AI
  currently re-authors the entire metadata block (up to 19K-token completions) that `produce()` throws away.
- Impact: latency — ~10× completion cut; the biggest single lever on the 141 l2_emit timeouts. Do BEFORE enabling
  guided_json on the emit path (D2), since guided decoding adds per-token cost.
- Risk: byte-identity seam — keep `gate_exact_metadata`/enforce as backstop; A/B against gold runs.

**D2. guided_json rollout (item 17 + 20)** — groups: other (1a/1b) then layer2
- Order: (1) `layer1b/resolve/asset_resolve.py` — `{confident: bool, names: array{enum: shown candidates}}` (kills the
  `[NO-DATA]` name leak, 3/994); (2) `layer1b/basket/column_basket.py` — feasible/probable with column enums (81/1,931
  calls hallucinate columns today, silently filtered); (3) `layer1a/story_builder.py` — stories object with
  `patternProperties ^\d+$` (kills 'card 44' keys + the stories-as-list AttributeError); (4) LAST, after D1:
  `layer2/emit/emit.py:72` — envelope schema requiring swap_decision/fields-kind-enums/answerability enum; optionally
  per-card slot/column/fn enums. `llm/client.py:83-99` already supports `schema=`; the 1a route call proves it live.
- With (4), trim the dead contract fields (item 20): drop `conforms/failure/render_slot/controls/card_id/$ctx` from
  the required emission + `layer2/schema.py:_REQUIRED` (or mark echo-only) — CONFIRM first that no in-flight change
  starts consuming `controls`/`render_slot`.
- Impact: defect — whole violation classes become unrepresentable (the 4 gate-rejected re-prompts per run were all
  enum-preventable); recovers 2× ~18K-tok retry cost per affected run; smaller completions.
- Risk: grammar-compile latency per unique schema (per-card enums defeat grammar caching) — benchmark one one live
  run on :8200 before enabling on the emit path; keep gates.py as backstop (schema cannot express cross-field rules).

**D3. System-prompt restructure (item 19)** — group: layer2 (LAST; after A1/A2/C-cuts land and a gold A/B harness exists)
- `layer2/prompts/{swap,metadata,data_instructions}.md` + `layer2/emit/emit.py:49-57` assembly: ~10 numbered HARD
  RULES at top (each 1–2 lines + consequence), reference material (compact per-kind table, ROSTER, $ctx, RECOVERY
  LIBRARY) in the middle, 10-line checklist restatement at the bottom next to the output exemplar; fold the 10,864B
  COMMON DEFECTS list into the owning rules as ONE worked example each. Target ≤30K bytes (from 53,482). Keep STATIC
  prefix for cache. Include the Batch-A text corrections if not already landed: const/source contradiction
  (`data_instructions.md:103` vs `:209` vs `gates.py:556` — document what the gate accepts:
  `live | test-db | $ctx | const`), FOUR→FIVE walls (`:47,:98,:260` + `user_message.py:249`), the dangling
  "(see PART 3)" (`metadata.md:7`), the filename reference (`user_message.py:247`), and move the RTM/HPQ
  sectionContracts fixtures (`metadata.md:19`) into those two cards' user context.
- Impact: defect + tokens — hard rules read BEFORE the 18.6K reference wall; numbered rules give the gate-retry
  re-prompt (`emit.py:67-70`) citable handles; ~6K tok/call dilution removed.
- Risk: HIGHEST of the backlog — 8 rounds of accumulated edits encode real regressions; MOVE text, don't drop worked
  examples (endpoint closed-set compliance is 75/75); mandatory A/B vs gold runs.

**D4. qty-classifier ancestor-bleed + chrome keys (item 16)** — group: layer2 (classifier is shared by prompt AND gate — change both sides together)
- Files: `layer2/quantity_class.py:166-175` (stop the slot_class ancestor walk at the leaf's parent element; extend
  token vocab: vavg/vmin/vmax→voltage, amps/neutrala→current, sag/swell→event-count);
  `vocab.element_chrome_keys` row + `layer2/emit/slot_catalog.py:42-47` (add 'label'/'name' so numeric-string labels
  — card 17's `'16'` — never become fillable value keys with `expected_qty=power`); optional sequence-aware
  day-of-month pattern for the `'Apr 15','16'` family; give the 3 `*_event_active` flags `qty=event-flag` instead of
  `qty=?`.
- Evidence: card 19 — `worstVoltage.neutralA → expected_qty=voltage` (it's a current), `worstCurrent.vAvg/vMin/vMax →
  expected_qty=current` (voltages), `worstCurrent.sag → expected_qty=current` (event count): walls that BLANK correct
  binds and invite wrong ones.
- Impact: defect — removes provably wrong walls; tokens — card 17 −4-5K chars.
- Risk: medium — gate/prompt coherence; 'name' may be a legit value key somewhere: sweep payload_stripped first.

**D5. 1a catalog compression + 1b label dedup (item 21)** — group: other (layer1a/1b build-time, no prompt edits)
- `layer1a/db_reads` catalog builder: collapse purpose/theme/answers (10,404B of 3 restatements per sweep) into one
  merged story line per page → 14.8K→~8K user message ×27 router calls; KEEP the granularity keywords
  (panel/feeder/single-generator) the routing rules key on — validate on the near-tie examples in
  `layer1a/prompts/system.md:21-26`. `layer1b/resolve`: emit the label only when it differs from
  title-case(column_name) (~25-30% of the block).
- Impact: tokens; low urgency (18.9K router is not the pain point). Risk: low.

**D6. Hygiene batch (item 22)** — groups: mixed, all tiny
- (a) tests: app_config cast-integrity test — for every row assert `_cast(value, data_type, SENTINEL) is not SENTINEL`
  (the `display.null_dash` dead-row class: data_type='number' on a text value made the row INERT; found live, fixed by
  a concurrent fixer — nothing prevents the next mis-typed INSERT).
- (b) `grounding/role_scrub.py:33-34` docstring: describes the retired fail-empty design; code follows the
  code-default-mirror mandate (group: strip).
- (c) parse-hardening: `layer2/build.py:560` feedback fragmentation on '; ' (carry failures as a list);
  `layer1a/story_builder.py:19` `_norm_id` '44-45'→'44' (reject non-pure-digit keys once D2-(3) lands);
  `run/layer2_all.py:29` payload aliases exact_metadata (copy at the boundary).
- (d) OPS (not a repo file): audit `/etc/systemd/system/vllm.service` — AXIS-2 measured `--max-model-len 32768` with
  no `--enable-prefix-caching`, while archived logs show 65,536-token completions and memory says 64K. Reconcile the
  actual window, ensure prefix caching is on (85 calls/run share a 53K-byte prefix), and re-check completion headroom
  vs the 24K-tok worst prompts. Restart only in a quiet window (kills in-flight sweeps).

---

## 3. Paste-ready next-round input (`scripts/wf_fast_loop_round.js` args)

Layer strings are chosen to route to the intended fix group (regexes in the script: `layer2|emit|gates|prompt`→layer2,
`strip|payload|grounding|seed`→strip, `fill|roster|render|exec|derivation|validate`→emsexec,
`web|frontend|ssr|component`→fe, else other). Pages are drawn from the script's PROMPTS map so the targeted recheck
exercises the worst-affected families. Run Batches A–C as ROUND 1; Batch D as ROUND 2+ with A/B gating.

```json
{
  "ts": "20260706_backlog",
  "residuals": [
    {"page":"transformer-asset-dashboard/thermal-life","card_id":"76","issue":"A1 _morphed contract: metadata.md:20 says OPTIONAL/audit-only but producer.py:64-92 applies ONLY declared morphs (2/6812 compliance) — make _morphed REQUIRED in prompt, add \"_morphed\":[] to the contract exemplar (data_instructions.md:263), add _undeclared_morphs telemetry diff in producer (NO auto-promote)","layer":"layer2-emit-prompts","log_evidence":"6812 parsed l2_emit across _log_archive: _morphed present in 2"},
    {"page":"transformer-asset-dashboard/thermal-life","card_id":"76","issue":"A2 canonical proxy rule: state same-quantity-family proxy ONCE (metadata.md:7, data_instructions.md:188-198 delete 'different-quantity...you may bind it', :240, user_message.py:213-215 add SAME-QUANTITY qualifier, column_system.md:14 align vocab) — proven cross-quantity bind followed the laxest restatement","layer":"layer2-emit-prompts","log_evidence":"ai_r_f3b19721cb calls 6+10: loadFactorPct/active_power_total_kw bound into timeline.tempAxis.* expected_qty=temperature"},
    {"page":"panel-overview-shell/harmonics-pq","card_id":"*","issue":"A3 llm/client.py: truncated (finish=length) retried inside parse loop bypassing llm.no_retry_kinds; retry GROWS prompt at context wall; also order finish-check BEFORE parse-success return; preflight budget must count system+user","layer":"llm-client","log_evidence":"ai_r_f9787f915f: ptok 46438->46589, total pinned 65536; failures reason=truncated"},
    {"page":"panel-overview-shell/voltage-current","card_id":"18","issue":"A4 build.py:403 answerability fail-open: absence -> 'full'; change default to 'partial' + read data_instructions-nested answerability/data_note fallback (rescues 29 nested)","layer":"layer2-build","log_evidence":"730/6812 emits omit top-level answerability; 29 nest inside data_instructions"},
    {"page":"panel-overview-shell/voltage-current","card_id":"18","issue":"A5 user_message.py:255-282: panel_aggregate WITH roster_spec falls into NO-FIELDS-CARD/OMIT-ems_backend chrome text while also told 'roster MUST conform' — add third branch (ROSTER CARD: roster conforming to roster_spec + fields:[] + endpoint; answerability=member coverage); write against the gate's real acceptance","layer":"layer2-emit","log_evidence":"23 calls: 12 emitted ems_backend, 11 omitted; card 18 dropped roster entirely"},
    {"page":"panel-overview-shell/real-time-monitoring","card_id":"*","issue":"A6a user_message.py:19-20 gates.fields_optional_classes default missing 'panel_aggregate' (build.py:383/validate/build.py:54 carry 5) — add token or hoist ONE accessor config/gates_vocab.py imported by all 3 (+2 test literals)","layer":"layer2-emit","log_evidence":"DB row has 5 entries; user_message default has 4"},
    {"page":"panel-overview-shell/energy-power","card_id":"*","issue":"A6b host/display_dash.py:68 mirror stale: [\"kw\",\"kwh\"] vs row [\"kw\",\"kwh\",\"kva\",\"kvar\"] — byte-equal the code default (DB-outage fmt(null) re-crash parity)","layer":"exec-display","log_evidence":"row display.unit_value_key_suffixes extended by concurrent fixer"},
    {"page":"individual-feeder-meter-shell/real-time-monitoring","card_id":"*","issue":"A6c ems_exec/executor/roster.py:80 default 'off' vs row 'on' — flip code default to 'on' (row stays the kill-switch); outage currently disables the whole roster interpreter","layer":"roster-exec","log_evidence":"SELECT roster.interpreter_enabled='on'"},
    {"page":"ups-asset-dashboard/battery-autonomy","card_id":"70","issue":"B1 serve data_note + l2_answerability: host/server.py:312-347 _enrich_card additive fields; render beside gap-chip in host/web/src/cmd/registry.tsx:157-165 or fold into _gap_note so proxy notes hit render.reason — 1369 notes currently invisible","layer":"frontend-web-serve","log_evidence":"response_r_44796d791a card 70 proxy note dropped; grep host/web: no consumer of notes"},
    {"page":"individual-feeder-meter-shell/power-quality","card_id":"*","issue":"B2 stage= telemetry: column_basket.py:62 (stage=basket + retry_once + llm_failed via contract_problems), asset_resolve.py:99 (stage=asset_resolve), story_builder.py:33-37 (stage=stories + stories_llm_failed record); replace literal timeouts with llm.timeout.<stage> rows","layer":"layer1-telemetry","log_evidence":"failures: 5x stage=- timeout + 79x stage=- Errno111 unattributable"},
    {"page":"panel-overview-shell/harmonics-pq","card_id":"23","issue":"C1 user-message token bundle: RAW-star/FAIL per-line prose -> tokens + header defs (user_message.py:39-45); slot qty parenthetical -> '| expected_qty=X' (slot_catalog.py:255-261); drop empty metric/rank fields (user_message.py:34-36,210); cap relevant-cols why-prose to conf<1.0 rows (:56-65); move endpoint closed-set/retired/choose-by to system prompt (:168-174,229-232 -> data_instructions.md ems_backend section). ONE A/B run after","layer":"layer2-emit-prompts","log_evidence":"measured: 129580+12376 star/fail chars, 48275 slot-suffix chars, 4540/4540 empty metric+rank, 95319 endpoint chars per sweep"},
    {"page":"panel-overview-shell/harmonics-pq","card_id":"5","issue":"C2 emit.py:24-46 filter RECOVERY LIBRARY to basket-compatible fns (+ '(N fns hidden...)' trailer, keep honest-degrade line, nameplate fns only when rating populated); ROSTER section only when roster_spec/panel_aggregate (data_instructions.md:212-232). Tail-only change preserves prefix cache","layer":"layer2-emit","log_evidence":"7812-char library, 50 fns unfiltered to all 85 calls; ROSTER ships to 85, needed by 28"},
    {"page":"diesel-generator-asset-dashboard/voltage-current","card_id":"69","issue":"C3 add NAMEPLATE fact line (config/nameplates.py; '- => unbindable, omit') + DATA WINDOW first/last/age line ('anchor to last, not wall-clock') to ASSET block (user_message.py:198-199); add last=<ts> per member in panel_members_block.py. GATED on the fixed nameplate re-seed (209 fabricated class_default rows)","layer":"layer2-emit","log_evidence":"255 no_reading blanks; 28/38 window emits chose today; card 69 const I_RATED=131, card 40 ratedKw=600 on faith"},
    {"page":"transformer-asset-dashboard/tap-rtcc","card_id":"*","issue":"C4 prompt text corrections: const/source contradiction (data_instructions.md:103 vs :209 vs gates.py:556 — document 'live|test-db|$ctx|const', split the 2332B bullet in 4, drop mock asides); FOUR->FIVE walls (:47,:98,:260 + user_message.py:249); '(see PART 3)' -> BEST-EFFORT+ANSWERABILITY (metadata.md:7); filename ref (user_message.py:247); move RTM/HPQ sectionContracts fixtures out of metadata.md:19 into the 2 cards' user context","layer":"layer2-prompts","log_evidence":"grep of logged 53482B system: no PART 3; gate wants live|test-db|const|$ctx"}
  ]
}
```

ROUND 2+ (structural, each gated as described in §2 Batch D — submit as its own residual set after Round 1 re-verify):
D1 morph-map-only contract (layer2, A/B) → D2 guided_json staged 1b-asset/1b-basket/1a-stories/L2-emit + dead-field trim
(other→layer2, latency benchmark on :8200) → D3 system-prompt restructure ≤30K (layer2, gold A/B mandatory) →
D4 qty-classifier ancestor-bleed + chrome keys (layer2, prompt+gate together) → D5 1a/1b build-time compression →
D6 hygiene (cast-integrity test, role_scrub docstring, parse-hardening, vLLM service audit).

---

## 4. Cross-axis notes for the fixers

- **Two independent root causes for the same visible defect family:** cross-quantity binds are conflict-driven
  (A2 — four differently-qualified proxy policies, laxest nearest the data), NOT purely prompt-size-driven; fixing A2
  is prerequisite to judging D3's effect.
- **The l2_emit timeout family is completion-size-driven** (the AI re-authors the full metadata skeleton that
  `produce()` discards): A1 → D1 is the latency path, not more timeout budget.
- **Prefix-cache invariant:** every prompt change should keep the shared system PREFIX byte-identical across the 85
  parallel calls; per-card variation belongs at the TAIL (C2) or in the user message.
- **A/B discipline:** the current prompts encode 8 rounds of real regressions (endpoint closed-set compliance 75/75,
  RAW★ suppressing wrap-in-fn). Move text; never silently drop a worked example. Baseline = the 20 Jul-6 runs in
  `outputs/logs/ai_r_*.jsonl` + `outputs/replay2/sweep_index.json`.
- **Verified-good surface (no action):** AXIS-4 byte-diff confirmed all other seeded rows equal their code mirrors
  (role_scrub 15, quantity 3, validation 10, gates/windows, event_threshold 7, emit oversize knobs, reason_template
  32) — the only true drifts were A6a/A6b/A6c, and the only dead rows were the two display.* rows already re-typed by
  the concurrent fixer.

---

## Cert payload_error triage (2026-07-06 self-run, no workflow)

The two `payload_error` classes surfaced by the 3-concurrent cert sweep were **not code defects** — both were
execution-environment artifacts, confirmed by clean re-runs against a current-code host.

### RESOLVED-A — c47 "validate-fail honest-blank" mislabel (STALE DUMP)
- Dump `response_r_1bc17049b9.json` showed c47 (PowerQualityCard, UPS) with `payload_error="fields[0] column
  'thd_current_r_pct' failed pre-L2 data validation …"`. That message is the `_col_issue` string, which
  `layer2/gates.py:666-667` already routes to `_honest_blanked` **telemetry**, NOT to card-blocking `issues`/`failure`.
- The dump was from a host started **before** the gates.py fix (host 22:25 < gates.py mtime 22:33). Fresh run on a
  restarted host: **`payload_error=None`, verdict=render, answerability=full, 2/2 real leaves** — the AI binds
  iThd/vThd as declared same-quantity proxies (data_note) and honest-blanks the 3 voltage-harmonic leaves it can't
  measure. SSR: cards 47/48/49 all render OK. **No fix needed; code was already correct.**

### RESOLVED-B — c24 / c58 "llm timeout" (vLLM CONTENTION, not output size)
- Root cause: `run/layer2_all.py` fanned ALL page cards' l2_emit calls concurrently (unbounded). Each is a ~22K-tok
  prompt; N concurrent emits split vLLM decode throughput N ways. The biggest emit (c24 harmonics heatmap) sat at
  **152s on a solo 5-card page** — right at the `llm.timeout.l2_emit=150` fail-fast edge — and starved past it under
  the 3-page (~15-concurrent) sweep. Skeleton sizes are small (c24=3527c); the completion bulk is data_instructions
  (per-feeder×metric bindings), so this is throughput-bound, not output-size-bound.
- Clean re-runs: c24 → `payload_error=None`, verdict=partial, **36/56 real leaves**. c58-class same (composite chart).
- **FIX (durable, DB-driven):** bound the fan-out — `run_parallel(tasks, max_workers=cfg("layer2.emit_concurrency",4))`
  (`run/parallel.py` + `run/layer2_all.py`; `db/seed_layer2_emit_concurrency.sql`). Excess cards queue; each in-flight
  emit keeps enough throughput to finish with margin. Generic, no card ids, code-default 4. L1a∥L1b split untouched.

### FOLLOW-UP — c49 const-gate over-blanks LoadImpactChart axis chrome (NOT cert-blocking)
- On the power-quality page, c49's const-source gate honest-blanks `loadImpact.views.*.yMax/yMin/yTicks/watchLines[].value`
  as "const has no real DB source". Those are **axis chrome** (scale bounds / tick arrays / threshold lines), not data
  readings — a false positive that strips the chart's y-axis scale. Card still renders SSR-clean (no crash, no
  fabrication), so it is a quality follow-up, not a defect: extend the chrome carve-out (chrome_subtree_keys or the
  const-gate axis exemption) to cover yMax/yMin/yTicks/watchLines while keeping `stats[*].value` (real readings) gated.

**MEASURED (cap=4, host restarted):** the heatmap page (cards 23-27, the 152s-solo worst case) re-fired while a
second run (browser-triggered "dg voltage and current") ran CONCURRENTLY — a deliberate 2-page contention that used to
force the c24 timeout. Result: **all 5 cards `payload_error=None`** (c24 = 36/56 real leaves), SSR 5/5 render OK,
0 fabrication seeds. Every per-emit finished inside its 150s budget under contention that previously starved it.
Total page wall-clock 203s (page-level, under contention; the 150s budget is per-EMIT not per-page). pytest 565 pass.

**CROSS-PAGE CAVEAT:** the cap bounds concurrency PER page (per run_2_all). A cert sweep that runs many pages at once
still multiplies (K pages × 4). The cap fixes the single-page robustness gap (a normal heatmap-page request was at the
150s edge); a multi-page SWEEP should additionally limit page-concurrency (≤2-3) — the 6-page sequential re-fire proved
that path clean. Knob `layer2.emit_concurrency` drops to 3 for more per-emit margin with no code change.
