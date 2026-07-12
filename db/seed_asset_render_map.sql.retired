-- db/seed_asset_render_map.sql — idempotent card_render_map rows for the 34 asset deep-tab cards (ids 50-81).
-- [atomic, DB-driven, additive] Mirrors the existing feeder/panel convention: one PER-PAGE fill module under
-- host/web/src/cmd/fill/, status 'fill' (data-fill page, not 'compose'). card_render_map has NO runtime consumer yet
-- (planning/metadata table), so these rows DECLARE the intended fill module per asset page.
--
-- STATUS: re-derived FROM LIVE 2026-07-06 — the asset-page fill modules SHIPPED (host/web/src/cmd/fill/ups-*.tsx,
-- dg-*.tsx, transformer-*.tsx exist on disk) and live rows were flipped to status='fill'; this seed now mirrors that.
--
-- Idempotent: ON CONFLICT (page_key, card_id) DO UPDATE. Run:
--   psql -h localhost -p 5432 -d cmd_catalog -f db/seed_asset_render_map.sql

INSERT INTO card_render_map (page_key, card_id, fill_module, status) VALUES
 -- UPS · Battery & Autonomy
 ('ups-asset-dashboard/battery-autonomy',                50, 'host/web/src/cmd/fill/ups-battery-autonomy.tsx',       'fill'),
 ('ups-asset-dashboard/battery-autonomy',                51, 'host/web/src/cmd/fill/ups-battery-autonomy.tsx',       'fill'),
 ('ups-asset-dashboard/battery-autonomy',                52, 'host/web/src/cmd/fill/ups-battery-autonomy.tsx',       'fill'),
 ('ups-asset-dashboard/battery-autonomy',                53, 'host/web/src/cmd/fill/ups-battery-autonomy.tsx',       'fill'),
 -- UPS · Source & Transfer
 ('ups-asset-dashboard/source-transfer',                 54, 'host/web/src/cmd/fill/ups-source-transfer.tsx',        'fill'),
 ('ups-asset-dashboard/source-transfer',                 55, 'host/web/src/cmd/fill/ups-source-transfer.tsx',        'fill'),
 ('ups-asset-dashboard/source-transfer',                 56, 'host/web/src/cmd/fill/ups-source-transfer.tsx',        'fill'),
 -- UPS · Output & Load Capacity
 ('ups-asset-dashboard/output-load-capacity',            57, 'host/web/src/cmd/fill/ups-output-load-capacity.tsx',   'fill'),
 ('ups-asset-dashboard/output-load-capacity',            58, 'host/web/src/cmd/fill/ups-output-load-capacity.tsx',   'fill'),
 ('ups-asset-dashboard/output-load-capacity',            59, 'host/web/src/cmd/fill/ups-output-load-capacity.tsx',   'fill'),
 -- DG · Engine & Cooling
 ('diesel-generator-asset-dashboard/engine-cooling',     60, 'host/web/src/cmd/fill/dg-engine-cooling.tsx',          'fill'),
 ('diesel-generator-asset-dashboard/engine-cooling',     61, 'host/web/src/cmd/fill/dg-engine-cooling.tsx',          'fill'),
 ('diesel-generator-asset-dashboard/engine-cooling',     62, 'host/web/src/cmd/fill/dg-engine-cooling.tsx',          'fill'),
 -- DG · Fuel & Efficiency
 ('diesel-generator-asset-dashboard/fuel-efficiency',    63, 'host/web/src/cmd/fill/dg-fuel-efficiency.tsx',         'fill'),
 ('diesel-generator-asset-dashboard/fuel-efficiency',    64, 'host/web/src/cmd/fill/dg-fuel-efficiency.tsx',         'fill'),
 ('diesel-generator-asset-dashboard/fuel-efficiency',    65, 'host/web/src/cmd/fill/dg-fuel-efficiency.tsx',         'fill'),
 -- DG · Voltage & Current
 ('diesel-generator-asset-dashboard/voltage-current',    66, 'host/web/src/cmd/fill/dg-voltage-current.tsx',         'fill'),
 ('diesel-generator-asset-dashboard/voltage-current',    67, 'host/web/src/cmd/fill/dg-voltage-current.tsx',         'fill'),
 ('diesel-generator-asset-dashboard/voltage-current',    68, 'host/web/src/cmd/fill/dg-voltage-current.tsx',         'fill'),
 ('diesel-generator-asset-dashboard/voltage-current',    69, 'host/web/src/cmd/fill/dg-voltage-current.tsx',         'fill'),
 -- DG · Operations & Runtime
 ('diesel-generator-asset-dashboard/operations-runtime', 70, 'host/web/src/cmd/fill/dg-operations-runtime.tsx',      'fill'),
 ('diesel-generator-asset-dashboard/operations-runtime', 71, 'host/web/src/cmd/fill/dg-operations-runtime.tsx',      'fill'),
 ('diesel-generator-asset-dashboard/operations-runtime', 72, 'host/web/src/cmd/fill/dg-operations-runtime.tsx',      'fill'),
 ('diesel-generator-asset-dashboard/operations-runtime', 73, 'host/web/src/cmd/fill/dg-operations-runtime.tsx',      'fill'),
 -- Transformer · Thermal & Life
 ('transformer-asset-dashboard/thermal-life',            74, 'host/web/src/cmd/fill/transformer-thermal-life.tsx',   'fill'),
 ('transformer-asset-dashboard/thermal-life',            75, 'host/web/src/cmd/fill/transformer-thermal-life.tsx',   'fill'),
 ('transformer-asset-dashboard/thermal-life',            76, 'host/web/src/cmd/fill/transformer-thermal-life.tsx',   'fill'),
 ('transformer-asset-dashboard/thermal-life',            77, 'host/web/src/cmd/fill/transformer-thermal-life.tsx',   'fill'),
 -- Transformer · Tap & RTCC
 ('transformer-asset-dashboard/tap-rtcc',                78, 'host/web/src/cmd/fill/transformer-tap-rtcc.tsx',       'fill'),
 ('transformer-asset-dashboard/tap-rtcc',                79, 'host/web/src/cmd/fill/transformer-tap-rtcc.tsx',       'fill'),
 ('transformer-asset-dashboard/tap-rtcc',                80, 'host/web/src/cmd/fill/transformer-tap-rtcc.tsx',       'fill'),
 ('transformer-asset-dashboard/tap-rtcc',                81, 'host/web/src/cmd/fill/transformer-tap-rtcc.tsx',       'fill')
ON CONFLICT (page_key, card_id) DO UPDATE SET
  fill_module = EXCLUDED.fill_module,
  status      = EXCLUDED.status;
