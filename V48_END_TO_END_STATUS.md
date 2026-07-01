# V48 — Full-Codebase Status (2026-06-30)

> WHOLE-codebase audit of pipeline_v48 (not a session snapshot). Every subsystem audited module-by-module for
> implemented / partial / stub / dead + whether it's reachable from the live spine. Companion: `IMPLEMENTATION_PROGRESS.md`.
> Verified against: Qwen3.6 @ :8200, live `cmd_catalog`, ems_backend daphne @ :8890, host @ :8770, Vite @ :5188.
> **Headline:** the runtime SPINE is genuinely live end-to-end on all 9 pages; but the V48 atomic-structure rule left
> ~110+ single-purpose STUB files whose logic is *inlined into the live modules* — so the tree looks far more
> modular-complete than it is. The `contracts/` enforcement layer is entirely unbuilt, `copilot/` is built but was
> undocumented, and there is one real live bug (no-dup swap gate). See the inventory + gaps below.

---

## ✅ THE LIVE SPINE — works end-to-end
```
prompt → 1a (page/template) ∥ 1b (asset mfm_id + column basket) → validate → asset-gate
       → Layer 2 (per-card swap + exact_metadata + data_instructions)  [parallel fan-out]
       → host fetches ems_backend frame per endpoint → frontend renders the REAL CMD V2 card via its own mapper
```
- **All 9 pages route + render; 38/38 cards fillable** (real live data reaches every card) — verified per page.
- **ems_backend**: 44 live consumer strategies + REST + WS dispatch + Keycloak auth + DB-keyed `derivations/` recovery — all wired through `asgi.py` over `compat` (DB `target_version1`). `EMS_REFERENCE_NOW=2026-03-26T05:55:09+05:30`.
- **Recovery**: `ems_backend/lt_panels/derivations/` (registry + 8 pure-fn modules), deterministic `RECOVERY_FN` auto-derive in `BaseLiveStrategy.fill_derived`. 27 value-keys, verified on real data.
- **copilot/** (was missing from the old doc): a FULLY-BUILT, deployed typeahead query layer — systemd `:8772` + a 4B model `:8201`, wired into the host PromptBar, zero pipeline coupling (`test_no_coupling`). 16 live modules.

## 🗄️ DATA SOURCE (verified 2026-06-30)
DB **`target_version1`**, two schemas:
- **`neuract`** — the RAW live logging, **ACTIVELY WRITING**. 321 tables `esp32_mfm_<NNN>`, **11 columns** each:
  `timestamp_utc, Hz, I_L1, I_L2, I_L3, kVAR, kW, PF, V_L1, V_L2, V_L3` (3-phase RMS V/I + kW/kVAR + PF + freq). Ground truth.
- **`compat`** — the canonical layer the ems_backend consumers read. `cmp_mfm_<NNN>` are **VIEWS** (61 cols) that COMPUTE the
  derived metrics (avg / deviations / unbalance / THD / energy / KPIs) from the 11 raw neuract columns.

**Flow:** `neuract` (raw, live) → `compat` VIEWs (computed) → ems_backend consumers (`cmp_mfm_*`) → host → frontend. So the
pipeline renders **live** data (the compat views sit over the actively-writing raw feed).

**THREE databases (corrected — it's not one):**
| DB | holds | how code connects |
|---|---|---|
| `cmd_catalog` | card/page catalog | pipeline `data/db_client.q()` (psql, env `PGHOST/PGPORT`) |
| `lt_panels_db` | **registry** — `lt_mfm` (220 rows, the db_link), `lt_config`, types/topology | Django ORM `settings.py NAME=lt_panels_db` + pipeline 1b `q('lt_panels_db', …)` |
| `target_version1` | **DATA** — `neuract` raw → `compat` views | the per-MFM `db_link` (libpq), NOT Django settings |

So the DATA path is the `lt_mfm.db_link` (already repointed to `target_version1`/`compat`), independent of the Django ORM DB.

**Connection / env-driven wiring (done this session):** the `db_link` DEFAULTS in `lt_panels/models.py`, `assets/models.py`,
and the two seed commands previously hard-pointed at the OLD `postgresql://postgres@/lt_panels?host=/run/postgresql` socket
DB → now use **`lt_panels/data_db_link.default_db_link()`** (env-driven): `DATA_HOST` (def `localhost`) · `DATA_PORT` (def
`5432`) · `DATA_DB` (def `target_version1`) · `CONSUMER_SCHEMA` (def `compat`). Migrations `0012`/`0004` record it; existing
rows untouched; local fill re-verified. user `postgres`, no password (trust). **archbox**: set `DATA_HOST=127.0.0.1
DATA_PORT=5433` (+ `PGHOST/PGPORT` for the pipeline's catalog/registry). Verify: `psql -h 127.0.0.1 -p 5433 -U postgres -d
target_version1 -c "select count(*) from information_schema.tables where table_schema='neuract'"` → 321.

**⚠️ Deployment items to confirm on archbox (NOT code):** the `:5433` tunnel exposes ONLY `target_version1` — `cmd_catalog`
+ `lt_panels_db` must be reachable some other way there (local socket / separate tunnel). And the `compat.cmp_mfm_*` VIEWS
must exist on the archbox `target_version1` — a probe of `:5433` found neuract but not the cmp_mfm_* views; the compat
generator (see `findings/neuract_compat_integration.md` "Remaining for the FULL rollout") must have run there, else the
consumers honest-degrade. The `lt_panels` DATA DB is DEPRECATED — only the legacy `derivations` example references it.

**Settles the contract/rated gap:** the rated-capacity / load-%-of-rated / nameplate columns are in NEITHER schema (neuract
logs only raw measurements; confirmed no such column in any neuract table). So contract/`2700` honest-degrade is CORRECT —
the rating was never logged; only the old lt_panels *simulator* computed it. `derivations/` recovers what the raw feed
*does* support (neutral from per-phase I, nominal from V+deviation, PF-angle from PF); rated/contract genuinely can't be.

## 📊 SUBSYSTEM INVENTORY (impl / partial / stub / dead)
| subsystem | impl | part | stub | dead | one-line |
|---|---|---|---|---|---|
| `run/` (spine) | 6 | 1 | 1 | 0 | live; **1 bug**: `layer2_all.py` drops `already_chosen` |
| `layer1a/` | 16 | 0 | 4 | 4 | critical path live; 4 dead scaffolds |
| `layer1b/` | 8 | 1 | 12 | 13 | asset-resolve + basket live; guardrail (L3.5) unbuilt; 12 inlined scaffolds |
| `layer2/emit/` | 6 | 0 | 30 | 30 | live = user_message + consumer_binding + split/producer; 18 shape-metadata + 6 field_* binders **dead** (morphs are AI-generic) |
| `layer2/` (rest) | 21 | 0 | 4 | 4 | build/gates/schema + 7 swap gates + 8 catalog reads live |
| `validate/` + `contracts/` | 9 | 0 | 10 | 9 | validate/ live; **contracts/ ENTIRELY unbuilt** (validate.py + 8 invariants + 10 schema.json = stubs) |
| `workers/` | 11 | 0 | 21 | 19 | fill+stitch path live; all of `sharedctx/`, `fill/kinds/`, multi-buffer stitch = Approach-B stubs |
| `host/` + `host/web/` | 33 | 3 | 0 | 0 | preview API + React SPA fully live; 3 partials = dev-only dead code |
| `ems_backend/consumers/` | 44 | 2 | 22 | 0 | 44 live strategies; **ht_panel + sub_panel = StubStrategy across ALL 13 screens** (22) |
| `ems_backend/` (core) | 48 | 0 | 1 | 0 | REST+WS+services+derivations+Keycloak live |
| `data/` (DB access) | 1 | 0 | 15 | 14 | only `db_client.q()` is live; **all 14 registry/lt_panels/cmd_catalog/nameplate/derived_metrics modules are TODO stubs, bypassed** |
| `copilot/` | 16 | 0 | 1 | 0 | fully built + deployed (was undocumented) |
| infra (`config/llm/obs/partition/payload_db/ems_compat`) | 33 | 0 | 0 | 0 | all real; payload_db/ems_compat = offline CLI harvest tools |
| `tests/` | 10 | 0 | 15 | 0 | 10 real; **15 are TODO(v48) placeholders** targeting live modules |

## ⚠️ REAL LIVE GAPS (in the flow, unbuilt — fix these)
1. **`run/layer2_all.py` — `already_chosen` not threaded** (real bug). `run_2_all` calls `run_card` without `already_chosen`, so the no-dup swap gate (`swap/gate_no_dup.py`) is fed an always-empty set → two parallel cards on a multi-card page can both swap to the *same* target. `trace.py` already does it right (threads `chosen`). Also resolve the design inconsistency: `layer2_all`'s docstring says no-dup is "a pure AI-prompt rule" but `swap/decide.py` still has the deterministic gate.
2. **`contracts/` enforcement layer — entirely unbuilt.** `contracts/validate.py` + 8 `invariants/*.py` (byte_identical_default, every_key_once, no_chrome, no_root, one_payload, opt_in_default_off, live_sentinel_ref) + 10 `*.schema.json` are all stubs/empty skeletons. The byte-identical / no-chrome / one-payload guarantees V48 rests on are enforced **only ad-hoc** inside `layer2/gates.py` + `workers/stitch` — no central validator, no regression net.
3. **ems_backend `ht_panel` + `sub_panel` — StubStrategy across ALL 13 screens** (22 stubs). Any prompt resolving to an HT-panel or sub-panel asset returns empty frames on every screen. **Blocked on user spec**, not a code bug. (The old doc only flagged the much-narrower panel-history gap.)
4. **Test debt** — 15 of 25 test files are TODO(v48) placeholders for live behaviors: each swap-gate, stitch one-payload, fill-kinds, metadata byte-identity + no-chrome, dialects, aggregate builders, partition_inputs, orphan-160, contracts-roundtrip. So "62 pass" is true but coverage is ~40% of the named surface. Whole subsystems untested: contracts, copilot, ems_backend, host, payload_db, fe_contract.
5. **`workers/fill/window.py` + `spec_seam.py`** — worker-side SQL re-slice unbuilt; works today because windowing is delegated to the ems_backend WS query (`ems_window.py`). Only matters if an offline/test-db fill path is ever needed.

## 🧱 DEAD SCAFFOLDING (~110+ atomic stubs — logic is INLINED into the live modules)
The atomic-structure rule (one file per concern) created many single-purpose files that were never filled because the
logic was written directly into the live module. **These files look functional but are empty `# TODO(v48)` shells, not in
the live flow** — flagged, not asserted-dead (verify served/unique-value before any deletion, per the project rule):
- `layer1b/` ~13 (resolve/basket/guardrail/parse scaffolds — logic inlined in `asset_resolve.py`/`column_basket.py`)
- `layer2/emit/metadata/` 18 shape modules (heatmap, rail, hpq_*, radar, sankey, sld, kpi_tile, table, progress…) + `emit/data/field_{raw,derived,const,event,text}.py` + `atom_emit`/`standalone_emit`/`ctx_source_form`/`fill_mode` — morphs are AI-decided generically, not per-shape Python
- `data/` 14 (registry/, lt_panels/, cmd_catalog/, `nameplate.py`, `derived_metrics.py`) — bypassed by direct `db_client.q()` + `information_schema` queries; **recovery formulas live ONLY in `ems_backend/lt_panels/derivations/`, NOT in `data/`**
- `workers/sharedctx/` (builder + 6 `gen_*`) + `stitch/{resolve_multibuffer_id,dedup_keys,attach_ctx}` + `fill/kinds/*` — the Approach-B / multi-buffer / per-field-kind future work (interdependency machinery)
- `layer1a/` 4 (page_handling, think_strip, v_interaction, selection_dimension), `layer2/` 4 (card_resolve, recipe_reconcile, contract_components, self_correct)

## ⏳ PENDING / LEFT (genuine work, prioritized)
1. **Value-correctness sweep** — "fillable" ≠ "correct value." Known: rail Voltage tile `6,353 V` (should be ~415/240) = mapper column/unit bug. Need a per-card `V3_mismap` pass.
2. **Fix `layer2_all` no-dup** (gap #1) + add a multi-card-with-swap test.
3. **Build `contracts/`** (gap #2) — the central byte-identity/no-chrome/one-payload validator + invariants, or formally drop it in favor of the ad-hoc gates.
4. **Remove the inert AI-recovery emit path** — the Layer 2 prompt still asks the AI for recovery `fn` recipes + the `&derived=` plumbing ships them, but the deterministic `RECOVERY_FN` baseline overrides them (the AI mis-selects). Dead weight; remove for clean deterministic recovery (user: "don't use AI" for recovery).
5. **Contract/nameplate real-sourcing on compat** — `2700`/rated honest-degrade (the ratio columns were dropped lt_panels→compat). Carry the column into compat OR populate the empty `asset_config` tables.
6. **ht_panel/sub_panel strategies** (gap #3) — blocked on user spec.
7. **Panel history strategies** — `energy_power_history/`/`demand_profile/` have no `pcc_panel.py`; panel trend cards are live-only (correct for their window-based components); implement for panel date-nav.
8. **Implement the 15 placeholder tests** (gap #4).
9. **The 4 walls (~46 values)** — waveform / per-order harmonics / externally-assigned nameplate / device-state — genuinely no data on compat → honest-degrade.
10. **Interdependency / cross-card date-sync** — DEFERRED (user). NOTE this also covers the whole `workers/sharedctx/` Approach-B machinery (currently stubs). Plan: `V48_INTERDEPENDENT_CARDS_DESIGN.md`.
11. **Ops**: `kcauth/ws_auth.py` built but NOT wired into `asgi.py` (WS auth off by default — needs FE token-send).

## Session-scoped work (2026-06-30) — folded into the above
websocket-client dep fix · 3-shape frame routing (widgets/queue/buckets), history frames KEPT (blunt drop reverted) ·
RTM footer frame-share · panel energy-power `widgetsFrame(frame,pageFrame)` fallback (the one endpoint↔shape mismatch) ·
DB-keyed `derivations/` resolver + deterministic `RECOVERY_FN` · 38/38 fillability verification.
