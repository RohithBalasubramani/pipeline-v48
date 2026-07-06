-- db/seed_asset_backend_strategy.sql — ADDITIVE UPDATE of card_handling.backend_strategy for the 34 asset deep-tab
-- cards (ids 50-81) so Layer 2 binds each asset card's data-slots to the MAIN V48 pipeline against NEURACT — NOT the
-- simulator (assets/consumers/*) paths that several rows wrongly carried. [atomic, DB-driven, idempotent]
--
-- CONVENTION (mirrors the individual-feeder-meter-shell cards 28-49, the routable "single asset meter -> neuract"
-- pattern): backend_strategy = 'consumers/<neuract-screen>/lt_panel.py'. layer2/emit/data/consumer_binding/
-- screen_map.canonical_screen() takes the segment AFTER 'consumers/' (hyphenated) as the card's neuract screen; that
-- string MUST be one of ems_backend's LIVE endpoints (endpoint_registry.LIVE_ENDPOINTS): overview,
-- real-time-monitoring, energy-power, energy-power-history, demand-profile, load-anomalies, energy-distribution,
-- voltage-current, voltage-history, current-history, power-quality-summary. All values below use ONLY those, so the
-- AI's endpoint choice stays on-domain. Tiles/table cards -> the LIVE screen; flat_series (trend) cards -> the
-- in-domain HISTORY variant where one exists, else the live screen (exactly as feeder cards 43-46 do
-- voltage-current/voltage-history/current-history).
--
-- These are NOT the ems_backend/assets simulator consumers (that path is owned by other work); we deliberately point
-- at the real per-meter neuract screens via lt_panel, same as the feeder shell. Idempotent: pure UPDATE by card_id
-- (rows already exist — pages/cards were NOT re-inserted). Re-runnable with no drift.
-- Run: psql -h localhost -p 5432 -d cmd_catalog -f db/seed_asset_backend_strategy.sql

BEGIN;

-- UPS (Asset · UPS, ids 50-59)
UPDATE card_handling SET backend_strategy='consumers/voltage_current/lt_panel.py'      WHERE card_id=50;  -- Battery Health (SOC/DC-V, live)
UPDATE card_handling SET backend_strategy='consumers/voltage_history/lt_panel.py'      WHERE card_id=51;  -- Battery Health History
UPDATE card_handling SET backend_strategy='consumers/energy_power/lt_panel.py'         WHERE card_id=52;  -- Backup Readiness (autonomy vs load)
UPDATE card_handling SET backend_strategy='consumers/energy_power_history/lt_panel.py' WHERE card_id=53;  -- Backup Readiness History
UPDATE card_handling SET backend_strategy='consumers/real_time_monitoring/lt_panel.py' WHERE card_id=54;  -- Transfer readiness (source/breaker state)
UPDATE card_handling SET backend_strategy='consumers/real_time_monitoring/lt_panel.py' WHERE card_id=55;  -- Activity (transfer event ticks)
UPDATE card_handling SET backend_strategy='consumers/real_time_monitoring/lt_panel.py' WHERE card_id=56;  -- Source Transfer — Composite
UPDATE card_handling SET backend_strategy='consumers/energy_power/lt_panel.py'         WHERE card_id=57;  -- UPS Capacity (kVA/load capacity)
UPDATE card_handling SET backend_strategy='consumers/energy_power_history/lt_panel.py' WHERE card_id=58;  -- UPS Load
UPDATE card_handling SET backend_strategy='consumers/energy_power_history/lt_panel.py' WHERE card_id=59;  -- Output Load & Capacity — Composite

-- Diesel Generator (Asset · DG, ids 60-73)
UPDATE card_handling SET backend_strategy='consumers/real_time_monitoring/lt_panel.py' WHERE card_id=60;  -- Engine 3D Callout Viewer (asset_3d live snapshot)
UPDATE card_handling SET backend_strategy='consumers/energy_power_history/lt_panel.py' WHERE card_id=61;  -- Thermal Timeline (load-driven trend)
UPDATE card_handling SET backend_strategy='consumers/energy_power_history/lt_panel.py' WHERE card_id=62;  -- Pressure · Speed · Load
UPDATE card_handling SET backend_strategy='consumers/real_time_monitoring/lt_panel.py' WHERE card_id=63;  -- Fuel Tank Anatomy (asset_3d snapshot)
UPDATE card_handling SET backend_strategy='consumers/energy_power/lt_panel.py'         WHERE card_id=64;  -- All Runs (Fuel Log) — run/energy log
UPDATE card_handling SET backend_strategy='consumers/energy_power_history/lt_panel.py' WHERE card_id=65;  -- Fuel & Tank — Composite
UPDATE card_handling SET backend_strategy='consumers/voltage_current/lt_panel.py'      WHERE card_id=66;  -- Voltage Live Health
UPDATE card_handling SET backend_strategy='consumers/voltage_history/lt_panel.py'      WHERE card_id=67;  -- Voltage History
UPDATE card_handling SET backend_strategy='consumers/voltage_current/lt_panel.py'      WHERE card_id=68;  -- Current Live Health
UPDATE card_handling SET backend_strategy='consumers/current_history/lt_panel.py'      WHERE card_id=69;  -- Current History
UPDATE card_handling SET backend_strategy='consumers/real_time_monitoring/lt_panel.py' WHERE card_id=70;  -- Live Operations & Runtime
UPDATE card_handling SET backend_strategy='consumers/energy_power_history/lt_panel.py' WHERE card_id=71;  -- Runtime & Duty
UPDATE card_handling SET backend_strategy='consumers/energy_power/lt_panel.py'         WHERE card_id=72;  -- Energy & Reliability
UPDATE card_handling SET backend_strategy='consumers/energy_power/lt_panel.py'         WHERE card_id=73;  -- Power Energy Analysis

-- Transformer / Source (Asset · Transformer / Source, ids 74-81)
UPDATE card_handling SET backend_strategy='consumers/real_time_monitoring/lt_panel.py' WHERE card_id=74;  -- Thermal Life (live thermal/health)
UPDATE card_handling SET backend_strategy='consumers/energy_power/lt_panel.py'         WHERE card_id=75;  -- Life & Capacity (loading vs capacity)
UPDATE card_handling SET backend_strategy='consumers/energy_power_history/lt_panel.py' WHERE card_id=76;  -- Thermal Timeline
UPDATE card_handling SET backend_strategy='consumers/energy_power_history/lt_panel.py' WHERE card_id=77;  -- Insulation Aging & Loss of Life
UPDATE card_handling SET backend_strategy='consumers/voltage_current/lt_panel.py'      WHERE card_id=78;  -- Tap Position Optimization (voltage regulation)
UPDATE card_handling SET backend_strategy='consumers/voltage_history/lt_panel.py'      WHERE card_id=79;  -- Voltage Regulation Timeline
UPDATE card_handling SET backend_strategy='consumers/voltage_current/lt_panel.py'      WHERE card_id=80;  -- Recent Tap Changes
UPDATE card_handling SET backend_strategy='consumers/voltage_history/lt_panel.py'      WHERE card_id=81;  -- Tap Activity & Wear

COMMIT;
