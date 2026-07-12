# V48 Testing Audit — 2026-07-12 (audit lens: testing)

Scope: `pipeline_v48/tests/` (96 files, 12,978 lines, 883 collected test functions) plus the JS render gates
(`host/web/scripts/`), `copilot/tests/`, and the DB/CI surroundings the suite depends on. All file:line citations
were read during this audit.

## Overall assessment

The suite is unusually strong on assertion quality for a fast-moving AI pipeline: an AST scan over all 883 test
functions found exactly ONE without an assertion (`tests/test_sankey_null_endpoint_guard.py:117`, a legitimate
never-raises test), there are no snapshot-only tests, and the flagship acceptance suite
(`tests/test_render_guarantee_50.py`) has an explicitly reasoned anti-fake-green preflight (hard-FAIL on
wrong-schema DB, loud SKIP on tunnel outage — lines 26–31, 340–412). The fabrication incident class is genuinely
regression-pinned. The weaknesses are all *around* the tests rather than in them: there is no CI of any kind, the
"offline" tier silently contains live-LLM tests, the suite's green depends on hand-seeded mutable DB content that
no fixture can reconstruct, and two of the three historical incident classes (SSR crash, cache-poison) are only
partially or manually protected.

---

## Findings (ranked)

### T1 — HIGH — No CI pipeline, no pytest config, no hooks: the 883-test suite only runs when a human remembers
**Evidence:**
- No `.github/`, `.gitlab-ci.yml`, `Jenkinsfile`, or git hooks anywhere under the repo root `/home/rohith/desktop/BFI`
  (checked; only `docker-compose.calcite.yml`, `docker-compose.cube.yml` exist; `NeuraReport/.pre-commit-config.yaml`
  belongs to an unrelated project).
- No `pytest.ini` / `pyproject.toml` / `setup.cfg` / `tox.ini` in `pipeline_v48/` — the only pytest configuration is
  `tests/conftest.py:22-23` registering the `live` marker. There are no `addopts`, so a plain `pytest` runs the live
  tier (real Qwen :8200, live DBs) by default; `-m "not live"` is oral tradition, not configuration.
- No coverage configuration anywhere (`.coveragerc` absent).

**Why it matters:** every green claim in the project memory ("882 suite green") is a manual run on one dev box.
Nothing structurally prevents a commit that breaks the suite; the committed `.pyc` files throughout the tree and the
manual runbooks are symptoms of the same gap. This is the single largest production-readiness gap in the testing
story, and it is cheap to close without enterprise ceremony.

**Recommendation:** (1) add a minimal `pytest.ini` with `addopts = -m "not live"` and the marker declaration;
(2) one CI job (even a cron/systemd script on the dev box, given no code-forge CI) running the offline tier +
`npm run ssr-gate`; (3) publish the two-lane contract (offline lane must pass with NO services; local-DB lane
requires :5432). Safe — no behavior change to any test.

---

### T2 — HIGH — The "offline" tier is not offline: 4+ files call the live LLM/pipeline with no `live` marker
**Evidence (all confirmed to have zero `pytest.mark.live` and zero mocking):**
- `tests/test_orchestrator.py:28-32` — `test_pipeline_live_join` runs the FULL `run_pipeline("voltage and current
  health for AHU-5")` and asserts an exact LLM routing (`page_key == "individual-feeder-meter-shell/voltage-current"`)
  and an exact resolver pin (`mfm_id == 36`).
- `tests/test_layer1a_routing.py:52-75` — `test_route_live_in_available`, `test_stories_every_card_covered`,
  `test_e2e_contract2_conformance`, `test_asset_agnostic_routing` all call `route()` / `build_stories()` / `run_1a()`
  (LLM stages `route`/`stories`) unmocked.
- `tests/test_layer1b_asset_resolve.py:41-54` — `test_resolve_confident_live` / `test_resolve_ambiguous_live` call
  `resolve_asset()` (LLM stage `asset_resolve`) unmocked and assert exact outcomes (`how == "AI"`, `class == "AHU"`,
  all-UPS candidate list).
- `tests/test_available_pages.py:23-26` — `test_route_stays_in_available` fires `route()` on 3 prompts.
- `tests/test_render_guarantee_50.py:478-503` — `test_render_guarantee_under_outage` is parametrized WITHOUT the
  live marker and calls `host.server.build_response()` (which needs the LLM for 1a routing) whenever `_data_db_up()`
  is False — i.e. exactly on the laptop-without-tunnel it is meant to tolerate.

By contrast the marked-live tier is only 4 files (`grep mark.live`: `test_layer1_reconcile_no_data.py`,
`test_layer2_card.py`, `test_render_guarantee_50.py`, `test_validate.py`).

**Why it matters:** `pytest -m "not live"` on a laptop with no :8200/:5433 fails or hangs in these files, so the
offline lane can never be a CI gate as-is; worse, the unmarked tests assert *specific nondeterministic LLM outputs*
(page_key, mfm_id, ambiguity class) in what everyone treats as the deterministic tier — LLM drift or a vLLM restart
turns the "unit" suite red. **Recommendation:** add `pytest.mark.live` to those ~9 test functions (or move them into
the live files). Safe — pure test metadata.

---

### T3 — HIGH — Cache-poison incident class: the permanent fix (`TTLCache` + panel_members never-cache-empty) has zero regression tests, and an unfixed sibling cache family is also untested
**Evidence:**
- `data/ttl_cache.py` (the 2026-07-09 "poison-permanent-fix", read in full, 54 lines) — no test anywhere imports it:
  `grep -rln ttl_cache` over the tree matches only `data/ttl_cache.py`, `data/lt_panels/panel_members.py`,
  `data/registry/lt_mfm.py`, `layer1b/resolve/has_data.py`. Its expiry semantics (`__contains__` goes False after
  TTL, `__setitem__` restamps, DB-knob `cache.resolution_ttl_s` fail-open at lines 22-28, 42-53) are unpinned.
- `data/lt_panels/panel_members.py:31-38` — `_MEMBERS_CACHE = TTLCache()` plus the never-cache-empty guards (the
  module that actually blanked panel_aggregate cards in the incident) has NO test: the only test hits on
  "panel_members" are `tests/test_equipment_ai_context.py:159-175` and `tests/test_residual_layer2_emit.py:149-150`,
  both of which test `layer2/emit/panel_members_block.py` (the prompt-fact formatter), not the resolver cache.
- What IS covered: `tests/test_has_data_outage.py:31-40` (`test_outage_result_is_never_cached`) pins the
  has_data leg — good, but it is one of three legs.
- The SAME poison family survives, unfixed and untested, in `ems_exec/data/neuract.py:24-25`:
  `_COLS_CACHE: dict = {}` / `_LOGGED_CACHE: dict = {}` are plain process-lifetime dicts populated at lines 83-92 and
  105-110 — a tunnel flap during column introspection caches a wrong answer for the process life, exactly the
  incident mechanism, through a different door. No test references these caches.

**Why it matters:** this incident class already cost a production-style outage (cards blank until server restart).
A refactor that swaps `TTLCache` back to `{}` — or copies the `neuract.py` dict-cache pattern into new code — would
reintroduce it with zero test signal. **Recommendation:** (1) a 30-line `test_ttl_cache.py` (monkeypatch
`time.time`: entry present → absent after TTL → overwrite restamps; knob fail-open); (2) a `panel_members` test:
edges stub raises once (empty result) → next call re-resolves (never-cache-empty); (3) either move
`_COLS_CACHE`/`_LOGGED_CACHE` onto `TTLCache` or pin the flap behavior there too. Safe (tests only; the neuract
cache change is risky-hot-path if taken).

---

### T4 — HIGH — SSR-crash incident class is guarded only by manually-run JS gates; zero automated linkage to the suite
**Evidence:**
- The gates exist and are good: `host/web/scripts/ssr_repro.tsx`, `ssr_gate.mjs`, `client_repro.tsx`,
  `datesync_repro.tsx`, and `host/web/package.json` scripts `"ssr-gate": "vite-node scripts/ssr_gate.mjs --"`,
  `"client-gate"`, `"layout-gate"`.
- Nothing invokes them automatically: `grep -rn ssr_repro` across `*.py` matches only docs
  (`outputs/INTEGRATION_AUDIT-wiring.md:35`, `docs/testfw/v48_subsystem_map_2026-07-12.json`); no pytest test, no CI
  (T1), no hook runs `npm run ssr-gate`. The only SSR word in `tests/` is a docstring mention in
  `tests/test_multi_asset.py:3` ("the live 2-asset render is asserted by the ssr/client gates + a curl").
- The per-leaf render-safety python tests (`tests/test_family_h_render_safety.py`, 168 lines) cover the *payload*
  side (freshness/trend_badge/display seams), not React component execution.

**Why it matters:** "honest-blank leaves crash CMD_V2 components" (Family H) is a *certified* incident class — the
cert was a point-in-time event. Any new card payload shape or blanking rule can reintroduce an SSR crash and the
883-test python suite cannot see it; protection currently depends on an agent remembering a runbook.
**Recommendation:** commit 2–3 sanitized `response_*.json` fixtures (including honest-blank-heavy ones) and add one
pytest that shells out to `npm run ssr-gate -- <fixtures>` (skip-with-reason when node_modules absent), so the
incident class is in the default lane. Safe.

---

### T5 — MEDIUM — Suite correctness is coupled to live, hand-seeded, mutable cmd_catalog content; no fixture/seeding story exists for a second machine
**Evidence:**
- Exact-content asserts against the production catalog: `tests/test_layer1a_routing.py:19`
  (`len(specs) == 68`), `:29` (`len(cards) == 8 and 5 in ids and 160 in ids`);
  `tests/test_layer1b_asset_resolve.py:19-28` (registry ids 317-320 are Panels with feeders, 171 has
  `has_feeders False`, AHU-5 pinned at id 36/table `gic_03_n6_ahu_5_p1`); `tests/test_available_pages.py:7-9`
  (`len(AVAILABLE_PAGES) == 18`).
- Knob/vocab-dependent behavior read from the live DB at test time: `config/app_config.py:18-24` fails open to `{}`
  on outage, so the SAME test can exercise different code paths depending on whether :5432 is up and what rows it
  holds; `tests/test_residual3_fixes.py:1-2` says outright "the quantity-vocab pins read the seeded cmd_catalog
  rows"; `tests/test_power_plausibility_knobs.py:15` "default is asserted against the live-seeded defaults";
  `tests/test_presentation_chrome_kept.py:9,19` mirrors two seeded vocab rows.
- The seeds themselves are ~60 hand-applied files in `db/` (`seed_*.sql`, `fix_*.sql`, `patch_*.sql` — listed) with
  no manifest, no ordering, no migration runner; `tests/test_render_guarantee_50.py:197-198` even instructs a human
  to "run db/render_guarantee_schema.sql + db/render_guarantee_seed.sql" when the matrix is empty.

**Why it matters:** (a) a catalog edit (adding page #69, re-slotting RTM cards) turns unrelated tests red — the
count asserts are content snapshots of a mutable DB; (b) a knob row edited for production tuning silently changes
what the tests assert, in both directions; (c) no CI or new team member can reconstruct the DB state the suite
needs, which blocks T1's local-DB lane. **Recommendation:** (1) an ordered `db/manifest` (or numbered `db/migrations/`)
plus a `tools/seed_test_catalog.sh` that builds a from-scratch cmd_catalog; (2) replace exact-count asserts with
invariant asserts (`>= N`, "RTM page contains cards 5 and 160") or read the expected count from the same DB row the
code reads. Breaking (test expectations change), low risk.

---

### T6 — MEDIUM — 10 permanently-green skip stubs, including the contract-critical files, inflate coverage optics
**Evidence:** 10 six-line files whose only test is `pytest.skip("TODO(v48): implement")` (all read):
`test_invariants.py` ("the §B4 invariant assertions"), `test_contracts_roundtrip.py` ("every schema in contracts/
round-trips"), `test_layer2_data_instructions.py`, `test_layer2_metadata_no_chrome.py`,
`test_layer2_metadata_byte_identical.py`, `test_layer1a_partition_inputs.py`, `test_partition_orphan_160.py`,
`test_sharedctx_generalizations.py`, `test_workers_aggregate_panel174.py`, `test_workers_aggregate_builders.py`.
Several are marked "★" (their own convention for critical). Some of their subjects ARE covered elsewhere
(byte-identity: `tests/test_layer2_card.py:32-40`; no-chrome: `test_layer2_card.py:58-60`), others are not
(contracts round-trip; partition orphan-160 — `tests/test_partition_groups.py` is 20 lines).
**Why it matters:** the file count (96) and "suite green" reporting silently include 10 no-op files; a reader
greps `test_layer2_metadata_byte_identical.py`, sees a file, and assumes the invariant is pinned.
**Recommendation:** delete the stubs whose subject is covered elsewhere (note the covering test in the deletion
commit), implement the 2–3 genuinely uncovered ones (contracts round-trip is nearly free: iterate `contracts/`
schemas). Safe.

---

### T7 — MEDIUM — Whole subsystems with zero (or lint-only) tests
**Evidence (import scan over `tests/*.py` + direct greps):**
- `copilot/` — 23 files / 1,692 lines, a RUNNING service (:8772 + its own LLM :8201): the only test is
  `copilot/tests/test_no_coupling.py` (59 lines, an AST import-decoupling lint — read). Retrieve→generate behavior,
  ranking, and its API have no tests.
- `knowledge/` — 2 files / 86 lines (`route.py`, `answer.py`, the concept-Q&A refusal wall): zero tests. The
  off-domain-refusal wall is a safety behavior with no pin.
- `host/exec_cards.py` and `host/payload_store.py` — zero test references (grep); the other 7 host modules are tested.
- `grounding/` — only `default_assemble`, `role_scrub`, `swap_settle` are imported by tests; `schema_route.py`,
  `schema_fingerprint.py`, `exemplar_reduce.py`, `meaningful.py`, `event_skeleton_scrub.py`,
  `measured_annotation_scrub.py` have no direct tests (package is 1,449 lines).
- `ems_exec` executor modules with no direct test references (grep over tests): `wildcards.py` (186 lines, the `[*]`
  array-grow that fills every series card), `window_policy.py`, `roster_modes_series.py` (332 lines),
  `renderers/_insight.py` (the ONLY LLM caller inside ems_exec). These get incidental coverage through `fill()`
  tests at best.
- `obs/` — 19 files; only `ai_log`, `failures`, `stage` are touched by tests; `redact.py`, `bus.py`, sinks, spans
  untested (telemetry, so lower stakes — but redaction is a correctness surface).
- `validation/` — 20 files / 2,179 lines (the new prompt-testing framework skeleton dated today): no tests, expected
  at this stage but worth tracking.

**Why it matters:** the pipeline's stated fix-order is prompts→DB→code, but `wildcards.py` and
`roster_modes_series.py` are load-bearing generic code where a regression produces *wrong-looking real data* — the
class of bug only the live 50-prompt suite would catch, at much higher triage cost. Copilot/knowledge are
user-facing services whose only safety net is manual use. **Recommendation:** prioritize direct unit tests for
`wildcards.py`, `roster_modes_series.py`, `knowledge/route.py` (refusal wall), and one copilot retrieve→generate
happy-path with the LLM seam mocked. Safe.

---

### T8 — MEDIUM — DB-availability gating is inconsistent: most cmd_catalog tests hard-ERROR (not skip) on a machine without :5432
**Evidence:**
- Gated correctly: `tests/test_equipment_topology.py:21-28` (`_local_up()` probe +
  `pytestmark = pytest.mark.skipif(...)`); `tests/test_render_guarantee_50.py:77-82, 179-198` (in-test preflight);
  `tests/test_asset3d_dg_seed.py:23` (skip on :5433 only).
- Ungated despite querying the DB at test (or import) time: `tests/test_equipment_ratings.py:17`,
  `tests/test_equipment_3d.py:56`, `tests/test_equipment_ai_context.py:3` (docstrings say ":5432-local", no skipif);
  `tests/test_layer2_swap_gates.py:15,31,186,193` and `tests/test_layer2_slot_catalog_series.py:18,23` (raw
  `q("cmd_catalog", ...)`); `tests/test_page13_dg_cert_defects.py:406`; `tests/test_layer1a_routing.py:13`
  (module-level `available_page_keys()`); `tests/test_layer1b_asset_resolve.py:16-28`.
- Three different gating idioms coexist (skipif-probe / preflight-fail-vs-skip / skip-marked parametrize param),
  per the subsystem map and confirmed here.

**Why it matters:** on any machine that isn't the dev box, the suite's failure mode is a wall of psycopg2 connection
errors indistinguishable from real regressions — the exact "fake-red" the render-guarantee preflight was built to
avoid. **Recommendation:** one shared `requires_cmd_catalog` fixture/marker in `conftest.py` (probe once per
session, skip with a machine-readable reason), applied to the ~12 files above; keep render_guarantee's stricter
fail-on-wrong-schema policy as-is. Safe.

---

### T9 — MEDIUM — Swap-chain coverage depends on `/tmp/l2_inputs.json`, a machine-local artifact of a prior live run
**Evidence:** `tests/test_layer2_card.py:21-29` — `_l2_inputs()` opens `/tmp/l2_inputs.json` ("REAL L1a/L1b outputs
… dumped by a prior live pipeline run"), and `pytest.skip`s when absent. `/tmp` is wiped on reboot; the artifact is
not in the repo, and no script in `tools/` is referenced for regenerating it in the test itself.
**Why it matters:** on every fresh machine — and on the dev box after any reboot — the swap-chain tests silently
skip forever; coverage that looks present in the file evaporates at exactly the moment (new environment) it is most
needed. The stated reason ("we never fabricate one") conflates fabricating *data values* with committing a
*sanitized structural fixture* — the anti-fabrication rule is about rendered values, not test inputs.
**Recommendation:** commit one sanitized `tests/fixtures/l2_inputs.json` (real structure, dummy values are fine for
swap-chain structure tests) and fall back to `/tmp` for the live-refresh path. Safe.

---

### T10 — MEDIUM — Ordering/parallelism hazards: alphabetical-order reporter, wall-clock timing assert, ad-hoc cache resets
**Evidence:**
- `tests/test_render_guarantee_50.py:200-203, 512-533` — module-global `_RESULTS` mutated by parametrized tests and
  consumed by `test_zz_aggregate_report`, which "runs last; alphabetical zz". Breaks under `pytest-xdist` (workers
  don't share `_RESULTS`) or random ordering; the final `any_answered` assert would then fail or skip spuriously.
- `tests/test_orchestrator.py:16-21` — `test_run_parallel_is_concurrent` asserts `time.time() - t < 0.7` around two
  0.4 s sleeps; on a loaded machine (the same box running vLLM) a 0.3 s scheduler stall makes it flake. The only
  `sleep` in the suite, but it is in the deterministic tier.
- Cache-reset discipline is split: `conftest.py:29-38` autouse-clears only `config.app_config._load` and
  `config.vocab.vocab` (added after a real ordering failure the docstring documents), while other module caches are
  cleared ad-hoc inside individual files — `tests/test_equipment_topology.py:39,43,262,277,293,310`
  (`lt_mfm._CACHE.clear()`), `tests/test_fab_guards.py:65,81,150` + `tests/test_post_fill_rescue_overreach.py:336`
  (`G._ROWS_CACHE.clear()`), `tests/test_equipment_ai_context.py:173` (`pmb._block_for.cache_clear()`). Uncovered
  cache sites a future test can poison exactly as before: `ems_exec/executor/recipe.py:26,71` (lru 256/64),
  `layer2/emit/panel_members_block.py:65`, `data/lt_panels/panel_members.py:32`, `layer1b/resolve/has_data.py`
  module caches, `ems_exec/data/neuract.py:24-25`.

**Why it matters:** the suite already had one order-dependent failure (conftest docstring); the remaining uncovered
caches are the same trap re-armed. The timing assert and zz-reporter block ever running the suite parallel — which
an 883-test suite will want soon. **Recommendation:** extend the autouse fixture to clear the enumerated caches
(cheap, explicit list); replace the timing assert with a barrier/event-based concurrency proof; move the aggregate
report to a `pytest_terminal_summary` hook in conftest (order-independent). Safe.

---

### T11 — LOW — Fixture and probe duplication; no shared helpers module
**Evidence:** no `tests/helpers.py` / shared fixtures beyond the 38-line conftest. Duplicates found:
`_capture` urlopen-fake built independently in `tests/test_route_guided_json.py:26-43` and
`test_item17_guided_json.py`; `call_qwen` patched per-file in 6 files (counts: item17 ×11, llm_truncation ×10,
stage_telemetry ×5, route_guided ×5, foundations ×3, basket_logged_floor ×2); neuract stubbed via `setattr(nx, …)`
in 7 files with two independent `_stub_neuract` helpers; a `_card` builder defined 4 times; DB probes duplicated
(`_local_up` in test_equipment_topology.py:21 vs `_catalog_up` in test_render_guarantee_50.py:77). The
`sys.path.insert` bootstrap is duplicated in 2 test files despite conftest doing it globally
(`tests/test_render_guarantee_50.py:38-40`).
**Why it matters:** minor today; it mostly costs consistency (each fake encodes slightly different LLM-reply shapes)
and makes T8's consolidation harder. **Recommendation:** one `tests/_fakes.py` with `fake_qwen(reply)`,
`stub_neuract(rows)`, `catalog_up()`; adopt opportunistically. Safe.

---

### T12 — LOW — Audit-round naming obscures area coverage; residual batches overlap fill() coverage
**Evidence:** regression batches named by round, not subject: `test_residual_layer2_emit.py`,
`test_residual2_fixes.py` (header lists R1–R14 across roster gaps, narrative, timezone, xaxis, yscale, walls),
`test_residual3_fixes.py` (R1–R13), `test_agentb_fill_fixes.py`, `test_seam3_seed_and_period.py`,
`test_item17_guided_json.py`, `test_item21_catalog_compress.py`, `test_page13_dg_cert_defects.py`,
`test_stage_telemetry_item15.py`. The content is good (real, specific asserts — verified in residual2/3 heads);
the cost is discoverability: yscale behavior now lives in `test_yscale_derivation.py` AND residual3 R7–R9;
xaxis in `test_fill_chrome_axes_preserved.py` AND residual2 R6/R7 AND residual3 R4/R5.
**Why it matters:** someone changing `yscale.py` cannot find its tests by name; duplicated-looking failures across
3 files slow triage. **Recommendation:** don't rename wholesale (churn); when a residual pin is next touched, move
it into the subject file and leave the round id in the test docstring. Safe.

---

### T13 — LOW — conftest `sys.modules` surgery for the layer2 package shadow is load-bearing and fragile
**Evidence:** `tests/conftest.py:7-15` deletes wrongly-bound `layer2*` modules and re-imports, with an assert that
the package file lives under ROOT. It works because pytest happens to put ROOT first; the docstring itself notes the
grandparent `backend/layer2` package shadow. Two files ALSO re-insert ROOT themselves (T11).
**Why it matters:** a pytest rootdir change (e.g. adding a `pyproject.toml` at `backend/` level per T1) or running
tests from a different cwd re-arms the shadow; the failure mode (importing v47's `layer2`) is confusing.
**Recommendation:** when adding the T1 `pytest.ini`, set `rootdir`/`testpaths` explicitly so the workaround becomes
deterministic; longer-term the directory rename the map suggested is the real fix. Safe.

---

## What is genuinely good (keep)

- **Fabrication incident class: properly regression-pinned.** `tests/test_fab_guards.py` (666 lines, pure unit,
  monkeypatched neuract — header lines 1-17 read) covers the 3 generic fabrication classes both at the guard unit
  AND through the real `fill()`; `tests/test_page13_dg_cert_defects.py` pins the two cert defects;
  `tests/test_render_guarantee_50.py:209-226` asserts the no-seed-leak invariant structurally on every live prompt;
  `tests/test_fill_display_siblings.py` pins seed-vs-live display reconciliation. This is what incident-class
  regression testing should look like.
- **Anti-fake-green preflight** (`test_render_guarantee_50.py:340-412`): the outage/wrong-schema/no-config
  classification with fail-vs-skip policy is exemplary and should become the shared idiom for T8.
- **Assertion quality:** 1 assert-less test out of 883, and it is a legitimate never-raises test
  (`test_sankey_null_endpoint_guard.py:117-122`).
- **The autouse config-cache reset** (`conftest.py:29-38`) — right idea; T10 asks to widen it, not change it.
- **`test_has_data_outage.py`** — the outage-vs-bad-chunk split is exactly the right shape for cache/poison pins;
  T3 asks for two more files in the same style.

## Test-to-source coverage map (summary)

| Area | Coverage |
|---|---|
| layer1a routing/parse/db_reads | Good, but live-LLM tests unmarked (T2); partition_inputs stubbed (T6) |
| layer1b resolve/basket/guardrail | Good; compare/ lane via test_multi_asset (mocked) |
| layer2 emit/gates/swap/quantity | Strongest cluster (~20 files); byte-identity stub is redundant with real tests |
| ems_exec fill + post-fill passes | Dense (largest cluster) EXCEPT wildcards, window_policy, roster_modes_series, _insight (T7) |
| grounding | 3 of 10 modules tested (T7) |
| host | 7 of 9 modules; exec_cards, payload_store untested (T7) |
| run/harness | Via orchestrator + live suite; degrade_gate via has_data/reconcile tests |
| validate | Well covered (8 modules imported) |
| obs | ai_log/failures/stage only (T7) |
| data/ (ttl_cache, lt_panels, registry) | ttl_cache and panel_members UNTESTED (T3); registry via equipment_topology |
| copilot / knowledge | lint-only / zero (T7) |
| Incident classes | fabrication: strong · SSR crash: manual-only (T4) · cache-poison: 1 of 3 legs (T3) |
