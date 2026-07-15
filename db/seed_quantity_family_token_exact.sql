-- db/seed_quantity_family_token_exact.sql — T2.2-S2: DEFAULT OFF (byte-identical).
-- quantity.family_token_exact — read by layer2/cross_domain._token_exact_on. ON => the cross-domain honesty pass
-- classifies both sides with domain.quantity_class's TOKEN-EXACT slot_class/name_class + the weak/dimensional
-- compatible() grants instead of config.metrics.quantity_family's longest-STEM SUBSTRING scan (which false-positives:
-- 'boiler' -> temperature via the 'oil' stem inside b-OIL-er). OFF => the verbatim substring path, byte-identical.
-- The wall_corpus_replay baseline (gate_roster + enforce_honest_blank) is UNAFFECTED (cross_domain is a separate gate).
INSERT INTO app_config (key, value, data_type, section, note) VALUES
 ('quantity.family_token_exact', 'off', 'text', 'quantity',
  'T2.2-S2: on = cross_domain uses token-exact quantity_class classifiers (no substring false-positives); off = legacy quantity_family substring, byte-identical (layer2/cross_domain.py)')
ON CONFLICT (key) DO NOTHING;
