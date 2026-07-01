# FINDING — EMS backend hardcoding: tables vs columns (hands-on audit)

> User flagged (2026-06-29): *"there is hardcoding in ems backend i think — of tables and columns."*
> Checked the actual CMD EMS backend code by hand (`/home/rohith/CMD/backend`): `lt_panels/services.py`, `consumers/_base.py`, `consumers/_dispatch.py`, `consumers/real_time_monitoring/pcc_panel.py`, `routing.py`. A parallel workflow corroborates across all ~80 consumer files.

## Verdict: TABLES are not hardcoded; COLUMNS are (as per-(view×class) recipes). Reuse-by-resolved-asset still holds.

### TABLES — fully parameterized by the resolved asset ✅
- WS route = `ws/mfm/<int:mfm_id>/<endpoint>/` (`lt_panels/routing.py`). The **asset is a URL param** (`mfm_id`).
- `_base.py::connect()` → `self.mfm_id = scope['url_route']['kwargs']['mfm_id']` → `MFM.objects.get(id=mfm_id)` (the **registry** row).
- Every read in `services.py` (`fetch_live/fetch_window/fetch_bucketed/…`) takes `(db_link, table, panel_id, …)` as **arguments**; the dispatcher passes `self.mfm.db_link, self.mfm.table_name, self.mfm.panel_id`. **Zero hardcoded table-name literals in any consumer** (grep: only `'mfm_id'/'mfm_name'/'mfm_type'` *wire keys* appear, never a `"mfm_…"` table name).
- **Aggregate fan-out roster** (PCC RTM) is **discovered from topology**, not baked: `_load_topology()` reads `self.mfm.incoming` / `self.mfm.outgoing`; each child fetched by its own `child.db_link/table_name/panel_id`.
- **Strategy selection** is a pure function of the asset: `_dispatch.resolve_category(mfm)` = name-prefix rule (`"pcc panel"→pcc_panel`, extensible list) → else `mfm.mfm_type.code`. No asset pinning.
- ⇒ Point a consumer at **any** `mfm_id` (what 1b resolves) and it reads **that** asset's table(s). This is exactly the V48 reuse mechanism — it already works this way.

### COLUMNS — hardcoded as per-(view × class) literal recipes (the real "hardcoding"), but column-tolerant
- Each strategy declares literal column maps: e.g. RTM `_METRIC_COLS = {kw:'active_power_total_kw', volt:'voltage_avg', …}`, `_FETCH_COLS`; voltage_current `_EVENT_COLS = [('sag_event_active','sag'),…]`. A few `services.py` helpers also bake columns (`fetch_hourly_buckets` → `active_power_total_kw…`; `fetch_phase_events` → `voltage_r_n/y_n/b_n`).
- **Mitigations that make this non-blocking:**
  1. **Column-tolerant**: `get_table_columns()` introspects the real table; `_select_existing` / agg builders **silently drop + None-pad** columns absent on that asset's table. Cross-class degrades (blanks) instead of erroring ("a transformer table may carry `voltage_hv_avg` instead of `voltage_avg`").
  2. **Class-appropriate by construction**: per-class strategy files (`pcc_panel/lt_panel/transformer/ups/apfc`) are selected by the asset's type, so the literal columns match the asset's schema for same-class assets.
  3. **Column-row strategies accept a `?columns=` URL override** (identifier-validated). NB: **aggregate strategies (RTM, V&C-PCC) do NOT** — their column set is fixed.

### THRESHOLDS / constants — hardcoded, but cosmetic (not data-sourcing)
- `_NOMINAL_LN_V = 415/√3`, band cutoffs (load 60/80/95%, PF 0.98/0.95/0.90, etc.). Code itself flags `# HARDCODED thresholds — TODO: move to per-MFM config`. These drive **severity colouring / derived math**, not which rows/columns are read.

## Implication for V48 Layer 2 (refines the DATA decision)
- **"Reuse CMD consumers directly, parameterized by 1b's resolved asset" is VALID.** Hardcoded columns are the *recipe*, not a blocker.
- **The AI's `data_instructions` knobs are: `{asset mfm_id, range/preset, sampling, widget, selection commands (select_feeder / timeline_time / selected_period)}` — NOT the column list.** A consumer's columns are fixed by its (view×class); only column-row strategies expose `?columns=`. This is arguably *correct* (we don't want the AI inventing column math) — the consumer IS the vetted data recipe. The 1b column-basket therefore informs **upstream metric/asset selection**, not the consumer's read list.
- **Constraint to honor:** a consumer yields *correct* data for an asset only where that asset's table carries the consumer's assumed columns — full for same-class, graceful-partial (blanks) cross-class. Layer 2's card→consumer choice (`card_handling.backend_strategy`) must therefore agree with the resolved asset's class, or accept graceful blanks. Log mismatches (no reloop).
- **Same column vocabulary** as 1b: consumers read physical column names that match `lt_parameter.column_name` — so basket ↔ consumer columns are the same dictionary.

---

## Corroboration (19-agent workflow across all ~80 files) + the decisive reconciliation

The workflow agreed on both axes (TABLE parameterized everywhere; COLUMN = hardcoded literal per-(class,page) list everywhere; `services.py` + `assets/services.py` reuse-clean) and added precise facts:
- **The `lt_parameter` source EXISTS but is bypassed by the WS path.** `models.Parameter` (db_table `lt_parameter`, FK `mfm_type`, `column_name`) is queried by the REST `views.py` (`params_by_col`) — but **zero** consumers/services read it. So columns *could* be sourced from `mfm_type_id → lt_parameter`; the WS consumers just don't.
- **The 3 column-baking helpers in `services.py`** (`fetch_hourly_buckets`, `fetch_phase_events`, `fetch_phase_event_counts_per_bucket`) are **DEAD within the package** — ignore them (don't re-introduce).
- **Assets nameplate table is class-pinned:** `CONFIG_TABLE='transformer_config'`/`'ups_config'` literals (db_link/asset_id stay parameterized; only the config-table *name* is class-fixed).
- **`?columns=` override reaches column-row strategies but NOT the PCC aggregates** (RTM/V&C/E&P/PQ/overview `pcc_panel` ignore `self.columns` and use module literals — baked hardest).

### The reconciliation — "blocked" only under a wrong assumption
The workflow's "blocked on the column axis" verdict assumes you **force ONE strategy file onto an arbitrary-class asset.** But that is **not how the system is driven, and not how V48 should drive it.** The dispatcher selects the strategy by the **resolved asset's class** (`RealTimeMonitoringDispatcher.STRATEGIES = {lt_panel→…, transformer→…, ups→…, pcc_panel→…(aggregate), ht_panel/sub_panel→Stub}`; key = `resolve_category(mfm)` → `mfm_type.code`). So when you drive `ws/mfm/<resolved mfm_id>/<page-endpoint>/`, you get the **class-correct strategy**, whose hardcoded columns are **correct-by-construction for that class.** Same-class is automatic and right; the "cross-class blanks" failure only happens if you pin a fixed strategy file and ignore the dispatcher.

### ⇒ Decisive directive for V48
- **Drive the EMS by `(resolved mfm_id, page-endpoint)` through the dispatcher — do NOT pin `card_handling.backend_strategy`'s literal file onto an arbitrary asset.** Read `backend_strategy` as **(view/page-endpoint + a representative class file)**; the *actual* strategy = `STRATEGIES[resolved_asset_class]` on that page's dispatcher. Column hardcoding then becomes a **non-issue** (each class reads its own right columns).
- This also settles the earlier build-time open (**WS service vs in-process adapter**) in favor of **driving CMD's own WS dispatcher**: it gives class-routing + `?columns=` + interactivity + graceful degradation for free; an in-process adapter would have to re-implement `resolve_category`/`STRATEGIES`/dispatch.
- **RTM heatmap slice is SAFE in practice:** that card = the PCC feeder-severity heatmap = the `pcc_panel` *aggregate* strategy; its asset is a PCC panel, so the fixed 7-metric roster (`active_power_total_kw`, `power_factor_total`, `voltage_avg`, `current_avg`, `current_unbalance_pct`, `kpi_kw_load_pct_of_rated`) is exactly right. No cross-class concern for this card.
- **Genuine residual limits (log, no reloop):** (1) some `(class,page)` pairs are `StubStrategy` → 'pending' empty frame (e.g. `ht_panel`/`sub_panel` RTM) — a real coverage gap; (2) within a class, the strategy roster is fixed — within-class column variants pad None (graceful). **Remediation only if ever needed:** source columns from `mfm_type_id → lt_parameter` in the strategy base (preferred; mechanism already exists in `views.py`), or build `?columns=` from `lt_parameter` in the V48 caller for column-row strategies (aggregates need the base-level fix).
