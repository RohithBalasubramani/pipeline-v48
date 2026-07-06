-- db/seed_routable_pages.sql — the DB-driven routable-page allow-list read by config/available_pages.py.
-- One page_key per row; enabled=false disables a page without deleting it. Idempotent (ON CONFLICT). The code-default
-- in config/available_pages.AVAILABLE_PAGES is the DB-down fallback; this table lets ops toggle routing with no deploy.
-- Adds the 9 asset deep-tab pages alongside the original 9 built pages. Run:
--   psql -h localhost -p 5432 -d cmd_catalog -f db/seed_routable_pages.sql

CREATE TABLE IF NOT EXISTS routable_pages (
    page_key text PRIMARY KEY,
    enabled  boolean NOT NULL DEFAULT true,
    note     text
);

INSERT INTO routable_pages (page_key, note) VALUES
 ('panel-overview-shell/energy-distribution',            'Energy & Distribution'),
 ('panel-overview-shell/energy-power',                   'Energy & Power'),
 ('panel-overview-shell/harmonics-pq',                   'Harmonics & PQ'),
 ('panel-overview-shell/real-time-monitoring',           'Real-Time Monitoring'),
 ('panel-overview-shell/voltage-current',                'Voltage & Current'),
 ('individual-feeder-meter-shell/voltage-current',       'Feeder Voltage & Current'),
 ('individual-feeder-meter-shell/real-time-monitoring',  'Feeder Real-Time Monitoring'),
 ('individual-feeder-meter-shell/energy-power',          'Feeder Energy & Power'),
 ('individual-feeder-meter-shell/power-quality',         'Feeder Power Quality'),
 ('diesel-generator-asset-dashboard/engine-cooling',     'DG Engine & Cooling (asset deep-tab)'),
 ('diesel-generator-asset-dashboard/fuel-efficiency',    'DG Fuel Efficiency (asset deep-tab)'),
 ('diesel-generator-asset-dashboard/operations-runtime', 'DG Operations & Runtime (asset deep-tab)'),
 ('diesel-generator-asset-dashboard/voltage-current',    'DG Voltage & Current (asset deep-tab)'),
 ('transformer-asset-dashboard/tap-rtcc',                'Transformer Tap & RTCC (asset deep-tab)'),
 ('transformer-asset-dashboard/thermal-life',            'Transformer Thermal & Life (asset deep-tab)'),
 ('ups-asset-dashboard/battery-autonomy',                'UPS Battery & Autonomy (asset deep-tab)'),
 ('ups-asset-dashboard/output-load-capacity',            'UPS Output & Load Capacity (asset deep-tab)'),
 ('ups-asset-dashboard/source-transfer',                 'UPS Source & Transfer (asset deep-tab)')
ON CONFLICT (page_key) DO UPDATE SET note = EXCLUDED.note;
