# pipeline_v48 — Unused-code & Duplication Audit (consolidated) — 2026-07-12 ~03:45 IST

**Scope:** `backend/layer2/pipeline_v48` (the active pipeline), verified against the ENTIRE BFI tree
(all pipeline versions v45–v49, frontend, `/home/rohith/CMD_V2`, systemd units) + the live `cmd_catalog` DB.
**Method:** independent static analysis (AST import graph over 528 modules / 3,102 top-level functions;
vite import-graph over 145 web files incl. `import.meta.glob` barrels; word-boundary + camelCase + DB-row-text
cross-reference for every candidate), reconciled with the parallel refactor-campaign docs
(`docs/findings/refactor_20260712/*`, `docs/audit_2026-07-12/*`) written earlier tonight.
**Nothing was deleted or modified by this audit. Recommendations only.**

> ⚠ **Concurrency note.** A parallel session was actively landing refactor-campaign changes while this audit ran
> (288 source files touched tonight: `obs/` wiring, `replay/`, `admin/`, `validation/`, `tools/payload_diff/`,
> `config/policy_read.py`, `db/fix_orphan_knobs_20260712.sql`, …). Everything created/modified tonight
> (2026-07-12 00:30–03:30) is treated as **concurrent WIP and explicitly excluded from unused/dead claims**.
> Findings below were re-verified against the tree state at ~03:30.

---

## 1. Unused files

**Verdict: essentially none — the tree is unusually clean at file level.**

- **Python (528 modules):** 306 reachable from live services (`host/server.py` :8770, `copilot/server.py` :8772),
  82 reachable from `__main__` ops scripts, 131 test-tier. The 9 statically-orphan candidates all REFUTED:
  `llm/providers/openai_compat.py` (loaded by name: `llm/providers/__init__.py:41` `import_module(f"llm.providers.{name}")`),
  `tools/seed_quantity_vocab.py` (documented guard-less ops script), `validation/*` (tonight's WIP with its own CLI/report entries).
- **Frontend (145 files under `host/web/src`):** 144 reached from `main.tsx` once the two eager glob doors are honored
  (`cmd/registry.tsx:27` globs `./fill/*.tsx`; `cmd/components/index.ts:8` globs `./*.ts(x)`). The single "unreached"
  file is `vite-env.d.ts` (ambient TS types — not code). **Zero dead React files.**
  The committed editor temp file `App.tsx.tmp.4127533.*` (frontend F15) was already removed tonight.
- **Superseded directory:** `ems_compat/` (0 py files; historical SQL template + COVERAGE.md truth-table) — move to
  `docs/` (refactor dead-code F2).
- **Cruft in the live tree** (dead-code F8, re-verified): `db/seed_endpoint_resolve_policy.sql.retired`,
  root `err.log` (0 bytes), `host/host_restart.log` (~217 KB, growing), `host/vite_restart.log`,
  9 × `copilot/*.png` screenshots, `copilot/logs/`. NOTE `copilot/copilot_index.sqlite` is the LIVE retrieval
  index — relocate only together with its path config.
- **Doc rot:** `README.md:3-13` references four deleted paths (`workers/`, `frames/`, `db_build/`, `run/assemble`)
  and five relocated design docs (dead-code F1).

## 2. Unused functions

Excluded by design: 1,023 pytest `test_*` functions (name-discovered), all of tonight's WIP folders.
14 public *methods* flagged statically were all refuted (dynamic/attribute dispatch) — methods are clean.

**Consolidated from the campaign (verified):**
- **15 dead import names + 3 dead locals** across 11 files (dead-code F3; each seam-verified — keep
  `fill._deriv` and the `host/server.py` noqa re-exports, they are live test seams).
- **6 unwired backend2-parity derivation functions** (dead-code F4): `mean_active_power_kw`,
  `active_power_loss_kw_gated`, `active_power_loss_pct_gated`, `specific_energy_consumption_ratio`,
  `i_thd_peak_pct`, `io_resolution`. The only dispatch door is the closed dict in
  `ems_exec/derivations/registry.py`; the DB expression AST (`evaluate.py`) cannot name python fns.
- **10 dead public helpers** (dead-code F5): `swappable_ids`, `meaningful_probe`, `panel_member_tables`,
  `metadata_paths`, `endpoint_registry.is_live`, `_db.has_column`, `classify_columns`, `table_fingerprint`
  + the 4-candidate config introspection quartet (`all_class_defaults`, `all_page_classes`, `all_nameplates`,
  `all_page_types`).

**NEW in this audit (each verified: zero call sites tree-wide, zero camelCase/DB-row-text hits, zero CMD_V2 hits):**

| # | Function | Location | Note |
|---|----------|----------|------|
| N1 | `i_thd_pct` | `ems_exec/derivations/power_quality.py:47` | 7th unwired parity fn — same class as F4 (F4 caught only `i_thd_peak_pct`) |
| N2 | `nominal_voltage` | `ems_exec/derivations/nameplate.py:59` | dead **and** a duplicate — the registry wires `nominalVoltageLN` → `voltage.nominal_voltage_ln`, a second implementation of the same formula |
| N3 | `pq_limits` | `config/nameplates.py:238` | seeded-knob accessor, no consumer (seed comment names `services/mfm_config.py` — an ems_backend file that never calls it) |
| N4 | `capacity_utilization` | `config/nameplates.py:251` | parity-port accessor, no consumer |
| N5 | `trend_deadband` | `config/topology_policy.py:34` | accessor + its `topology.trend_deadband` row: no reader of either |
| N6 | `rating_vocab` | `config/viewer_policy.py:68` | staged for the kitpreview resolver (knob OFF); today no consumer — `page_type_for()` in the same module IS live |
| N7 | `fingerprints` | `config/schema_map.py:46` | referenced only by a comment in `grounding/schema_fingerprint.py:25` |
| N8 | `all_policy` | `config/quality_policy.py:26` | same introspection family as the F5 quartet |
| N9 | `bindable` | `config/derivation_binding.py:31` | word appears only in docstrings elsewhere |
| N10 | `django_db`, `data_db` | `config/databases.py:34,60` | unadopted accessor pair (tree hits are pytest's own `django_db` fixture, unrelated) |
| N11 | `reset_cache` ×3 | `registries/neuract/topology.py:84`, `registries/neuract/meters.py:101`, `ems_exec/executor/recipe.py:155` | cache-reset hooks with zero callers (not even tests) — wire into test fixtures or drop |
| N12 | `_last_seg`, `_is_dict_subtree` | `grounding/default_assemble.py:142`, `grounding/role_scrub.py:153` | dead private leftovers |

## 3. Unused APIs

**Endpoint ↔ caller cross-match — no unused endpoints, no broken references:**

| Server | Endpoint | Consumer |
|---|---|---|
| host :8770 | `GET /api/health` | ops scripts (`tools/stack_monitor.sh`, admin) |
| host :8770 | `GET /api/assets`, `GET /api/site`, `POST /api/frame`, `POST /api/run` | `host/web/src` (all four fetched) |
| copilot :8772 | `GET /copilot/health` | ops |
| copilot :8772 | `GET /copilot/starters`, `POST /copilot/suggest` | PromptBar FE |
| copilot :8772 | `GET /` index | copilot's own demo page |
| admin (tonight's WIP) | `/admin/api/*`, `/replays`, `/replay` | `host/web/src/admin/api.ts` |

**Dead wire *fields* (the real unused-API surface — api-design L4 / frontend F14, verified):**
`frames` (always `{}`), `live_frame` (always `None`), `frame_status`, and vestigial `sb_base` are still served in
every `/api/run` response and threaded through `types.ts` → `App.tsx` → `CardGrid` → `CmdCard` → all ~30 fill
functions (~60 LOC of dead plumbing that actively misleads — three modules still document "live frame overrides
the seed"). Staged removal plan is in frontend F14.

## 4. Duplicate utilities

Consolidated (duplication.md D1–D4, D7, D8, D12 — spot-verified): the duplication in v48 is **helper-level, not
file-level** (my content-hash scan found no whole-file copies):

- **D1** pooled psycopg2 neuract door duplicated wholesale: `ems_exec/data/neuract.py` vs `registries/neuract/_db.py`
  (byte-identical `_key`/`_conn`, same docstring) → proposed `data/neuract_pool.py`. *Highest leverage: tunnel-flap
  fixes must currently land twice.*
- **D2** `data_quality_policy` reader boilerplate re-implemented per config module + **`_esc` defined 13× in
  `config/` (18× tree-wide)** → `config/policy_read.py` (**landed tonight** — repointing in progress).
- **D3** fail-open `_cfg` shim ×12 + byte-identical `_cfg_num` ×2 → `config/failopen.py`.
- **D4** float-coercion `_f` ×6 byte-identical in derivations (+8 variants, several with deliberately divergent
  semantics that must NOT be merged — documented list in D4).
- **D7** psql boolean-cell parse ×5 → `pg_bool()` in `data/db_client.py`.
- **D8** `_load_prompt` ×4 (+2 inline variants with an `errors="replace"` robustness divergence) → `llm/prompt_load.py`.
- **D12** psql row/JSON guard idioms ×7/×5 → `first_row()`/`json_cell()` in `data/db_client.py`.

## 5. Duplicate React components

No duplicate component *files* (vite graph + hash). Snippet/intra-file duplication (frontend.md, verified):
- **F3** `date-wiring.ts` copied across 7 fill folders (two byte-identical), `DateWindow` type re-declared 8×.
- **F4** `sanitizeHistory`/`sanitizeHealth` implemented twice with **divergent guard behavior** for the same CMD_V2
  contract (latent bug, not just duplication).
- **F5** `unavailableHistory`/`unavailableHealth` structured-empty VMs duplicated (one cached, one not).
- **F6** `/api/site` polling loop hand-rolled twice with different intervals; `let alive` fetch idiom ×4.
- **F8** Spark/Mag SVG icons pasted 3×/2×; **F9** three error-boundary classes; **F10** honest-blank markup ×3.
- **F16** RTM heatmap body implemented twice (`compose.tsx` HeatmapCard vs `RtmComposite` HeatmapBody).

## 6. Duplicate SQL

- **Content level: clean.** Zero hash-identical inline SQL strings across files; zero duplicate `CREATE TABLE`
  across `db/*.sql` (verified over 54 inline statements + all seed/schema files).
- The real issue is **mechanics duplication**: f-string SQL + copy-pasted `_esc` at 18 sites (database F9, same
  fix as D2/R2), and the same catalog-read row-guard idiom ×7 (D12).
- Hygiene: `db/seed_schema_and_endpoints.py` TRUNCATEs non-transactionally from the flaky tunnel (database F12);
  75 hand-applied SQL files have no migration ledger (database F2 → R9).

## 7. Duplicate prompts

- **Content level: clean.** 712 long strings hashed — zero cross-file duplicates; 8 prompt `.md` files — all unique;
  v1 prompt trio (swap/metadata/data_instructions.md) properly deleted.
- Residue: `llm.prompt_v2` keys still stubbed in two test fixtures + 2 stale comments (dead-code F7);
  prompt-loader duplicated ×4 (D8); `llm.no_retry_kinds` row parsed identically in two places (D10).
- The prompt-fragment architecture is sound: enum lines are DB-interpolated so prompt and clamp can't drift
  (mappings-addendum).

## 8. Duplicate business logic

Verified real duplications (beyond utilities):
- **Post-fill rescue trio** shares `_honest_blanked` ×3 / `_blank` ×2(+4) / window-fill idiom ×2 (D5) —
  fabrication-guard-adjacent; a matcher fix must land 3×.
- **Boolean-flag vocabulary drift** (D6): `data/equipment/edges.py:42` and `layer2/emit/metadata/asset_3d.py:146`
  are missing `"t"` from the truthy set — a DB operator writing `t` flips some knobs but not others.
  *This is a latent behavior divergence, not just cosmetics.*
- **`_norm` asset-match key ×3** inside layer1b (D9) — desync risk for the collision-gate class of bugs.
- **`card_handling` read tripled** (D11).
- **Response assembly drifted** (api H4): the multi-asset path never applies the prompt-derived date window
  ("compare A and B last week" fills with `date_window=None`) — **already a real bug**, extract one `response_envelope()`.
- **NEW:** `nameplate.nominal_voltage` vs `voltage.nominal_voltage_ln` — same formula, two homes, only one wired (N2).

Verified **non**-duplicates (do not chase): power vs energy derivations; copilot's deliberate zero-coupling twins;
`services/dict_merge.py` documented twin; validate/ vs grounding/ (4 distinct "has data" semantics, documented);
tools/scripts import the harness rather than re-implementing (full list in duplication.md).

## 9. Unreachable code

- **Syntactic: clean.** AST scan of all 528 modules: zero statements after return/raise, zero `if False` blocks.
  (`layer2/schema.py`'s dead `if…: pass` was removed tonight.)
- **Semantic unreachability that matters:**
  - The executor **budget branch is dead**: `host/exec_cards.py` `as_completed()` has no `timeout=`, so the
    `_FTimeout` path can never fire and the 45 s budget is decorative (audit H5 → R1 — this is also the
    tunnel-flap outage amplifier).
  - The **7 unwired derivation functions** (F4 + N1) and the **11 unwired config accessors** (N3–N10) are
    unreachable by construction (closed registry dict / no caller).
- **Dormant-by-config (deliberate — do NOT treat as dead):** equipment `topology`/`derivations`/`kitpreview`
  knobs staged OFF; the `lt_panels` branch of the derivation registry (documented as the worked example of the
  DB-keyed mechanism); adoption flags whose code defaults are off while the DB rows hold the certified "on"
  (config-centralization F8 — owner call to flip defaults).

## 10. Unused database tables

Live `cmd_catalog` now has **66 tables** (the `obs_*` ×9 and `prompt_*` ×3 families landed tonight — WIP, wired to
`obs/query.py` + the prompt-corpus seeds). Full classification run (word-boundary grep per table across the whole
tree incl. CMD_V2 + row counts + reader-line inspection):

**Zero runtime readers anywhere (write-only / seed-only):**

| Table | Rows | Written by | Status |
|---|---|---|---|
| `endpoint_policy` | 12 | `db/seed_schema_and_endpoints.py` | known dead (dead-code F6); mappings-addendum: do **not** wire it to `endpoint_registry` — shapes differ |
| `band_policy` | 6 | `db/seed_band_policy.sql` | **NEW** — no reader in v48/v47/CMD_V2/anywhere |
| `limit_override` | 4 | `db/seed_round2_config.sql` | **NEW** — round2 config surface, unwired |
| `live_window_policy` | 3 | `db/seed_round2_config.sql` | **NEW** — round2 config surface, unwired |
| `card_rendering` | 145 | `db/seed_roster_recipes.sql` (2026-07-06) | **NEW** — "Inventory B facts" FE-render inventory; authoring-time only |
| `card_render_map` | 70 | `db/seed_asset_render_map.sql` | **NEW** — only a filename-convention comment in `dg-operations-runtime.tsx:9` references it |

**Readers only in superseded v47 (deprecation candidates once v47 retires):** `payload_shapes` (10 rows),
`nameplate_config` (13), `derived_metrics` (45 — `copilot/build/entities.py:73` explicitly declines it as a source).

**Write-only by documented design (keep):** `registry_lt_mfm_incoming` (93 rows — "mirrored anyway for completeness",
`scripts/sync_neuract_registry.py:32`).

**All 53 remaining tables have live v48 readers** — including the `registry_*` mirror family, which is read via
dynamically-composed names (`data/registry/lt_mfm.py` `{p}device_mappings`/`{p}asset`/… joins), so naive grep
under-counts them. `obs_v_recent_errors` is 0-row but wired (new obs layer).

## 11. Unused configuration

- **5 orphaned `app_config` rows** (config-centralization F3) — **fixed tonight** by
  `db/fix_orphan_knobs_20260712.sql`: `llm.prompt_v2` + 3 `flags.*` deleted; `ems_backend.frame_budget_s`
  **renamed** to `ems_exec.card_budget_s` (F4's key drift: the seeded row used the old name while the only reader
  reads the new one — editing the row now actually moves the budget).
- **NEW — knob rows/tables whose only reader is a dead accessor** (dead-end config an operator can edit with no
  effect): `viewer.rating_vocab` (`__knob__` row, read only by dead `rating_vocab()`), `topology.trend_deadband`
  (read only by dead `trend_deadband()`), the PQ-limit rows behind dead `pq_limits()`, plus the entire
  `limit_override` / `live_window_policy` / `band_policy` tables (§10). Decide wire-or-retire per row family.
- **46 "suspicious" dotted keys all cleared** — read via dynamic prefixes (`cfg(f"vocab.{name}")`,
  `cfg(f"fab_guards.{name}")`, `cfg(f"llm.timeout.{stage}")`, FE `layout_fe` section) — no dead flags in code
  (dead-code "cleared" list; independently consistent with my scan).
- Remaining owner calls (config-centralization, re-confirmed open): F6 three knob homes (app_config vs
  data_quality_policy vs `__knob__` sentinel rows), F7 endpoint defaults scattered per consumer,
  F8 certified-on flags defaulting off in code.
- FE: hardcoded `/home/rohith/CMD_V2` alias path + undeclared deps = FE builds only on this machine (react F2).

---

## Safe refactoring plan (ordered; nothing deleted by this audit)

**Ground rules:** park removals in `archive/` (house convention) rather than deleting; run the offline test tier +
`npm run ssr-gate` after each batch; do not touch tonight's WIP (`obs/`, `replay/`, `admin/`, `validation/`,
`tools/payload_diff/`); coordinate with the parallel session — items marked *landed tonight* are already moving.

1. **Zero-risk deletions** (mechanical, test-guarded): the 15 dead import names + 3 dead locals (F3);
   `llm.prompt_v2` fixture keys + 2 stale comments (F7); README path fixes (F1).
2. **Dead-helper batch** (functions with zero references — N1–N12 + F5): delete or archive in one commit per
   folder so git history stays legible. Two decisions needed from the owner first:
   *(a)* the **parity-port seven** (F4 + `i_thd_pct`): wire via `derivation_binding` rows + registry descriptors
   if the backend2-parity intent stands (AI-first rule: a row edit, not new code), else archive;
   *(b)* the **config-accessor eleven** (N3–N10): wire-or-retire together with their orphaned knob rows (§11) —
   retiring the accessor but keeping the row (or vice versa) recreates the dead-end.
3. **Dead DB surface**: rename the six reader-less tables' seeds to `.retired` (house pattern:
   `seed_endpoint_resolve_policy.sql.retired`) and record row snapshots in `archive/` before dropping anything;
   keep `registry_lt_mfm_incoming`; revisit the three v47-only tables when v47 is formally retired.
4. **Dedup homes** in duplication.md's order: D2 (*landed tonight*) → D3 → D4 → D7/D8/D9/D10/D11/D12 →
   D5 (rescue trio, behind the DEFECT-56 tests) → D6 (boolean-vocab unification — the one *intentional* behavior
   repair, own commit) → D1 (neuract pool door — hot path, do last, full 882-suite + live sweep after).
5. **Dead wire fields** `frames`/`live_frame`/`sb_base`: follow F14's staged 3-step (grep-confirm sole producer →
   drop props/params → keep `Card.endpoint`/`refetch`). Pairs with the `response_envelope()` extraction that also
   fixes the multi-asset date-window drop (api H4 — real bug).
6. **Cruft relocation**: `.retired` seed → `archive/`; restart logs → `outputs/` + gitignore; copilot PNGs →
   docs/outputs; `ems_compat/` → `docs/`. (`copilot_index.sqlite` moves only with its path config.)
7. **Unreachable-branch repair** (behavior-affecting, separate from cleanup): make the executor budget real
   (audit R1) — the dead `_FTimeout` branch is the amplifier of the :5433 tunnel-flap outage class.

**Cross-validation note:** my independent AST/xref pass converged with the parallel campaign on every overlapping
finding (same 6 unwired derivations, same dead helpers, same `endpoint_policy` verdict) and added the 12 §2 deltas,
5 reader-less tables, and the dead-end knob rows — high confidence in both directions. Raw analysis artifacts:
session scratchpad `v48_analysis.json`, `v48_reach.json`, `v48_tables.json`, `v48_func_verify.json`.

---

## IMPLEMENTATION STATUS (final — 2026-07-12 ~07:10 IST)

**The plan is fully implemented.** Pass 1 (~04:30): steps 1/2/3/6 + dedup homes D4/D7/D8/D9/D10/D11 + the H4
multi-asset date-window bug; step 7 (executor budget) was implemented by the refactor-campaign session the same
night. Pass 2 (~07:00, after the campaign session went idle): D3 `config/failopen.py`, D6 `flag_on()` (incl. the
intentional `'t'` vocabulary repair in edges.py), D5 `rescue_common.honest_blanked`, D12 `first_row`/`json_cell`
(divergent failure modes preserved as an explicit parameter), **F14 wire-field prune end-to-end** (server +
multi_asset + the whole FE chain; per-card `frame_status` kept), and **D1 `data/neuract_pool.py`** (which also
extends the never-cache-empty schema probe to the registries door — closing the audit-H2 residue there).
The table DROPs were subsequently owner-authorized and APPLIED (~08:00): all six reader-less tables are gone,
their seeds retired/block-commented so every runnable seed stays clean, snapshots in `archive/db_snapshots_20260712/`.
Nothing from this audit remains open.

Verification: per-batch targeted greens throughout; `tsc -b` clean; SSR gate PASS (archived + fresh live
responses); host :8770 restarted on the new tree — full live `/api/run` smoke green (picker path + 4-card
pinned run, prompt-derived last-7-days window, retired fields absent). Full detail →
`docs/findings/refactor_20260712/APPLY_LOG_unused_dupes_audit.md`.
