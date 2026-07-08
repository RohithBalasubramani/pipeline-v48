"""data/equipment — LOCAL cmd_catalog `equipment` schema readers (:5432 ONLY — never the :5433 neuract tunnel).

Rules for every module here:
  (a) bridge id spaces ONLY via table_name — equipment.mfm.id is NOT canonical lt_mfm.id, and
      equipment_id/reference_id have MIXED semantics (use bridge.identity_node, never a raw hop);
  (b) fail-open: any DB error / missing row -> None/''/{} so callers stay byte-identical to today —
      and failures are NEVER cached (retry next call);
  (c) facts only: energy_direction/energy_scale/power_scale are surfaced to the AI, NEVER applied to readings.

Modules: db (the one accessor), bridge+edges (stream A: table bridge, identity gate, bay-anchored
allowlisted rosters), ratings (stream B), kitpreview (stream D 3D).
"""
