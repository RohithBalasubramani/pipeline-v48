-- ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
--  V48 RENDER-GUARANTEE CONFIG SCHEMA  (cmd_catalog, editable rows — ZERO hardcoded policy in logic code)
--  Every threshold / mapping / nameplate / schema-map / metric-class / reason / endpoint policy is an EDITABLE ROW here.
--  Run:  psql -h localhost -p 5432 -d cmd_catalog -f db/render_guarantee_schema.sql   (idempotent — safe to re-run)
--  Read by the atomic accessors in config/*.py (each a thin reader over its table).  Spec: V48_RENDER_GUARANTEE_CONTRACT.md
-- ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════

-- ── asset_nameplate ── rated/contract/nominal/role/section per neuract asset table (kills fabricated capacity:60 + hardcoded dict)
--    seeded from cmd_equipment.public.mfm (302) cross-ref + name-token grammar + per-class engineering defaults [RN-01/02/05/07, DS-10, DID-03, VC-05]
CREATE TABLE IF NOT EXISTS asset_nameplate (
    asset_table       text PRIMARY KEY,          -- neuract table_name (the physical meter table) — the stable join key
    mfm_name          text,                       -- neuract lt_mfm.name (human label)
    rated_kva         numeric,                    -- nameplate rating (denominator for loading% / headroom)
    contracted_kva    numeric,                    -- contracted / sanctioned demand (NULL if unknown)
    nominal_voltage_ll numeric,                   -- nominal line-line voltage (V)
    role              text,                       -- incoming | outgoing | spare | coupler (from cmd_equipment.mfm.role)
    section           text,                       -- HT | LT | … (from cmd_equipment.mfm.section)
    asset_category    text,                       -- UPS | Transformer | APFCR | HT Panel | … (class bucket)
    source            text                        -- provenance: cmd_equipment | name_parse | class_default | none
);

-- ── asset_class_default ── per-CLASS engineering defaults (policy/limit knobs a per-asset nameplate can't carry) ─────
--    asset_category → default JSON (contracted_frac, statutory band, THD limits, UPS battery bands, DG service knobs).
--    Resolution: per-asset nameplate row → this class default → None. NEVER a fabricated rated_kva (rating stays honest
--    per-asset). Ported from CMD/backend2/core/config_defaults.py. Read by config/asset_class_defaults.py. [#12 port]
CREATE TABLE IF NOT EXISTS asset_class_default (
    asset_category text PRIMARY KEY,               -- class bucket: Transformer | Distribution Panel | LT Panel | DG | UPS
    default_json   jsonb                            -- {contracted_frac, voltage_statutory_deviation_pct, thd_*_limit_pct, ready_threshold, …}
);

-- ── schema_slot_map ── per-fingerprint routed column map: which physical column feeds which logical slot [DS-03/07]
--    fingerprint ∈ {p1_72, tm_ups_56, feedbacks_35, ng_se_jk_70, sch_stub_3, …}
CREATE TABLE IF NOT EXISTS schema_slot_map (
    fingerprint  text,                            -- schema family key
    slot         text,                            -- logical slot: active_power_total_kw, voltage_ll_avg, energy_import, …
    column_name  text,                            -- the real physical column that fills the slot ('' → slot not present)
    unit         text,                            -- kW | kVA | V | A | kWh | pct | … (unit guard for the snap)
    quantity     text,                            -- active_power | apparent_power | voltage | current | energy | pf | thd
    PRIMARY KEY (fingerprint, slot)
);

-- ── metric_class ── which column-CLASS each page requires (per-(asset,page) feasibility gate) [DS-07, class-vs-page]
--    a page routes only to a meter whose table actually exposes required_class.
CREATE TABLE IF NOT EXISTS metric_class (
    page_key       text,                          -- ems page code (e.g. energy-power, power-quality, voltage-current)
    required_class text,                           -- power | energy | voltage | current | pf | thd | breaker | …
    PRIMARY KEY (page_key, required_class)
);

-- ── data_quality_policy ── the numeric/threshold policy knobs (VALUE_MIN, denorm ε, reversed-CT max, meaningful-power) [DS-01/04/05/06]
CREATE TABLE IF NOT EXISTS data_quality_policy (
    key       text PRIMARY KEY,                   -- policy knob name
    num_value numeric,                            -- numeric value (NULL if txt policy)
    txt_value text,                               -- text value (NULL if numeric policy)
    note      text                                -- human note on what the knob governs
);

-- ── derivation_binding ── only recovery fns whose base_columns ⊆ present may bind (fn / base / fidelity) [DID-02/05, DS-04]
CREATE TABLE IF NOT EXISTS derivation_binding (
    metric       text PRIMARY KEY,                -- logical derived metric (e.g. windowEnergyKwh, thdComplianceIeee519)
    fn           text,                            -- registry fn name that computes it
    base_columns text,                            -- comma-separated real columns the fn needs (⊆ present ⇒ bindable)
    fidelity     text                             -- real_exact | recovered | approx
);

-- ── reason_template ── machine-readable → human reason strings (honest-blank causes) [ER-6/2, systemic reason channel]
CREATE TABLE IF NOT EXISTS reason_template (
    cause    text PRIMARY KEY,                    -- machine cause key (no_data, no_history, no_nameplate, reversed_ct, …)
    template text                                 -- human template ('no data logged for {asset}', …)
);

-- ── endpoint_policy ── per (page,scope) endpoint + expected frame shape + is_history + pre-validation [ER-1/2/4/5/7/8]
CREATE TABLE IF NOT EXISTS endpoint_policy (
    page_key       text,                          -- ems page code
    resolver_scope text,                          -- single_asset | panel_aggregate | topology (the resolved asset scope)
    endpoint       text,                          -- the ems_backend WS endpoint to open
    expected_shape text,                          -- queue | buckets | widgets (what the card's fill mapper reads)
    is_history     boolean,                       -- date-navigable history endpoint?
    PRIMARY KEY (page_key, resolver_scope)
);

-- (render_spec REMOVED 2026-07-02 — it was the retired Layer 3's output cache; the render verdict is now derived
--  in host/server.py::_card_leaf_stats from the ems_exec-completed payload. Rows archived: archive/render_spec_rows_*.json)

-- ── render_guarantee_matrix ── the EDITABLE acceptance-suite prompt matrix (which failure-mode asset×page×window each
--    of the 50-prompt render-guarantee prompts must exercise). Lives in cmd_catalog (UP even when the live DATA DB is
--    down) so the matrix ENUMERATES from config — never collapses to 0 on a tunnel outage. asset_selector is a stable
--    class/name predicate the test resolves against the LIVE registry when reachable; asset_name_hint is the DATA-DB-
--    independent fallback label (from the audit) used to still build the phrasing when the registry is unavailable.
--    NO hardcoded prompt literals in the test — every row here is an editable policy. [test-design coupling fix]
CREATE TABLE IF NOT EXISTS render_guarantee_matrix (
    tag             text PRIMARY KEY,             -- failure-mode class key (populated_feeder, empty_meter, pcc_aggregate, history_30d, …)
    asset_selector  text,                         -- registry predicate: 'class=UPS&has_data', 'name~ups-04', 'name~pcc-panel-1', 'class=UPS&!has_data', …
    asset_name_hint text,                         -- DATA-DB-independent fallback asset label (audit-named) when the live registry is down
    page_glob       text,                         -- page_key or shell-glob the prompt routes to (e.g. 'individual-feeder-meter-shell/energy-power', 'individual-feeder-meter-shell/*')
    time_window     text,                         -- '' | 'last_30d' | 'ytd' | 'this_month' — trailing window the phrasing requests (DS-02)
    phrasing        text,                         -- NL phrasing template with {a} for the asset name ('energy and power for {a}')
    enabled         boolean DEFAULT true,         -- toggle a row out without deleting it
    note            text                          -- audit ref / human note
);

-- ── render_guarantee_page_phrase ── editable page-segment → NL verb-phrase (the {page} token in a matrix phrasing). ─
--    Keyed by the last segment of page_key (energy-power, real-time-monitoring, …). Kept as DB rows so the natural-
--    language wording that routes each EMS page is editable too — no phrasing hardcoded in the test accessor.
CREATE TABLE IF NOT EXISTS render_guarantee_page_phrase (
    page_seg text PRIMARY KEY,                    -- last segment of page_key (e.g. 'energy-power')
    phrase   text                                 -- the NL phrase that routes that page (e.g. 'energy and power')
);
