# Code-Quality Audit — layer1a / layer1b / layer2 (2026-07-12)

Lens: code quality — smells, duplication, naming, dead code, complexity, atomic-structure violations, error-handling.
Scope: `/home/rohith/desktop/BFI/backend/layer2/pipeline_v48/{layer1a,layer1b,layer2}` (~7,900 LoC).
Every citation below was read directly in this pass.

## Overall assessment

The three layers are **unevenly finished**. layer1a is genuinely clean: small single-purpose files, clear
fail-closed/fail-open decisions, DB-driven vocab, no dead code found. layer1b is close behind — good micro-module
discipline (`resolve/`, `guardrail/`, `basket/`) with a handful of dead-vocabulary leftovers from the 2026-07-09
collision-gate deletion and a fragile positional-row contract. **layer2 concentrates the debt**: the four largest
files (`build.py` 779, `gates.py` 837, `quantity_class.py` 791, `emit/user_message.py` 417) each bundle multiple
concerns and contain the two largest functions in the subsystem (`_finalize` ≈318 lines, `enforce_honest_blank`
≈138 lines), directly contradicting the project's own atomic-structure rule — while the `swap/` package
simultaneously over-applies that rule (a 5-line gate file that is logically dead). The cross-cutting production
risk is the data-access pattern all three layers share: one `psql` subprocess per query with f-string SQL, ~10+
queries per card in the L2 fan-out.

---

## Findings (ranked)

### 1. HIGH — `layer2/build.py::_finalize` is a 318-line function stacking ~14 sequential concerns
**Files:** `layer2/build.py:373-690` (also `run_card` 693-755, `_finalize_with_gate_retry` 758-779)

`_finalize` sequentially performs: LLM-error marker handling (381-392), morphmap vs full-path routing (387, 403-441),
metadata produce/gate/enforce (394-440), nested-envelope rescue (442-449), column override (452-456), envelope
backfill (457-466), window backfill (467-472), consumer build + binding (473-478), window/label coherence (479-488),
roster gate + honest-blank partition (489-546), slot reconcile (548-551), no-op-morph partition (553-570),
answerability/data_note resolution (572-625), topology-feasibility note (626-637), cross-domain blanking (638-657),
output assembly + schema gate (658-690). Each block is individually well-reasoned, but the composite is a single
function no one can hold in their head; every new gate lands as another stanza here (the file's own comments show at
least 9 accretions: R1, c14, c16, META-08, A1, A4, card-74, card-52, DEFECT-G). The window-math helpers
(`_lookback_delta`/`_range_delta`/`_calendar_start`/`_backfill_default_window`/`_slots_declared_range`,
lines 25-223) are a self-contained "window backfill" concern living in the same file.

**Why it matters:** this is the hot path of every card emit. At the current accretion rate the next 10 fixes make it
a 500-line function; regression risk per edit is already high (ordering is load-bearing — the file says so itself
at 494-498).
**Recommendation (safe, behavior-preserving):** split into single-purpose modules the way the rest of the repo
already does: `layer2/window_backfill.py` (lines 25-223), `layer2/cross_domain.py` (291-370),
`layer2/answerability.py` (the 572-625 + 601-625 note/soften logic), leaving `_finalize` as a ~60-line pipeline of
named steps. Pure extraction; keep the exact call order.

### 2. HIGH — `layer2/gates.py` bundles four unrelated gate families in one 837-line module
**Files:** `layer2/gates.py:22-113` (metadata byte-identity gates), `139-675` (honest-blank walls — 8+ rules),
`689-774` (`gate_data_instructions`), `777-837` (`gate_roster`); mid-file `import re as _re` at line 146 marks the
concatenation seam.

`enforce_honest_blank` (510-647) alone is ~138 lines orchestrating 9 wall rules, each of which is its own
data-driven policy (`_quantity_mismatch` 255-335 is itself ~80 lines with 5 evidence tiers). The module footer
(roster gate) has nothing to do with the header (byte-identity). The owner's atomic-structure rule ("one
single-purpose file per concern; each layer a folder of small pieces") is violated in exactly the place where it
would pay off most — these walls are the fabrication-prevention core and are edited constantly (the comments cite
c40/c42/c47/c49/c54/c55/c57/c59/c61/c65/c72/c78/c81...).
**Recommendation (safe):** `layer2/gates/` package: `metadata.py` (gate/enforce/free), `honest_blank/` (one file
per wall, mirroring the existing `swap/` micro-gate pattern which proves the team likes this shape),
`data_instructions.py`, `roster.py`, with `gates.py` kept as a barrel re-export (the `consumer_binding/__init__.py`
barrel at `layer2/emit/data/consumer_binding/__init__.py:20-36` is the in-repo precedent).

### 3. HIGH — data access: one `psql` subprocess per query, f-string SQL, repeated per-card catalog reads
**Files:** `data/db_client.py:12-21` (shared root — `subprocess.run(["psql", ...])` per call, no parameterization);
consumed heavily by the layers: `layer2/catalog/catalog_row.py:5-20` (7 separate `q()` calls per card),
`layer2/build.py:20-22` + `:730` (`_page_card_ids` re-queried inside `run_card` for every card with the same
`page_key`), `layer2/swap/candidates.py:52,71-78` (2-3 queries per card), `layer1b/resolve/has_data.py:34-38,105-108`
(UNION-ALL built by f-string over table names), `layer1b/basket/col_dict.py:18-19,42-47`,
`layer1a/db_reads/*` (5 readers). Values are spliced with `$a$...$a$` dollar-quoting (`layer2/build.py:22`,
`layer2/swap/candidates.py:52,73`) or bare interpolation (`col_dict.py:45` `LIMIT {n}`).

**Why it matters:** a single L2 page fan-out (≈20 cards × concurrency 4) spawns on the order of 200+ short-lived
`psql` processes (fork/exec + TCP connect + auth each) — measurable page latency, PID/conn churn, and brittle
behavior under load; this is a scaling wall for "enterprise production". The `$a$` quoting is also an injection
hazard by convention only (safe today because inputs are DB enums/ids, but nothing enforces that — a future caller
passing user text breaks it).
**Recommendation (risky — hot path, but behavior-preserving):** `db_client.q()` already has `pg_connect()`
(psycopg2) beside it; move `q()` onto a pooled psycopg2 connection with real parameter binding, and memoize the
page-scoped reads per run (`_page_card_ids`, `read_card_titles`, `read_page_specs` are identical for all cards of
one run). No caller changes needed if `q()` keeps returning rows of strings.

### 4. MEDIUM — `endpoint_registry` is a hardcoded snapshot while two sibling docstrings claim it is "derived"
**Files:** `layer2/emit/data/endpoint_registry.py:8-18` (`_FALLBACK = [...]`, `PAGES = _FALLBACK` — nothing is
parsed); `layer2/emit/data/consumer_binding/__init__.py:16-18` and
`layer2/emit/data/consumer_binding/screen_map.py:3-5` both state endpoint truth "comes from endpoint_registry,
which parses ems_backend's OWN `_PAGES` route table, so this follows ems_backend automatically (no drift)".

That derivation does not exist; the variable is even named `_FALLBACK` as if a primary source were wired. When
ems_backend adds/renames a WS route, the AI's CLOSED SET (`{{LIVE_ENDPOINTS}}` in the system prompt,
`emit.py:172-173`) silently drifts — the exact "power-quality-history straggler" failure the file's own header
cites as its raison d'être. Also in tension with the DB-driven-config principle (this is a code list, not a row).
**Recommendation (safe):** either actually derive (import ems_backend's route table, or mirror it into a
cmd_catalog row with this list as the code-default fallback — the established knob pattern), or at minimum fix the
two lying docstrings and add a parity test against ems_backend's routes.

### 5. MEDIUM — DB knobs frozen at import time in exactly the modules that claim live editability
**Files:** `layer2/gates.py:14-15` (`_CHROME = cfg("gates.chrome_markers", ...)`),
`layer2/swap/candidates.py:19` (`POOL_VERDICTS`), `:22` (`_AFFINITY_MIN_TOK`),
`layer2/swap/gate_force_renderable.py:30` (`FORCED_SWAP_CONFIDENCE`),
`layer2/emit/data/consumer_binding/screen_map.py:12` (`_PAGE_TAIL_ALIAS`),
`layer2/emit/data/consumer_binding/domain.py:15` (`RETIRED_ENDPOINTS`),
`layer2/catalog/card_grid_size.py:5` (`DEFAULT_VIEWPORT`).

Everywhere else the codebase deliberately reads `cfg()` per call (`_axis_chrome_const_segs()` in the same
`gates.py:378-384`, every `quantity_class` accessor, `coherence._families()`, ...). These seven are module-level
snapshots: in the long-running host, editing the row does nothing until a process restart — silently divergent
from the "edit a row, no code change" contract stated in the adjacent comments ("editable DB rows, not code
lists", candidates.py:8-9). Worse, if the DB is down at first import, the code default is frozen even after the DB
recovers.
**Recommendation (safe):** wrap each in the same accessor-function pattern the neighbors already use. Behavior
identical except knob edits now take effect.

### 6. MEDIUM — prompt composed by unverified string surgery; silent no-op on drift
**Files:** `layer2/emit/emit.py:176-181` (ROSTER marker cutting — assumes `_ROSTER_END` is followed by exactly one
newline: `out[e + len(_ROSTER_END) + 1:]`), `:192-193` (morphmap envelope rewrite —
`out.replace('"exact_metadata":{"_morphed":[]}', '"morphs":{}')` keyed on an exact byte-substring of
`layer2/prompts/data_instructions_v2.md:117`), `:172-173` (`{{LIVE_ENDPOINTS}}`/`{{RETIRED_ENDPOINTS}}`
substitution with no presence check).

The comment at 184-191 documents that this exact class of failure already happened once (the envelope contradiction
made morph-map "never actually activate" while everyone believed the flag worked). If the .md envelope line is ever
reflowed/pretty-printed, the replace silently no-ops again, the model sees a contradictory contract, and the only
symptom is degraded emissions. Same for a marker-line edit around the ROSTER block.
**Recommendation (safe):** after each substitution, assert the marker/old substring is gone (and the replacement
present); on failure, `obs.failures.record` + fall back loudly. Longer term: move the envelope line into a
placeholder (`{{OUTPUT_ENVELOPE}}`) so composition writes, never rewrites.

### 7. MEDIUM — positional-list row contracts with `len(c) > N` guards across ≥8 consumers
**Files:** producer: `layer1b/resolve/asset_candidates.py:100-125` (12-element list; documented shape only in a
docstring). Consumers indexing by magic number: `layer1b/resolve/asset_resolve.py:69,94-99,141-145,199-201`
(`c[0]`, `c[1]`, `c[5]`, `c[6]`, `c[10]`, `len(c) > 10` guards), `asset_candidates.as_asset:155-163`
(`len(c) > 6/7/8/9/10/11` ladder), `ambiguous_candidates.py:31,44` (`c[2]`, `c[6]`), `no_data_gate.py:31-34`
(`c[0]`, `c[5]`, `c[6]`), `class_from_subject.py` (`c[5]`), `empty_fallback.py` (`c[6]`),
`compare/detect.py`/`resolve_names.py` (`r[0]`, `r[1]`). Same pattern at scale in
`layer1a/db_reads/cards_intent.py:36-66` (`r[0]`..`r[31]`, 32 positional columns).

Adding one column to the registry row = shotgun edits across 8 files; a missed `len` guard silently changes
semantics (`as_asset` falls back to `bool(c[2])` for `has_data` when the row is short — a wrong answer, not an
error). The comment at `asset_candidates.py:107-108` even has to promise "every consumer indexes ≤9 or len-guards"
— a contract enforced by grep.
**Recommendation (breaking internal contract, mechanical):** make `asset_candidates()` return dicts (or a
NamedTuple) and delete the guards; `as_asset` becomes a projection. One-pass change, fully covered by the existing
882-test suite.

### 8. MEDIUM — 71 silent `except Exception` fail-opens, only 2 wired to failure telemetry
**Files:** grep count across the three layers: 71 `except Exception` sites; only
`layer1a/story_builder.py:39-45` and `layer1b/build.py:31-35` record to `obs.failures`. Representative silent
swallows: `layer1b/resolve/asset_candidates.py:96-97` (`_alias_map` → `{}` on ANY error),
`layer1b/resolve/asset_resolve.py:63-64` (`_pcc_alias_index` → `{}`), `layer2/emit/equipment_facts.py` (every
accessor → `''`), `layer2/emit/asset_facts.py` (both fact lines → `''`), `layer2/emit/emit.py:119-120`
(recovery library → "unavailable"), `layer2/build.py:87-88, 242-243`.

The fail-open convention is deliberate and mostly correct (per-leaf degradation). The smell is that a *programming
error* (schema rename, typo introduced in refactor) is indistinguishable from a transient outage: aliases,
equipment facts, or the recovery library can vanish **permanently and silently** — the exact "silent degradation"
class the project's render-guarantee work exists to kill. `has_data.py:41-53` shows the team already knows the
distinction matters (outage-vs-bad-chunk split) but that discipline exists in only that one file.
**Recommendation (safe):** a 5-line shared helper (`obs.swallow(scope, exc)`) that rate-limited-logs to
`obs.failures`; replace the bare `return '' / {} / ()` bodies with it. No behavior change on the happy path.

### 9. MEDIUM — chrome-marker detection duplicated with drift between gate and producer
**Files:** `layer2/gates.py:14-19` — DB-driven list
`["=>", "function(", "function (", "React.", "onClick", "px solid", "rgba("]` used by `_is_chrome`;
`layer2/emit/metadata/producer.py:129` — hardcoded inline subset `("=>", "function(", "React.", "px solid")`.

The producer's copy is missing `"function ("`, `"onClick"`, `"rgba("` and ignores the `gates.chrome_markers` DB
knob entirely. Consequence today: a morph value containing `rgba(...)`/`onClick` is *applied* by `produce()` and
then *reverted* by the gate — reported as "reverted to default" (a byte-identity violation) instead of
"morph rejected: chrome", polluting the failure taxonomy the sweeps count; and a knob edit tunes only one of the two
walls. Classic copy-paste drift between sibling modules.
**Recommendation (safe):** producer imports `gates._is_chrome` (or hoist `is_chrome` into a shared
`layer2/chrome.py`); one vocabulary, one knob.

### 10. MEDIUM — `quantity_class.py` self-describes as "ONE atomic concern" but bundles five vocabularies, two of them overlapping
**Files:** `layer2/quantity_class.py:1-32` (the "ONE atomic concern" claim) vs contents: unit/name classes
(41-216), semantic families (230-244), **two separate source-role vocabularies** — `_SOURCE_ROLES_DEFAULT`
(266-269, roles `bypass`/`input` with `dedicated` flags, consumed by `source_role_mismatch`) and
`_SOURCE_ROLE_MARKERS_DEFAULT` (287-297, roles `bypass`/`input`/`output`/... consumed by `source_role_of` for
ems_exec via getattr) — time-axis tokens (308), const-source resolution (688-791). Line 697 reaches into a private
API: `from config.app_config import _load`.

The two role maps define `bypass`/`input` twice with different shapes and different DB rows
(`quantity.source_roles` vs `quantity.source_role_markers`); a marker added to one wall does not reach the other,
and nothing says which one a maintainer should edit. The const-source resolver (a DB-lookup concern, not a
classification concern) drags a private `_load` import along.
**Recommendation (safe):** split into `quantity/` package (`classes.py`, `families.py`, `roles.py` — ONE role
vocabulary with both consumers, `const_source.py`); expose a public `all_rows()` on `config.app_config` instead of
`_load`.

### 11. MEDIUM-LOW — dead vocabulary from the deleted name-collision gate still validates/documents itself
**Files:** gate deletion recorded at `layer1b/resolve/asset_resolve.py:170-178` ("REMOVED 2026-07-09").
Leftovers: `layer1b/schema.py:22-30` — validator still accepts `how='collision_gate_fullname'` and a comment still
describes it as "a legitimate RESOLVED-WITH-DATA state"; `layer1b/compare/resolve_names.py:24-26` — still in
`_CONFIDENT_HOW` with an explanatory comment; `layer1b/resolve/confident_pin.py:11-12` — docstring still claims
"Homonyms ... are handled up-front by the name-collision gate in asset_resolve"; stale bytecode
`layer1b/resolve/__pycache__/name_collision.cpython-31{1,2}.pyc` for the deleted source.

No producer of that `how` value exists anymore (grep: only validators/comments). A maintainer reading
`confident_pin.py` will design against a safety net that was deleted three days ago.
**Recommendation (safe):** delete the enum member, the two comments, the docstring sentence, and the stale `.pyc`s.

### 12. MEDIUM-LOW — deliberately-dead device-identity machinery still costs a DB probe and threads unused params
**Files:** `layer1b/resolve/confident_pin.py:24-37` — `device_identity`/`_ident` hardcoded to return `None`
("stable no-op seam"); `layer1b/resolve/ambiguous_candidates.py:28-50` — the whole "pass (b)" (device-identity
collapse) can therefore never fire, yet `live = tables_with_values([...])` (line 31) still runs a real (cached)
DB probe whose result is only consumed inside the dead branch, and the O(n²) `dupes` scan sits ready; `cands`
parameter is unused in `dedup_candidates` and `confident_pin(cand_row, cands)`.

Documented-dead code is better than mystery-dead code, but three files carry the scaffolding and one pays a DB
read for a branch that provably cannot execute.
**Recommendation (safe):** collapse pass (b) to a comment pointing at the git history; drop the unused `cands`
params; keep `device_identity` as the one documented seam if desired.

### 13. MEDIUM-LOW — `compare/detect.py` module-global cache can permanently cache a partial alias index
**Files:** `layer1b/compare/detect.py:26-41` — `_ALIAS_IDX` is populated by `setdefault` inside the `try`; an
exception mid-iteration (tunnel flap during the row stream) leaves a **partially filled** dict that line 33
(`if _ALIAS_IDX: return _ALIAS_IDX`) then serves for the life of the process.

This is precisely the cache-poison class the project already fixed for `panel_members` with never-cache-empty +
`TTLCache` (`layer1b/resolve/has_data.py:13-16` uses `data/ttl_cache.py`); this sibling cache didn't get the
treatment. Impact is bounded (compare-by-alias silently degrades until restart) but the failure mode is proven in
this codebase.
**Recommendation (safe):** build into a local dict, assign on success only, and/or reuse `data.ttl_cache.TTLCache`
like `has_data.py`.

### 14. MEDIUM-LOW — column-name→unit logic triplicated with observable drift
**Files:** `layer1b/basket/describe.py:36-48` (`_UNITS` suffix table + prefixes; includes `("_deg", "°")`);
`layer2/resolve/column_override.py:35-48` (`_col_unit` — self-declared "mirrors layer1b.basket.describe.unit,
kept dependency-free"; already missing `_deg` and the `frequency` prefix); `layer2/quantity_class.py:41-93`
(unit→class map, a third spelling of the same suffix knowledge).

The "kept dependency-free" mirror is the smell: a new column suffix (say `_kva_r`) must now be taught in three
places or the slot-quantity guard and the basket disagree about the same column's unit — which manifests as
spurious honest-blanks or missed guards, not as an error.
**Recommendation (safe):** `column_override` imports describe's suffix table (it is in-process, same repo — the
dependency is not a real cost); `quantity_class` stays separate (different concern: class, not unit string) but
should source the suffix list from the same constant.

### 15. LOW — `gate_template_dedup` is logically dead; the micro-gate pattern over-rotated
**Files:** `layer2/swap/decide.py:26-30` chains `gate_no_dup.ok(...)` AND `gate_template_dedup.ok(...)`;
`layer2/swap/gate_no_dup.py:4-7` already forbids `template_card_ids` (`forbidden = set(template_card_ids) | ...`),
so `gate_template_dedup.py` (7 lines) can never change the outcome.

Harmless at runtime, but it is the mirror-image violation of the atomic rule (a pointless one-line file), and it
misleads: a reader auditing "where is the template protected?" finds two answers, one fake.
**Recommendation (safe):** delete `gate_template_dedup.py` (or fold the explicit intent into a comment on
`gate_no_dup`).

### 16. LOW — dead no-op statement in the L2 output validator
**Files:** `layer2/schema.py:23-25` —
`if out.get("$ctx") is not None and not out.get("is_group_marker", True): pass` — a condition computed and
discarded. Either a validation was intended and lost, or it is clutter; either way it reads like a bug.
**Recommendation (safe):** delete, or implement the intended `$ctx`-consistency check.

### 17. LOW — stale docstrings that contradict live behavior (morphmap, split rule)
**Files:** `layer2/emit/morphmap/producer.py:2` — "[ITEM 18 PREP — parallel path, NOT wired into the live emit]"
while `layer2/emit/emit.py:148-194` composes it into the live system prompt behind `emit.morphmap_mode` and
`layer2/build.py:387,403-413` routes its output; `layer2/emit/morphmap/mode.py` (correct, current) contradicts its
sibling's header. Also finding-4's two "parses ems_backend" docstrings (counted there).
**Why it matters:** in a codebase whose comments are the de-facto design record (see finding 20), a stale header is
actively harmful — the next engineer will "wire it in" a second time or refuse to trust the flag.
**Recommendation (safe):** update the two headers.

### 18. LOW — `_load_prompt` copy-pasted 4×; strip-non-alnum `_norm` copy-pasted 4×; camelCase splitter 3×
**Files:** `_load_prompt`: `layer1a/route.py:29-31`, `layer1a/story_builder.py:11-13`,
`layer1b/resolve/asset_resolve.py:35-37`, `layer1b/basket/column_basket.py:30-32` (identical 3 lines, different
`_HERE` anchors). `_norm` (strip `[^a-z0-9]`): `layer1b/resolve/asset_resolve.py:40-42`,
`layer1b/guardrail/spelling_recovery.py:13-14`, `layer1b/compare/discriminators.py:11`,
`layer2/quantity_class.py:725-726`. Camel-split regex `[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z0-9]+|[A-Z]+`:
`layer2/quantity_class.py:37`, `layer2/gates.py:246`, and inline again at `layer2/gates.py:463`.
**Why it matters:** small, but normalization functions are correctness-bearing here (name matching decides asset
pins); four copies invite one being "improved" alone.
**Recommendation (safe):** `llm/prompts.py::load(dir, name)` and a shared `textnorm.py` (`norm_key`, `camel_tokens`).

### 19. LOW — knob-truthiness parsing re-implemented six ways
**Files:** `layer1a/route_schema.py:31` (`_ON` tuple), `layer1b/resolve/answer_schema.py:33` (`_ON`),
`layer2/emit/morphmap/mode.py:24` (`_OFF`), `layer2/emit/equipment_facts.py:18` (`_OFF`),
`layer1b/resolve/asset_resolve.py:58` (inline off-list), `layer1b/resolve/asset_candidates.py:73` (inline
off-list). Two comments even say "same truthy vocabulary as config/app_config.py `_cast('bool')`" — i.e. the
canonical parser exists and is being re-derived by hand.
**Recommendation (safe):** `cfg_bool(key, default)` in `config/app_config.py`; replace the six sites.

### 20. LOW — changelog-style comment density obscures control flow in the hot files
**Files (measured):** `layer2/build.py` — 178 `#` lines + 93 docstring lines of 779; `layer2/gates.py` — 135 + 146
of 837; `layer2/quantity_class.py` — 201 + 120 of 791. The narrative encodes incident history (card numbers, audit
ticket ids, dates, prior defect reconstructions) rather than invariants — e.g. `gates.py:276-283` is a 7-line
comment about one commit's collateral; `quantity_class.py:59-93` is ~35 lines of comment for 6 dict keys.
**Why it matters:** the *why* is genuinely valuable (this codebase's biggest strength is that decisions are
explained), but incident forensics belong in `docs/`/commit messages; inline they push related code apart (the
`_finalize` read spans 3 screens of prose per screen of code) and they rot (findings 11, 17 are comments that
already lie).
**Recommendation (safe, judgment):** adopt a convention — inline comments state the invariant + a short tag
(`[c40]`), the reconstruction moves to `docs/`; apply opportunistically during the finding-1/2 splits.

### 21. LOW — `user_message._build` is a 227-line prompt assembler with a three-way prose branch inline
**Files:** `layer2/emit/user_message.py:190-417` — skeleton selection + loud-NULL check (200-218), endpoint hint
(221-229), fact lines (256-262), basket + probable blocks (263-285), roster/panel-aggregate/no-fields three-way
instruction prose (320-362), morphmap header flip (363-381), slot catalog + swap candidates (385-416). The file is
arguably one concern ("build the user message") so this is tension, not violation; but the three ★-branch prose
blocks (40+ lines of instruction text inside Python string literals) drift-race the system prompt `.md` they must
agree with (the A5/A6a comments record two such past disagreements).
**Recommendation (safe):** move the three instruction blocks into `layer2/prompts/` .md fragments loaded like the
system prompt, so prompt text lives with prompt text.

### 22. LOW — minor import hygiene drift
**Files:** `layer2/build.py:29` — `import re` inside `_lookback_delta` although `re` is imported at module top
(line 5); `layer1a/parse/granularity_reconcile.py:37` — a module-level `from config.asset_granularity import ...`
placed mid-file between two function defs; `layer2/gates.py:146` — `import re as _re` mid-file;
`layer2/emit/data/consumer_binding/domain.py:8` — `_HISTORY_BY_DOMAIN = HISTORY_BY_DOMAIN` pointless alias;
`layer2/emit/slot_catalog.py:22-24,40-41` stray triple blank lines. (Function-level imports done for cycle
avoidance are deliberate and fine — these five are just drift.)
**Recommendation (safe):** tidy in passing.

---

## What is clean (worth saying)

- **layer1a** as a whole: `route.py`'s fail-closed contract, the clamp modules, `catalog_compress.py`, and
  `page_key_fallback.py` are exemplary — small, single-purpose, DB-knobbed per call, honest about ambiguity.
- **layer1b's outcome modules** (`pinned_skip`, `no_data_gate`, `empty_fallback`, `confident_pin` structure,
  `retry_one`, `spelling_recovery`) are the atomic-structure rule done right.
- The **fail-open vs fail-closed asymmetry** (route raises, stories/basket degrade, resolver degrades-to-picker)
  is consistent and documented at each site.
- `layer2/emit/morphmap/mode.py` centralizing the flag decision consumed by three call sites is the right shape
  (only its sibling's docstring is stale).
- No committed `.pyc` files (bytecode exists only in untracked `__pycache__`); the earlier map's claim that they
  were committed is wrong.
