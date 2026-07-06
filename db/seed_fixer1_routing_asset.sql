-- db/seed_fixer1_routing_asset.sql — FIXER 1 (routing + asset) hardening rows. Idempotent (upsert). 2026-07-03
-- Backup of the pre-change rows: outputs/audit_db/backups/fixer1_routing_asset_rows_*.jsonl

-- ── 1. metric vocabulary: add the asset-page quantities the 8-keyword enum could not express ────────────────────────
-- (dg fuel/SFC, oil pressure, tank level, run-hours, battery SOH, tap position). New words APPENDED so existing
-- containment precedence is unchanged. config/metrics.py reads these via cfg(); layer1a/prompts/system.md renders
-- {{METRIC_VOCAB}} from the same row, so prompt and clamp can never drift.
UPDATE app_config SET value = '["current", "voltage", "power", "energy", "thd", "pf", "frequency", "temperature", "fuel", "pressure", "level", "runtime", "soh", "tap"]',
                      updated_at = now(),
                      note = 'canonical 1a metric keywords; extended 2026-07-03 with asset-page quantities (fuel/pressure/level/runtime/soh/tap) [hardening: metric vocab vs asset pages]'
WHERE key = 'metrics.vocab';

UPDATE app_config SET value = '{"power factor": "pf", "reactive power": "pf", "powerfactor": "pf", "harmonic distortion": "thd", "harmonics": "thd", "total harmonic distortion": "thd", "distortion": "thd", "power quality": "thd", "pq": "thd", "voltage/current": "voltage", "current/voltage": "voltage", "voltage and current": "voltage", "amps": "current", "ampere": "current", "amperage": "current", "amperes": "current", "volt": "voltage", "volts": "voltage", "kv": "voltage", "kw": "power", "kva": "power", "kilowatt": "power", "load": "power", "demand": "power", "supply": "power", "kwh": "energy", "consumption": "energy", "kwh consumption": "energy", "temp": "temperature", "thermal": "temperature", "heat": "temperature", "freq": "frequency", "hz": "frequency", "sfc": "fuel", "diesel consumption": "fuel", "fuel rate": "fuel", "fuel consumption": "fuel", "oil pressure": "pressure", "tank level": "level", "fuel level": "level", "state of health": "soh", "battery health": "soh", "tap position": "tap", "tap changer": "tap", "run hours": "runtime", "running hours": "runtime", "operating hours": "runtime", "autonomy": "runtime"}',
                      updated_at = now(),
                      note = 'metric phrase->keyword aliases; extended 2026-07-03 with asset-page phrases [hardening]'
WHERE key = 'metrics.aliases';

-- ── 2. new DB knobs (code defaults identical — rows make them visible/editable) ─────────────────────────────────────
INSERT INTO app_config (key, value, data_type, section, note) VALUES
  ('reflect.min_gap_frac', '0.34', 'number', 'reflect',
   'min fraction of gap cards (gaps/cards) required to re-route the whole page; below it the gapped cards honest-blank per-leaf. [hardening: 1-of-N reroute]'),
  ('route.card_titles_max', '400', 'int', 'layer1a',
   'per-page card-title evidence cap in the 1a candidate block (was hardcoded 160 — truncated the two most card-rich panel pages mid-word). [hardening]'),
  ('layer1b.has_data_window_rows', '20', 'int', 'layer1b',
   'rows in the window col_dict.window_nonnull scans for the per-column has_data(Y/N) basket flag (was latest-row-only). [hardening]'),
  ('llm.timeout.asset_resolve', '60', 'int', 'llm',
   '1b asset-resolve call timeout seconds (was hardcoded 60 at the call site). [hardening: DB-driven timeouts]'),
  ('layer1b.class_concept_hints',
   '{"UPS": {"tokens": ["ups"], "concepts": ["battery", "backup", "autonomy", "inverter", "rectifier"]}, "DG": {"tokens": ["dg", "diesel", "genset", "generator"], "concepts": ["fuel", "engine", "runtime"]}, "Transformer": {"tokens": ["transformer", "xformer", "tf"], "concepts": ["tap", "winding", "oil temp", "oil-temp", "hv-lv", "hvlv"]}, "APFCR": {"tokens": ["apfc", "apfcr"], "concepts": ["capacitor", "kvar", "power factor bank", "pf bank", "reactive comp"]}, "Incomer": {"tokens": ["incomer", "incoming"], "concepts": ["11kv", "ht incomer", "grid incomer"]}, "AHU": {"tokens": ["ahu"], "concepts": ["air handling", "air-handling"]}, "AirWasher": {"tokens": ["airwasher", "air washer", "air-washer"], "concepts": []}, "Chiller": {"tokens": ["chiller"], "concepts": []}, "Pump": {"tokens": ["pump"], "concepts": []}, "Compressor": {"tokens": ["compressor"], "concepts": []}, "Fan": {"tokens": ["fan"], "concepts": ["exhaust", "blower"]}, "Feeder": {"tokens": ["feeder"], "concepts": ["outgoing"]}, "Panel": {"tokens": ["pcc", "mcc", "bpdb", "mldb", "pdb", "panel"], "concepts": ["busbar", "bus bar", "distribution board"]}, "Spare": {"tokens": ["spare"], "concepts": []}}',
   'json', 'layer1b',
   'class prior hint grammar: explicit class tokens outrank ambient concepts; >1 class hit in the deciding pass = no narrowing. runtime moved UPS->DG (page-13 DG-1 root cause). [hardening]')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, data_type = EXCLUDED.data_type,
                                section = EXCLUDED.section, note = EXCLUDED.note, updated_at = now();

-- ── 3. cards profile drift on the ROUTABLE surface (1a router card-titles line + L2 card profile) ───────────────────
-- card 81 (transformer-asset-dashboard/tap-rtcc): the whole profile described a DIFFERENT card ('Loss Analysis' /
-- TapPositionGauge). card_handling + card_data_recipe agree the real card is 'Tap Activity & Wear' (ChartBars,
-- tap-operations counts). Re-authored from the real component.
UPDATE cards SET
  title = 'Tap Activity & Wear',
  primary_component = 'ChartBars',
  card_purpose = 'Counts tap-changer (OLTC) operations over the window — hourly activity bars plus the cumulative lifetime counter — tracks today''s total against typical activity, and estimates remaining contact life from the rated maximum.',
  user_question = 'How often is this transformer''s tap changer operating, is today''s activity abnormal, and how much contact life remains?',
  output_insight = 'An hourly tap-operations bar series with a cumulative lifetime counter, KPI tiles for total operations today / peak hour / average, a contact-life-remaining estimate, and a wear narrative.',
  decision_support = 'Flags hunting/excessive tap activity (upstream voltage-regulation instability), schedules OLTC contact inspection by remaining contact life, and separates normal daily activity from abnormal operation bursts.',
  visualization = 'ChartBars hourly operations bar chart with a cumulative counter overlay, KPI tiles (total today, peak hour, average), contact-life remaining (million ops) and a wear-estimate narrative.',
  sem_card_name = 'Tap Activity & Wear',
  sem_purpose = 'Count tap-changer operations and estimate OLTC contact wear',
  sem_answers = 'How often the tap changer operates, whether today''s activity is abnormal, and the remaining contact life'
WHERE id = 81;

-- card 74: cosmetic title drift vs card_handling ('Thermal & Life' vs 'Thermal Life') on routable thermal-life page.
UPDATE cards SET title = 'Thermal Life' WHERE id = 74;

-- ── 4. page_specs.archetype de-collide (router discriminator): THREE candidate pages all read '[Power Quality]', and
-- panel harmonics-pq collided too — anti-discriminative for exactly the vc-vs-pq near-tie. Only the routing candidate
-- block renders archetype (layer1a/route.py; copilot reads its own copy), so this is a safe re-label.
-- individual-feeder-meter-shell/power-quality KEEPS 'Power Quality' (it IS the PQ page).
UPDATE page_specs SET archetype = 'Voltage & Current Health' WHERE page_key = 'individual-feeder-meter-shell/voltage-current';
UPDATE page_specs SET archetype = 'Panel Voltage/Current & PQ Events Triage' WHERE page_key = 'panel-overview-shell/voltage-current';
UPDATE page_specs SET archetype = 'Harmonics & THD Compliance' WHERE page_key = 'panel-overview-shell/harmonics-pq';
