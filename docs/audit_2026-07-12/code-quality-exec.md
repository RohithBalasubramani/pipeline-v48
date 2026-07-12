# Code-quality audit — `ems_exec` (executor / data / derivations / renderers)
**Lens:** code-quality-exec · **Date:** 2026-07-12 · **Scope:** `/home/rohith/desktop/BFI/backend/layer2/pipeline_v48/ems_exec` (68 files, ~13.6k lines)
**Files read in full:** fill.py, fab_guards.py, data/neuract.py, members.py, roster.py, roster_paths.py, paths.py, panel_aggregate.py, narrative_ai.py, renderers/__init__.py, _story/__init__.py, scalar_tile_fill.py, scalar_mean_fill.py, load_factor_fill.py, measurable_resolve.py, wildcards.py, indexed_families.py (head), gaps.py, roster_gaps.py, verify.py, window_policy.py, derivations/registry.py, _insight.py, _agg.py, serve/run.py, recipe.py, display.py, plus config/app_config.py, config/neuract_dsn.py, data/db_client.py (dependencies).

## Overall assessment

This is a disciplined codebase, not a sloppy one: closed vocabularies (bindings/reducers/roster modes), honest-null arithmetic in one pure module (`_agg.py`), one dotted-path addresser for the fill side (`paths.py`), DB-knob-with-code-default everywhere, and genuinely zero hardcoded card-id *branching* in the executor (card numbers appear almost exclusively in comments as defect archaeology — the one real exception is `_story/CARD_PAGE`). The dominant risks are operational, not stylistic: (1) a re-introduction of the exact cache-poison family the team already fixed elsewhere on 2026-07-09, (2) a single shared DB connection with no timeouts behind a tunnel that is documented to flap, and (3) 211 broad `except Exception` handlers with **zero logging anywhere in the package**, which makes real bugs indistinguishable from honest blanks. Below that sit accretion problems: `fill()` as a 450-line pass-orchestrator whose ordering is load-bearing but documented only in prose, three coexisting mechanisms for filling a series slot that have already drifted from each other, and a four-module rescue stack with triplicated helpers.

---

## HIGH severity

### H1. Negative-result caches are process-lifetime — the member-cache-poison family, re-introduced
The 2026-07-09 "member cache poison" fix established the rule *never cache an empty/negative result forever* and landed `data/ttl_cache.py` (used by `data/registry/lt_mfm.py:33` and `data/lt_panels/panel_members.py:34`). Four caches inside ems_exec violate that rule today:

- `data/neuract.py:24` `_COLS_CACHE` — `present_columns()` (lines 72–86) caches `frozenset()` when `_run()` returns `[]` **on a tunnel outage** (line 84–85). Every read (`latest`, `bucketed`, `window`, `edge_count`…) gates on `col in present_columns(table)`, so one flap during first touch of a table permanently honest-blanks **every leaf of that asset** until process restart.
- `data/neuract.py:25` `_LOGGED_CACHE` — `column_logged()` (lines 89–104) caches `False` when the probe query errors (line 101–103). Post-recovery this is worse than a blank: fab_guards **CLASS 2** (`fab_guards.py:308–312`) blanks a *real* reading whenever `column_logged()` is False and `_table_has_rows()` is True — a healthy-then-flap-then-healthy sequence leaves CLASS 2 blanking live columns forever. The rescues (`scalar_mean_fill.py:90`, `scalar_tile_fill.py` via `measurable_resolve.resolve_column:329–344`, `load_factor_fill.py:110`) also all refuse permanently on a poisoned False.
- `executor/fab_guards.py:201–219` `_ROWS_CACHE` — `_table_has_rows()` caches `ok=False` on outage (line 218), permanently disarming CLASS 2 for that table (fail-safe direction, but still wrong state for process life).
- `executor/recipe.py:26` `@lru_cache read(card_id)` returns and caches `{}` on any DB error (lines 39–40), and `_endpoint_card` (line 71) caches `None` — a cmd_catalog blip at a card's first render silently disables its roster recipe (panel cards degrade to legacy/blank) until restart.

**Fix:** reuse the existing `data/ttl_cache.py` (knob `cache.resolution_ttl_s` already exists) and adopt never-cache-empty semantics in all four spots; for `recipe.read`, only cache successful reads. Behavior-preserving in the healthy path.

### H2. One shared psycopg2 connection, connect() held under the global lock, no timeouts — a hung :5433 tunnel freezes every card fill
`data/neuract.py:22–47`: `_POOL` holds exactly one connection per DSN key; `_conn()` performs `psycopg2.connect(**_dsn.conn_kwargs())` **inside `with _LOCK`** (lines 37–47). `config/neuract_dsn.py:60–69` `conn_kwargs()` sets **no `connect_timeout`**, and `_run()` sets no statement timeout. Consequences at production scale:

- A black-holing tunnel (documented failure mode) makes the connect block for the OS TCP timeout (~2 min) *while holding the global lock*, so **every** thread in the host's parallel card fill stalls — even reads that needed no new connection.
- All queries from all concurrently-filled cards serialize through the single connection (psycopg2 serializes cursor execution per connection), so the "pool" is a throughput ceiling of one in-flight query per process.
- The sibling module already learned this lesson: `data/db_client.py:40–47` `pg_connect()` sets `connect_timeout=5` with the comment "dead tunnel → fail fast, not ~2min TCP hang". `ems_exec/data/neuract.py` never got the fix.

**Fix:** add `connect_timeout` (and a server-side `options=-c statement_timeout=...` knob) to `conn_kwargs()`; move `connect()` outside the lock (connect, then swap under lock); allow a small per-thread or N-sized pool. Risky (hot path) but behavior-preserving.

### H3. Zero logging + 211 broad `except Exception` — real defects are indistinguishable from honest blanks
Measured: 211 `except Exception` handlers in ems_exec, 64 of them immediately `pass`; `grep -rn "import logging"` over the package returns **nothing** (the only "log" match is a docstring in `_insight.py:17`). Every post-fill pass in `fill()` is wrapped `try/except: pass` (`fill.py:474–657`), so a TypeError introduced into yscale/xaxis/fab_guards silently skips the pass with no trace anywhere — the payload just quietly regresses to a prior defect class. `serve/run.py:97–106` goes further: if `fill()` raises, it silently re-runs with `{"fields": []}` — a systemic bug presents as "every card blank" with zero diagnostic. `_windowed_register_delta` (`fill.py:110–134`) converts *any* exception into "register family, delta unresolvable → honest-blank", masking bugs as data gaps. The gaps channel records *data* reasons, not *code* failures — there is no channel at all for the latter.

**Fix (small, no framework):** one `logging.getLogger("ems_exec")`; in each pass-guard `except Exception: log.warning("pass %s failed card=%s", name, card_id, exc_info=True)` — the existing `try/except` structure stays. Optionally count pass-failures into the payload telemetry next to GAPS_KEY. Safe.

---

## MEDIUM severity

### M1. `fill()` is a ~450-line god-orchestrator with load-bearing pass order documented only in prose
`executor/fill.py:213–663` — one function performs: roster seam #1, window/columns/ratings resolution, wildcard pre-pass, single-index promotion (lines 275–298), indexed-family pre-pass (306–337), the main field loop with four inline chrome guards (338–430), then **eleven** sequentially-ordered, valve-guarded, individually-try/except'd post-fill passes (yscale → norm_series → xaxis → restore_chrome → view_select → display → freshness → trend_badge → fab_guards → three rescues → gap scans). Ordering constraints ("Runs BEFORE the three post-fill measurable RESCUES… ordering fix, DEFECT A/card 50" `fill.py:583–588`; "Runs after scalar_mean_fill so a sibling-field fill wins first" `fill.py:622`) exist only in comments. There are 17 lazy `from ems_exec.executor import X` statements inside function bodies (cycle-avoidance smell). The module also re-exports ~40 underscore-private names "byte-compatibly" (lines 42–61), and `gaps.py:102–108` reaches into `sys.modules["ems_exec.executor.fill"]` at runtime so tests that monkeypatch `fill._gap_sentence` still work — production indirection existing purely as a test seam.

**Fix:** extract the post-fill chain into an explicit ordered list of `(name, callable, valve)` in one small module (this also gives H3 its logging hook and makes ordering declarative); import passes at module top of that module (breaking the cycle via the list, not lazy imports); replace the sys.modules seam with a direct injection point. Risky (hottest path) but mechanical.

### M2. Three coexisting mechanisms fill "a series into an array slot", and they have already drifted
- `[*]` wildcard grow — `wildcards.py`
- `[i]` same-key families — `indexed_families.py`
- "single-index promotion" routing solo `[0].key` fields into the wildcard path — `fill.py:275–298`

Observable drift inside one grown array: the **column** branch aligns member series to the anchor axis *positionally* — `vals = (vlist + [None] * n)[:n]` (`wildcards.py:141`) — while the **derived** branch three lines later is timestamp-aligned with an explicit comment "never positional" (`wildcards.py:147–153`). Each member field is also bucketed with **its own** `f.get("sampling")` (`wildcards.py:139`) while the anchor's sampling came from the first field (line 111–115): two fields declaring different samplings inter-leave a 30-day daily axis with the first 30 *hours* of an hourly series — values attributed to wrong buckets. Same-table/same-sampling emissions mask this today; it is a latent misattribution, which is worse than a blank in a zero-fabrication system.

**Fix:** align the column branch by timestamp exactly like the derived branch, and force the group's sampling to the anchor's. Then fold "promotion" into wildcards' entry predicate so the mechanism count is two with one documented split (wildcard-vs-indexed). Breaking (intended behavior change in the mismatch case).

### M3. A wildcard grow that *throws* still marks its array as "written real" — seed-guard exemption hole
`wildcards.py:74–80`: `_fill_wildcard_arrays` does `try: _grow_one_wildcard_array(...) except Exception: pass` and then `filled_paths.add(array_path)` **unconditionally**. `fill.py:303–305` puts those paths into `written_value_paths`, and `fab_guards._is_written` (`fab_guards.py:360–371`) treats everything *under* a written prefix as filled-real — so CLASS 4 seed-leak policing is disabled for the whole subtree. Failure scenario: `_grow_one_wildcard_array` raises after the container was grafted from the default (`wildcards.py:90–96`) → default seed elements sit in the served payload, exempt from the very guard built to catch them (card-73 class). Move the `filled_paths.add` inside the `try` (and only after a successful set). Breaking only in the failure path (it correctly blanks what today would leak).

### M4. The rescue stack triplicates its own plumbing — drift has already produced three variants of the same predicate
- `_honest_blanked` wildcard-tuple matcher implemented three times: `scalar_tile_fill.py:175–190`, `scalar_mean_fill.py:28–41`, `load_factor_fill.py:321–336` (the third also loops both address forms — the normalization `fill._honest_blank_paths` (fill.py:83–96) already did, so it double-normalizes).
- `_tokset` (app_config csv/json → lowercased set) duplicated: `load_factor_fill.py:172–181` and `measurable_resolve.py:89–97`.
- `_cfg` fail-open shim copied ~8×: `load_factor_fill.py:39`, `measurable_resolve.py:30`, `roster_eval.py:13`, `panel_aggregate.py:44`, `derivations/nameplate.py:17`, `derivations/power.py:10`, `_insight.py:36`, `_story/energy_distribution.py:16`.
- Five slightly-different blank predicates: `gaps._blank_val` (gaps.py:30–35, treats all-None list as blank), `roster_gaps._blank` (:38–39, adds `[]`), `scalar_mean_fill._blank` (:24–25, scalars only), `load_factor_fill._blank` (:71–72), `roster._const_is_blank` (roster.py:242–247).
- `scalar_tile_fill._toks` (:165–167) is a function that re-imports `paths._toks` per call.

One `executor/_shared.py` (or additions to `paths.py`/`measurable_resolve.py`, the vocab home) for `_honest_blanked`, `_tokset`, `_cfg`, and a documented pair of blank predicates removes ~120 lines and the drift risk. Safe.

### M5. DB knobs frozen at import time — inconsistent with the package's own call-time-knob pattern
- `renderers/panel_aggregate.py:66–68` — `_ENERGY`, `_ENERGY_EXPORT`, `_ENERGY_POLICY` read `cfg()` at module import; `:240–242` `_LOAD_FACTOR_FNS` likewise.
- `executor/fab_guards.py:686` — `_MAGNITUDE_RE = _mag_re()` compiles the magnitude-unit vocab at import (the docstring at 663–665 calls the unit vocab "DB-driven").
- `renderers/_insight.py:65–68` — `LLM_URL/LLM_MODEL/LLM_TIMEOUT/LLM_TEMPERATURE` at import.

Everywhere else in the package knobs are read call-time. Two failure modes: an app_config edit + `reload()` changes some behavior but silently not these; worse, `config/app_config.py:18–24` `_load()` is `lru_cache` and **caches `{}` on a boot-time cmd_catalog outage** — a bad boot pins every knob in the process at code defaults with no signal (same poison family as H1, one directory up). Convert the import-time reads to small accessor functions (pattern already used 50 lines away in the same files); fix `_load` to not cache the empty error result. Risky only in that mid-process row edits start taking effect.

### M6. The card-72 "DEFINITIVE ban" on reactive-energy-from-power is enforceable around, via a DB expression row
`derivations/energy.py:305–315` neuters `reactive_energy_from_power_kvarh` to `return None` ("BANNED… DEFINITIVE 2026-07-07"). But `derivations/registry.py:303–325` `_execute()` consults `derivation_binding.expression` **first** and returns its value whenever non-None — so seeding an expression row for `reactiveEnergyFromPowerKvarh` (the DB-first culture makes this the *likely* way someone "re-enables" it) silently resurrects the fabrication class the audit banned, bypassing the neutered fn. The registry descriptor (`registry.py:116`) still advertises the fn in `catalog()` to Layer 2, inviting bindings. Enforce the ban at the dispatch layer: a small banned-set (DB row + code mirror) checked in `_execute`/`run`, and drop the fn from `catalog()`. Safe today (no expression row exists), closes the hole.

### M7. fab_guards.py: 972 lines, four guard classes + restore + vocab plumbing in one file, and per-leaf vocab reconstruction
The file is the package's largest and is really five concerns (CLASS 1–4 + `restore_chrome`), each with its own DB-vocab accessors. Beyond the atomic-rule tension, there is a measurable hot-path cost: the payload walks call vocab accessors **per leaf** — `_apply_class1._walk` calls `_is_time_axis_key` per node (`fab_guards.py:177–190`), which rebuilds `_time_axis_exact()` + `_time_axis_suffixes()` sets and may hit `config.vocab` each time (:117–126); CLASS 4's walk calls `_is_chrome_key`/`_structural_chrome_keys`/`_chrome_selector_keys`/`_data_value_keys` per leaf (:520–652), each reconstructing a set via `cfg()` — and `config/app_config._cast` re-runs `json.loads` for every json-typed row on every call (app_config.py:27–39). For ~10² leaves × ~10 vocab lookups × 70 cards/page-sweep this is thousands of avoidable set builds + JSON parses per page. Hoist the vocab sets once per `apply()` call (compute at entry, pass down) — no TTL machinery needed, behavior identical within a card. Also: `import re as _re` sits mid-file at line 660 below code that references it (`_key_words`, :510–517). Split the file per class when next touched. Safe.

### M8. Two dotted-path addressing systems, both exporting a function named `_toks` with different semantics
`executor/paths.py:16–17` `_toks(path) -> [str]` (flat tokens, "THE ONE dotted-path address home") vs `executor/roster_paths.py:13–17` `_toks(slot) -> [(name, marker)]` (tuples with `[]`/`[*]` markers, plus its own `_base`/`_readdress`/`_targets`/`values_at` walkers). `fill.py:42` re-exports the former; `roster.py:70–71` re-exports the latter. A maintainer moving code between the fill side and the roster side gets a silently-different return shape under the identical private name (a `tuple(_toks(p))` set-membership check against the wrong flavor never matches — precisely the shape of the H1/M4 path-set plumbing). Rename the roster one (`_slot_toks`) and note the deliberate split in both docstrings. Safe (mechanical rename inside the package + its re-export).

### M9. `CARD_PAGE` — a hardcoded card-id → page map in code, the one true AI-first violation found
`renderers/_story/__init__.py:38–43`: `CARD_PAGE = {8: "real-time-monitoring", 19: "voltage-current", 25: "harmonics-pq", 28: "individual-feeder"}`, used by `narrative_ai._page_key` (narrative_ai.py:32–38) when ctx omits `page_key`. The codebase elsewhere goes to great lengths to avoid exactly this (`renderers/__init__.py:57–63` replaced a card-63 id hardcode with a shape discriminator + DB vocab; cmd_catalog.card_handling exists to classify cards). A fifth narrative card, or a renumber, is a code edit. Move the mapping to a cmd_catalog row (card_handling extra column or app_config json) with this dict as the code-default mirror — the pattern is already established everywhere else. Safe.

### M10. Panel fan-out is N+1 sequential queries over the single shared connection
`executor/members.py:236–258` (`bucketed_rolled_members`) and `:283–356` (`bucketed_multi`) issue one `_nx.bucketed`/`bucketed_delta`/`bucketed_edges` SQL **per member per spec-key** sequentially; `rows()` (:88–101) is one `latest` per member. A PCC panel with ~10 members and a multi-spec trend card is 20–40 round-trips through the one pooled connection (H2) over an SSH tunnel — panel cards' latency scales linearly with member count and stacks with page concurrency. The gic_* per-meter table layout forces per-table SQL, but the reads are embarrassingly parallel or UNION-able. Fix after H2 (per-thread connections make a `ThreadPoolExecutor` fan-out safe), or generate a single `UNION ALL` statement per spec. Risky (hot path), behavior-preserving.

### M11. AI-controlled string manually escaped into SQL; the shared `q()` has no parameter support
`executor/recipe.py:79–85` `_endpoint_card` interpolates the **emission-declared** endpoint (`di.consumer.endpoint`, an LLM output — recipe.py:96–102) into SQL with only quote-doubling: `e = str(endpoint).replace("'", "''")` → f-string. `data/db_client.py:11–27` `q(db, sql)` shells out to `psql -c` and offers no parameterization, which is why the manual escape exists. Quote-doubling is adequate under default `standard_conforming_strings=on`, but this is the only place in the audited package where model output reaches SQL text, and the defense is one server setting away from insufficient. Add a params-capable path (`pg_connect` already exists in db_client) or validate the endpoint against `^[a-z0-9-]+$` before lookup. Safe.

---

## LOW severity

### L1. Redundant per-field re-query for NULL columns in the raw path
`executor/fill.py:204–206`: when the shared `latest_row` has None for a column, `_field_value` re-queries `_nx.latest(asset_table, [col])`. The column is by construction in `raw_cols` (fill.py:258–260 uses the same `kind`/`present_cols` filter), and both reads select the same `ORDER BY ts DESC LIMIT 1` row — the fallback returns the same None, costing one extra tunnel round-trip per NULL-valued raw field per card. Delete the fallback (or keep only when `latest_row == {}`, the read-failed case). Safe.

### L2. Legacy panel path: time axis taken from the *last* rolled series; re-implements fill's time-axis logic
`renderers/panel_aggregate.py:134–171` `_fill_bucketed_series` sets `axis` from whichever declared series was rolled **last** (line 156) and then writes it for all `kind='time'` leaves; two columns with different bucket coverage (members reporting one column but not another) misalign points and axis. Lines 158–171 also duplicate fill.py:395–405's startms/endms/list dispatch. Legacy-only (recipe cards bypass this), so Low; fix by intersecting/unioning bucket axes or reusing the wildcard grow's shared-anchor approach. Breaking in the mismatch case.

### L3. Stale references and dead scaffolding
- `renderers/panel_aggregate.py:84–85` comment: "defaults to mean via `_agg.reducer_for`" — no such function exists anywhere in ems_exec (verified by grep); the actual mechanism is the `_SUM_COLS` set.
- `renderers/_agg.py:88–96`: a full banner header "the quantity → reducer map — the single ground-truth per-column reduction" with **nothing under it** (the map was deleted; the banner survived).
- `derivations/registry.py:156–172`: `_LT_PANELS = _NEURACT` kept "purely as the worked example", then `LIBRARY = dict(_LT_PANELS)` — the live flat library is named after the deprecated simulator branch.
These comments *are* the design documentation this codebase leans on (pass ordering, honest-null rules), so rot here is costlier than usual. Safe.

### L4. `_card_id` duplicated verbatim
`renderers/__init__.py:170–183` and `renderers/narrative_ai.py:41–52` are the same function (keys `id/card_id/cid`, int coercion, bare-id tolerance). One import away. Safe.

### L5. Polarity classification by substring can misfire on labels
`executor/verify.py:51–70`: `_polarity_of_token` matches needles like `"va"` (from `-va`) as substrings of the joined unit+label blob — `"Availability"` contains `va` and classifies as *apparent*. Today this is fenced by the requirement that the **fn** side also carries a known energy polarity (`_polarity_conflict`, :89–105), so a false slot-side hit alone can't blank; but the fence is one refactor away. Token-exact matching (the package already has `measurable_resolve._tokens`) removes the trap. Breaking only in edge labels.

---

## Notes / observations that did not make the findings cut

- **Rescue statistics are mean-of-bucket-means:** `scalar_tile_fill.py:129–133` and `scalar_mean_fill.py:94–103` average hourly-bucket AVGs, weighting a 1-sample hour equally with a 3600-sample hour. For a rescue KPI this is acceptable; documenting it in the module docstring would prevent a future "numbers don't match" hunt (`load_factor_fill` already solved the analogous problem natively at :101–152).
- **`load_factor_fill._native_load_factor` builds raw SQL via `_nx._tsexpr/_qcol/_qtbl/_run`** (load_factor_fill.py:115–135) — the only module composing SQL outside the "ONLY door" (`data/neuract.py` docstring line 1). It reuses the door's own quoting helpers, so it's contained; if a second module ever does this, promote a `neuract.native_stat()` read instead.
- **Two gap systems** (`gaps.py` per-field, `roster_gaps.py` per-roster-leaf) mirror each other's record shape and addressing; they cover disjoint leaf families by design and share `reason_templates`, so this is acceptable duplication — but the record dict literal is built in three places (`gaps.py:189–196, 238–245`, `roster_gaps.py:42–44`, `fab_guards.py:138–140`); one `make_gap()` would pin the schema.
- **`serve/run.py` sankey sweep** (:36–45) exists because a fab_guards class-killer can blank sankey endpoint strings — a pass fighting a pass. The right home is inside fab_guards' CLASS 4 exemptions (sankey `source/target` are structural identity); the sweep is a correct belt-and-braces for now.
- **`renderers/__init__.py` and the shape-discriminator** (`_is_telemetry_3d`, :57–91) is a model of how the card-63 hardcode was *removed* — cite it as the pattern for M9.
- **`config/app_config.cfg` docstring** ("Editing the row changes behavior with no code change", :42–44) overstates: it requires `reload()` or restart because `_load` is `lru_cache(maxsize=1)`. Fold into M5's fix.
- **`db_client.q()` forks a `psql` subprocess per query** — outside this lens's scope (data/), but every ems_exec config accessor ultimately rides it; the per-process caches around it are what make it viable, which raises the stakes of H1/M5.
- **Positive:** `verify._verify`'s removal of the denorm epsilon clamp is documented with its rationale in place (:9–16); `_agg.py` is exemplary pure math; `members.py` takes every column set as a parameter (genuinely zero card knowledge); `paths._set_leaf_typed`'s type-preservation contract (:80–92) is the linchpin of per-leaf degradation and is respected everywhere I checked.
