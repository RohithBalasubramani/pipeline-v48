-- seed_asset_name_class_vocab.sql — the 1b table-name→equipment-class fallback vocabulary as an editable row
-- (hardcoded-mappings sweep, refactor audit 2026-07-12). Mirrors layer1b/resolve/asset_candidates.py _NAME_CLASS
-- byte-for-byte (json [[needles…], class] pairs, ORDER PRESERVED — UPS before Panel, Incomer before DG) —
-- behavior-identical until edited; a new plant's naming tokens then extend with a row edit, no code change.
-- Reader: asset_candidates._name_class_rules(). NOTE: 'dg_' keeps its startswith semantics in code.
INSERT INTO app_config (key, value, data_type, section, note) VALUES
  ('vocab.asset_name_class',
   '[[["ups"], "UPS"],
     [["transformer", "xformer", "_tfr"], "Transformer"],
     [["ahu"], "AHU"],
     [["air_washer", "airwasher"], "AirWasher"],
     [["chiller"], "Chiller"],
     [["apfc"], "APFCR"],
     [["pump"], "Pump"],
     [["compressor", "_comp"], "Compressor"],
     [["incomer", "_inc_", "incoming"], "Incomer"],
     [["dg_", "_dg_", "diesel", "generator"], "DG"],
     [["exhaust", "_fan", "fan_"], "Fan"],
     [["feeder"], "Feeder"],
     [["bpdb", "pdb", "pcc", "mcc", "mldb", "_db", "panel", "lamination", "packing", "curing"], "Panel"],
     [["electrical_room", "elec_room"], "ElectricalRoom"],
     [["spare"], "Spare"]]',
   'json', 'vocab',
   'ordered [[needles], class] table-name fallback vocabulary for 1b asset-class resolution; mirrors asset_candidates.py _NAME_CLASS')
ON CONFLICT (key) DO NOTHING;
