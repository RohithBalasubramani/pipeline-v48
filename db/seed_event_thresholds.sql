-- db/seed_event_thresholds.sql — EDITABLE numeric power-quality event bands for services.fetch_events.fetch_threshold_events.
-- The simulator's boolean *_event_active flags never fire, so the V&C event_timeline / sag-swell KPIs must detect events
-- off the RAW numeric columns crossing statutory limits (P0 #7). Each row is one detector spec (alias, column, direction,
-- threshold) read by config/event_thresholds.py. NO magic number in any consumer — retune a band by editing a ROW here.
-- Idempotent (CREATE IF NOT EXISTS + ON CONFLICT upsert). Run:
--   psql -h localhost -p 5432 -d cmd_catalog -f db/seed_event_thresholds.sql

-- ── event_threshold ── (alias, column_name, direction, num_value) numeric rising-edge event detector specs ───────────
--    direction ∈ {'below','above'}: 'below' = a falling crossing (value < threshold, e.g. voltage sag);
--                                    'above' = a rising crossing (value > threshold, e.g. current unbalance).
CREATE TABLE IF NOT EXISTS event_threshold (
    alias       text PRIMARY KEY,   -- wire event type / detector key (SAG, SWELL, I_UNBAL, NEUTRAL, I_THD, V_THD, TRUE_PF)
    column_name text,               -- physical numeric column the crossing is measured on
    direction   text,               -- 'below' | 'above' (crossing direction that fires the event)
    num_value   numeric,            -- the threshold value
    note        text                -- human note on the standard / band it encodes
);

INSERT INTO event_threshold (alias, column_name, direction, num_value, note) VALUES
 ('SAG',     'kpi_voltage_deviation_pct', 'below', -10.0, 'IS-12360 / IEEE-1159 sustained voltage sag: deviation < -10%'),
 ('SWELL',   'kpi_voltage_deviation_pct', 'above',  10.0, 'IS-12360 / IEEE-1159 sustained voltage swell: deviation > +10%'),
 ('I_UNBAL', 'current_unbalance_pct',     'above',  10.0, 'current-unbalance statutory limit: unbalance > 10%'),
 ('NEUTRAL', 'current_neutral',           'above',  30.0, 'neutral-current stress: neutral current > 30 A'),
 ('I_THD',   'thd_compliance_i_avg',      'above',   8.0, 'IEEE-519 current-THD compliance headroom crossed: > 8%'),
 ('V_THD',   'thd_compliance_v_avg',      'above',   5.0, 'IEEE-519 voltage-THD compliance headroom crossed: > 5%'),
 ('TRUE_PF', 'kpi_true_pf',               'below',   0.9, 'true power-factor floor: PF < 0.9 → PF-gap event')
ON CONFLICT (alias) DO UPDATE SET
    column_name = EXCLUDED.column_name,
    direction   = EXCLUDED.direction,
    num_value   = EXCLUDED.num_value,
    note        = EXCLUDED.note;
