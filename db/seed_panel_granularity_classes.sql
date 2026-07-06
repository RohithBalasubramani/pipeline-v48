-- db/seed_panel_granularity_classes.sql — the granularity reconcile now keys on asset CLASS, not has_feeders:
-- the panel-overview (aggregate) shell is the home of Panel-class assets only. A Transformer/DG/UPS with downstream
-- feeders is a single asset whose OWN meter renders on the meter shell (was wrongly forced onto panel-overview →
-- validation fail + dead cards). Idempotent; code default is ['Panel'].
INSERT INTO app_config (key, value, data_type, section) VALUES
 ('routes.panel_granularity_classes', '["Panel"]', 'json', 'routes')
ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, data_type=EXCLUDED.data_type, section=EXCLUDED.section;
