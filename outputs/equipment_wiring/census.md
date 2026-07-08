# Equipment schema census (cmd_catalog @:5432, schema `equipment`)

Generated 2026-07-08 by census agent. All text ascii-replaced.

## equipment.asset_meter  (29 rows)

| column | type | non-null |
|---|---|---|
| id | bigint | 29/29 |
| name | character varying | 29/29 |
| role | character varying | 29/29 |
| table_name | character varying | 29/29 |
| series_id | character varying | 29/29 |
| sheet_row | integer | 29/29 |
| section | character varying | 29/29 |
| zone | character varying | 29/29 |
| created_at | timestamp with time zone | 29/29 |
| updated_at | timestamp with time zone | 29/29 |
| data_source_id | bigint | 29/29 |
| reference_id | bigint | 29/29 |
| equipment_id | bigint | 29/29 |
| asset_category | character varying | 29/29 |
| load_profile | character varying | 29/29 |
| parent_series | character varying | 29/29 |
| rated_capacity_kva | double precision | 29/29 |
| energy_direction | character varying | 29/29 |
| energy_scale | double precision | 29/29 |
| power_scale | double precision | 29/29 |

FK constraints:
- `register_data_source_id_f19451ed_fk_data_source_id`: FOREIGN KEY (data_source_id) REFERENCES equipment.data_source(id) DEFERRABLE INITIALLY DEFERRED
- `register_equipment_id_0e0511b8_fk_equipment_id`: FOREIGN KEY (equipment_id) REFERENCES equipment.equipment(id) DEFERRABLE INITIALLY DEFERRED
- `register_reference_id_9d2ce68e_fk_equipment_id`: FOREIGN KEY (reference_id) REFERENCES equipment.equipment(id) DEFERRABLE INITIALLY DEFERRED

Sample rows (ascii-replaced, truncated):
```
{"id": "1", "name": "Diesel Generator-01", "role": "incoming", "table_name": "register_dg_01", "series_id": "REG-DG-01", "sheet_row": "1", "section": "HT", "zone": "HT", "created_at": "2026-06-12 08:19:47.665861+05:30", "updated_at": "2026-06-15 16:39:33.767491+05:30", "data_source_id": "1", "reference_id": "98", "equipment_id": "35", "asset_category": "DG", "load_profile": "process_furnace", "parent_series": "", "rated_capacity_kva": "1010.0", "energy_direction": "sum", "energy_scale": "1.0", "power_scale": "1.0"}
{"id": "2", "name": "Diesel Generator-02", "role": "incoming", "table_name": "register_dg_02", "series_id": "REG-DG-02", "sheet_row": "2", "section": "HT", "zone": "HT", "created_at": "2026-06-12 08:19:47.667868+05:30", "updated_at": "2026-06-15 16:39:33.768520+05:30", "data_source_id": "1", "reference_id": "98", "equipment_id": "151", "asset_category": "DG", "load_profile": "process_furnace", "parent_series": "", "rated_capacity_kva": "1010.0", "energy_direction": "sum", "energy_scale": "1.0", "power_scale": "1.0"}
{"id": "3", "name": "Diesel Generator-03", "role": "incoming", "table_name": "register_dg_03", "series_id": "REG-DG-03", "sheet_row": "3", "section": "HT", "zone": "HT", "created_at": "2026-06-12 08:19:47.668840+05:30", "updated_at": "2026-06-15 16:39:33.769177+05:30", "data_source_id": "1", "reference_id": "98", "equipment_id": "59", "asset_category": "DG", "load_profile": "process_furnace", "parent_series": "", "rated_capacity_kva": "1010.0", "energy_direction": "sum", "energy_scale": "1.0", "power_scale": "1.0"}
```

## equipment.asset_threshold  (6 rows)

| column | type | non-null |
|---|---|---|
| id | bigint | 6/6 |
| metric | character varying | 6/6 |
| warn | double precision | 6/6 |
| trip | double precision | 4/6 |
| band_low | double precision | 3/6 |
| band_high | double precision | 3/6 |
| asset_type_id | bigint | 6/6 |
| equipment_id | bigint | 0/6 |

FK constraints:
- `asset_threshold_asset_type_id_c0e96322_fk_core_assettype_id`: FOREIGN KEY (asset_type_id) REFERENCES equipment.core_assettype(id) DEFERRABLE INITIALLY DEFERRED
- `asset_threshold_equipment_id_564ee1ea_fk_equipment_id`: FOREIGN KEY (equipment_id) REFERENCES equipment.equipment(id) DEFERRABLE INITIALLY DEFERRED

Sample rows (ascii-replaced, truncated):
```
{"id": "2", "metric": "oilTemp", "warn": "110.0", "trip": "120.0", "band_low": "NULL", "band_high": "NULL", "asset_type_id": "2", "equipment_id": "NULL"}
{"id": "3", "metric": "intake", "warn": "70.0", "trip": "NULL", "band_low": "NULL", "band_high": "NULL", "asset_type_id": "2", "equipment_id": "NULL"}
{"id": "4", "metric": "exhaust", "warn": "550.0", "trip": "620.0", "band_low": "NULL", "band_high": "NULL", "asset_type_id": "2", "equipment_id": "NULL"}
```

## equipment.bms_meter  (38 rows)

| column | type | non-null |
|---|---|---|
| id | character varying | 38/38 |
| name | character varying | 38/38 |
| meter_group | character varying | 38/38 |
| asset_category | character varying | 38/38 |
| load_profile | character varying | 38/38 |
| load_group | character varying | 38/38 |
| parent_id | character varying | 0/38 |
| rated_capacity_kva | double precision | 38/38 |
| contracted_demand_kva | double precision | 38/38 |
| nominal_voltage_ll | double precision | 38/38 |
| nominal_freq_hz | double precision | 38/38 |
| tariff_rate | double precision | 38/38 |
| table_name | character varying | 38/38 |
| events_table | character varying | 14/38 |
| role | character varying | 38/38 |
| section | character varying | 0/38 |
| zone | character varying | 0/38 |
| meter_type | character varying | 38/38 |
| source_row | integer | 0/38 |
| data_source_id | bigint | 38/38 |
| equipment_id | bigint | 38/38 |

FK constraints:
- `bms_meter_data_source_id_fac8ec26_fk_data_source_id`: FOREIGN KEY (data_source_id) REFERENCES equipment.data_source(id) DEFERRABLE INITIALLY DEFERRED
- `bms_meter_equipment_id_7b733ac6_fk_equipment_id`: FOREIGN KEY (equipment_id) REFERENCES equipment.equipment(id) DEFERRABLE INITIALLY DEFERRED

Sample rows (ascii-replaced, truncated):
```
{"id": "MTR-CHL-01", "name": "Chiller-01", "meter_group": "HVAC", "asset_category": "Chiller", "load_profile": "chiller_plant", "load_group": "hvac_chiller", "parent_id": "NULL", "rated_capacity_kva": "1200.0", "contracted_demand_kva": "1020.0", "nominal_voltage_ll": "415.0", "nominal_freq_hz": "50.0", "tariff_rate": "7.8", "table_name": "meter_chiller_01", "events_table": "NULL", "role": "Load", "section": "NULL", "zone": "NULL", "meter_type": "meter", "source_row": "NULL", "data_source_id": "1", "equipment_id": "91"}
{"id": "MTR-CHL-02", "name": "Chiller-02", "meter_group": "HVAC", "asset_category": "Chiller", "load_profile": "chiller_plant", "load_group": "hvac_chiller", "parent_id": "NULL", "rated_capacity_kva": "1200.0", "contracted_demand_kva": "1020.0", "nominal_voltage_ll": "415.0", "nominal_freq_hz": "50.0", "tariff_rate": "7.8", "table_name": "meter_chiller_02", "events_table": "NULL", "role": "Load", "section": "NULL", "zone": "NULL", "meter_type": "meter", "source_row": "NULL", "data_source_id": "1", "equipment_id": "14"}
{"id": "MTR-CHL-03", "name": "Chiller-03", "meter_group": "HVAC", "asset_category": "Chiller", "load_profile": "chiller_plant", "load_group": "hvac_chiller", "parent_id": "NULL", "rated_capacity_kva": "1200.0", "contracted_demand_kva": "1020.0", "nominal_voltage_ll": "415.0", "nominal_freq_hz": "50.0", "tariff_rate": "7.8", "table_name": "meter_chiller_03", "events_table": "NULL", "role": "Load", "section": "NULL", "zone": "NULL", "meter_type": "meter", "source_row": "NULL", "data_source_id": "1", "equipment_id": "104"}
```

## equipment.bms_meter_limit  (15 rows)

| column | type | non-null |
|---|---|---|
| id | bigint | 15/15 |
| asset_category | character varying | 15/15 |
| metric | character varying | 15/15 |
| warn | double precision | 14/15 |
| trip | double precision | 11/15 |
| meter_id | character varying | 0/15 |

FK constraints:
- `bms_meter_limit_meter_id_99cc2cff_fk_bms_meter_id`: FOREIGN KEY (meter_id) REFERENCES equipment.bms_meter(id) DEFERRABLE INITIALLY DEFERRED

Sample rows (ascii-replaced, truncated):
```
{"id": "1", "asset_category": "Air Compressor", "metric": "winding", "warn": "130.0", "trip": "155.0", "meter_id": "NULL"}
{"id": "2", "asset_category": "Air Compressor", "metric": "bearing", "warn": "85.0", "trip": "95.0", "meter_id": "NULL"}
{"id": "3", "asset_category": "Air Compressor", "metric": "motor", "warn": "120.0", "trip": "140.0", "meter_id": "NULL"}
```

## equipment.breaker  (301 rows)

| column | type | non-null |
|---|---|---|
| id | bigint | 301/301 |
| breaker_type | character varying | 301/301 |
| rating_a | integer | 168/301 |
| source | character varying | 301/301 |
| glb_node | character varying | 301/301 |
| panel_key | character varying | 301/301 |
| updated_at | timestamp with time zone | 301/301 |
| mfm_id | bigint | 301/301 |

FK constraints:
- `breaker_mfm_id_094b8d45_fk_mfm_id`: FOREIGN KEY (mfm_id) REFERENCES equipment.mfm(id) DEFERRABLE INITIALLY DEFERRED

Sample rows (ascii-replaced, truncated):
```
{"id": "2", "breaker_type": "ACB", "rating_a": "2000", "source": "glb-match", "glb_node": "Solar incomer_Panel_spare2000A_ACB_Unit", "panel_key": "panel-1a", "updated_at": "2026-07-08 17:28:02.226764+05:30", "mfm_id": "27"}
{"id": "3", "breaker_type": "ACB", "rating_a": "1000", "source": "glb-match", "glb_node": "UPS-1_1000A_ACB_Unit", "panel_key": "panel-1a", "updated_at": "2026-07-08 17:28:02.228587+05:30", "mfm_id": "28"}
{"id": "4", "breaker_type": "ACB", "rating_a": "1000", "source": "glb-match", "glb_node": "UPS-2_1000A_ACB_Unit", "panel_key": "panel-1a", "updated_at": "2026-07-08 17:28:02.230331+05:30", "mfm_id": "29"}
```

## equipment.core_assettype  (15 rows)

| column | type | non-null |
|---|---|---|
| id | bigint | 15/15 |
| code | character varying | 15/15 |
| name | character varying | 15/15 |
| description | text | 15/15 |
| created_at | timestamp with time zone | 15/15 |
| updated_at | timestamp with time zone | 15/15 |

FK constraints: none

Sample rows (ascii-replaced, truncated):
```
{"id": "1", "code": "grid", "name": "Utility Grid", "description": "Utility grid supply (TSSPDCL 33 kV).", "created_at": "2026-06-05 20:45:30.831769+05:30", "updated_at": "2026-06-05 20:45:30.831773+05:30"}
{"id": "2", "code": "dg", "name": "Diesel Generator", "description": "Diesel generator set.", "created_at": "2026-06-05 20:45:30.833402+05:30", "updated_at": "2026-06-05 20:45:30.833405+05:30"}
{"id": "3", "code": "ups", "name": "UPS", "description": "Uninterruptible power supply unit.", "created_at": "2026-06-05 20:45:30.834911+05:30", "updated_at": "2026-06-05 20:45:30.834914+05:30"}
```

## equipment.core_paneltype  (3 rows)

| column | type | non-null |
|---|---|---|
| id | bigint | 3/3 |
| code | character varying | 3/3 |
| name | character varying | 3/3 |
| description | text | 3/3 |
| created_at | timestamp with time zone | 3/3 |
| updated_at | timestamp with time zone | 3/3 |

FK constraints: none

Sample rows (ascii-replaced, truncated):
```
{"id": "1", "code": "distribution_panel", "name": "Distribution Panel", "description": "Panel with a bus/hub feeding multiple feeders (PCC, HT, switchyard, APFC, HHF, BPDB/PDB, U...", "created_at": "2026-06-05 20:45:30.825240+05:30", "updated_at": "2026-06-05 20:45:30.825254+05:30"}
{"id": "2", "code": "transformer", "name": "Transformer", "description": "Power / distribution transformer (33/11 kV and 11 kV/415 V).", "created_at": "2026-06-05 20:45:30.827153+05:30", "updated_at": "2026-06-05 20:45:30.827157+05:30"}
{"id": "3", "code": "lt_panel", "name": "LT Panel", "description": "Low-tension load / auxiliary / safety panel (AHU, chiller, AW, CSU, HSD, fire, DG C&R, etc...", "created_at": "2026-06-05 20:45:30.829916+05:30", "updated_at": "2026-06-05 20:45:30.829924+05:30"}
```

## equipment.data_source  (2 rows)

| column | type | non-null |
|---|---|---|
| id | bigint | 2/2 |
| name | character varying | 2/2 |
| dsn | character varying | 2/2 |
| description | text | 2/2 |
| created_at | timestamp with time zone | 2/2 |
| updated_at | timestamp with time zone | 2/2 |

FK constraints: none

Sample rows (ascii-replaced, truncated):
```
{"id": "1", "name": "premier_energies", "dsn": "postgresql://postgres@/premier_energies?host=/run/postgresql", "description": "", "created_at": "2026-06-05 20:45:32.796765+05:30", "updated_at": "2026-06-09 17:32:55.922948+05:30"}
{"id": "2", "name": "loggerfast_target_v1", "dsn": "postgresql://postgres@127.0.0.1:5433/target_version1?options=-csearch_path%3Dneuract", "description": "LoggerFast target_version1.neuract via db-tunnel 127.0.0.1:5433 (real meters)", "created_at": "2026-06-25 17:13:43.836758+05:30", "updated_at": "2026-06-25 17:13:43.836772+05:30"}
```

## equipment.equipment  (182 rows)

| column | type | non-null |
|---|---|---|
| id | bigint | 182/182 |
| name | character varying | 182/182 |
| key | character varying | 182/182 |
| distribution_panel | boolean | 182/182 |
| metered | boolean | 182/182 |
| group | character varying | 182/182 |
| created_at | timestamp with time zone | 182/182 |
| updated_at | timestamp with time zone | 182/182 |
| asset_type_id | bigint | 34/182 |
| panel_type_id | bigint | 148/182 |

FK constraints:
- `equipment_asset_type_id_bfba3d31_fk_core_assettype_id`: FOREIGN KEY (asset_type_id) REFERENCES equipment.core_assettype(id) DEFERRABLE INITIALLY DEFERRED
- `equipment_panel_type_id_addb8bdd_fk_core_paneltype_id`: FOREIGN KEY (panel_type_id) REFERENCES equipment.core_paneltype(id) DEFERRABLE INITIALLY DEFERRED

Sample rows (ascii-replaced, truncated):
```
{"id": "171", "name": "UPS supply Lam-8.1", "key": "lam-8-1", "distribution_panel": "False", "metered": "False", "group": "", "created_at": "2026-06-05 20:45:31.521106+05:30", "updated_at": "2026-06-09 17:32:55.841100+05:30", "asset_type_id": "NULL", "panel_type_id": "3"}
{"id": "24", "name": "11KV HT Panel-01", "key": "ht-01", "distribution_panel": "True", "metered": "True", "group": "", "created_at": "2026-06-05 20:45:31.447111+05:30", "updated_at": "2026-06-09 17:32:55.842216+05:30", "asset_type_id": "NULL", "panel_type_id": "1"}
{"id": "64", "name": "PDB-4", "key": "pdb-04", "distribution_panel": "True", "metered": "True", "group": "", "created_at": "2026-06-05 20:45:31.464927+05:30", "updated_at": "2026-06-09 17:32:55.842837+05:30", "asset_type_id": "NULL", "panel_type_id": "1"}
```

## equipment.equipment_config  (120 rows)

| column | type | non-null |
|---|---|---|
| id | bigint | 120/120 |
| rated_kva | double precision | 113/120 |
| rated_kw | double precision | 1/120 |
| contracted_kw | double precision | 0/120 |
| critical_load_kw | double precision | 0/120 |
| nominal_voltage_v | double precision | 8/120 |
| voltage_statutory_deviation_pct | double precision | 7/120 |
| rated_current_a | double precision | 0/120 |
| current_tolerance_pct | double precision | 0/120 |
| current_high_threshold_a | double precision | 0/120 |
| energy_target_kwh_today | double precision | 0/120 |
| subsidy_limit_kw | double precision | 0/120 |
| target_efficiency_pct | double precision | 0/120 |
| thd_v_limit_pct | double precision | 0/120 |
| thd_i_limit_pct | double precision | 0/120 |
| notes | text | 120/120 |
| updated_at | timestamp with time zone | 120/120 |
| equipment_id | bigint | 120/120 |
| subsidy_limit_mvah | double precision | 0/120 |
| moderate_zone | double precision | 0/120 |
| ready_threshold | double precision | 0/120 |
| watch_zone | double precision | 0/120 |
| readiness_floor | double precision | 0/120 |
| current_unbalance_watch_pct | double precision | 0/120 |
| demand_limit_kw | double precision | 0/120 |
| service_interval_hours | double precision | 0/120 |
| service_warn_pct | double precision | 0/120 |
| rating | character varying | 1/120 |

FK constraints:
- `equipment_config_equipment_id_448c914c_fk_equipment_id`: FOREIGN KEY (equipment_id) REFERENCES equipment.equipment(id) DEFERRABLE INITIALLY DEFERRED

Sample rows (ascii-replaced, truncated):
```
{"id": "116", "rated_kva": "NULL", "rated_kw": "NULL", "contracted_kw": "NULL", "critical_load_kw": "NULL", "nominal_voltage_v": "NULL", "voltage_statutory_deviation_pct": "NULL", "rated_current_a": "NULL", "current_tolerance_pct": "NULL", "current_high_threshold_a": "NULL", "energy_target_kwh_today": "NULL", "subsidy_limit_kw": "NULL", "target_efficiency_pct": "NULL", "thd_v_limit_pct": "NULL", "thd_i_limit_pct": "NULL", "notes": "", "updated_at": "2026-06-15 16:02:27.901935+05:30", "equipment_id": "128", "subsidy_limit_mvah": "NULL", "moderate_zone": "NULL", "ready_threshold": "NULL", "watch_zone": "NULL", "readiness_floor": "NULL", "current_unbalance_watch_pct": "NULL", "demand_limit_kw": "NULL", "service_interval_hours": "NULL", "service_warn_pct": "NULL", "rating": "660A"}
{"id": "108", "rated_kva": "1010.0", "rated_kw": "NULL", "contracted_kw": "NULL", "critical_load_kw": "NULL", "nominal_voltage_v": "NULL", "voltage_statutory_deviation_pct": "NULL", "rated_current_a": "NULL", "current_tolerance_pct": "NULL", "current_high_threshold_a": "NULL", "energy_target_kwh_today": "NULL", "subsidy_limit_kw": "NULL", "target_efficiency_pct": "NULL", "thd_v_limit_pct": "NULL", "thd_i_limit_pct": "NULL", "notes": "", "updated_at": "2026-06-15 16:39:33.788388+05:30", "equipment_id": "35", "subsidy_limit_mvah": "NULL", "moderate_zone": "NULL", "ready_threshold": "NULL", "watch_zone": "NULL", "readiness_floor": "NULL", "current_unbalance_watch_pct": "NULL", "demand_limit_kw": "NULL", "service_interval_hours": "NULL", "service_warn_pct": "NULL", "rating": "NULL"}
{"id": "109", "rated_kva": "1010.0", "rated_kw": "NULL", "contracted_kw": "NULL", "critical_load_kw": "NULL", "nominal_voltage_v": "NULL", "voltage_statutory_deviation_pct": "NULL", "rated_current_a": "NULL", "current_tolerance_pct": "NULL", "current_high_threshold_a": "NULL", "energy_target_kwh_today": "NULL", "subsidy_limit_kw": "NULL", "target_efficiency_pct": "NULL", "thd_v_limit_pct": "NULL", "thd_i_limit_pct": "NULL", "notes": "", "updated_at": "2026-06-15 16:39:33.790363+05:30", "equipment_id": "151", "subsidy_limit_mvah": "NULL", "moderate_zone": "NULL", "ready_threshold": "NULL", "watch_zone": "NULL", "readiness_floor": "NULL", "current_unbalance_watch_pct": "NULL", "demand_limit_kw": "NULL", "service_interval_hours": "NULL", "service_warn_pct": "NULL", "rating": "NULL"}
```

## equipment.feeder  (194 rows)

| column | type | non-null |
|---|---|---|
| id | bigint | 194/194 |
| kind | character varying | 194/194 |
| label | character varying | 194/194 |
| metered | boolean | 194/194 |
| created_at | timestamp with time zone | 194/194 |
| updated_at | timestamp with time zone | 194/194 |
| source_id | bigint | 194/194 |
| target_id | bigint | 194/194 |

FK constraints:
- `feeder_source_id_0983cb75_fk_equipment_id`: FOREIGN KEY (source_id) REFERENCES equipment.equipment(id) DEFERRABLE INITIALLY DEFERRED
- `feeder_target_id_0f6be5d5_fk_equipment_id`: FOREIGN KEY (target_id) REFERENCES equipment.equipment(id) DEFERRABLE INITIALLY DEFERRED

Sample rows (ascii-replaced, truncated):
```
{"id": "379", "kind": "feed", "label": "Feeder ? HT Panel-M1", "metered": "True", "created_at": "2026-06-09 17:33:32.288914+05:30", "updated_at": "2026-06-09 17:33:32.288926+05:30", "source_id": "24", "target_id": "13"}
{"id": "380", "kind": "feed", "label": "Feeder ? HT Panel-M2", "metered": "True", "created_at": "2026-06-09 17:33:32.288941+05:30", "updated_at": "2026-06-09 17:33:32.288944+05:30", "source_id": "24", "target_id": "142"}
{"id": "381", "kind": "feed", "label": "Feeder ? 11kV APFCR Panel-1 (5000 KVAR)", "metered": "True", "created_at": "2026-06-09 17:33:32.288953+05:30", "updated_at": "2026-06-09 17:33:32.288955+05:30", "source_id": "24", "target_id": "5"}
```

## equipment.kitpreview_app_kv  (2 rows)

| column | type | non-null |
|---|---|---|
| key | character varying | 2/2 |
| value | jsonb | 2/2 |
| updated_at | timestamp with time zone | 2/2 |

FK constraints: none

Sample rows (ascii-replaced, truncated):
```
{"key": "default_panel_model", "value": "1000xacb-panel", "updated_at": "2026-06-16 05:48:57.132984+05:30"}
{"key": "viewer_defaults", "value": "{'toneMap': {'mode': 'NEUTRAL', 'exposure': 0.95}, 'lighting': {'dpr': 2.25, 'keyX': 9, 'k...", "updated_at": "2026-06-29 13:46:50.206216+05:30"}
```

## equipment.kitpreview_asset_rules  (1 rows)

| column | type | non-null |
|---|---|---|
| asset | character varying | 1/1 |
| rules | jsonb | 1/1 |
| updated_at | timestamp with time zone | 1/1 |

FK constraints: none

Sample rows (ascii-replaced, truncated):
```
{"asset": "cooling-tower", "rules": "[]", "updated_at": "2026-06-15 20:32:31.837879+05:30"}
```

## equipment.kitpreview_cat_asset  (55 rows)

| column | type | non-null |
|---|---|---|
| id | bigint | 55/55 |
| slug | character varying | 55/55 |
| label | character varying | 55/55 |
| url | text | 55/55 |
| sort | integer | 55/55 |
| created_at | timestamp with time zone | 55/55 |
| default_overrides | jsonb | 55/55 |
| template | jsonb | 25/55 |
| group_id | bigint | 55/55 |
| glb_file | character varying | 55/55 |

FK constraints:
- `kitpreview_cat_asset_group_id_f24f71eb_fk_kitprevie`: FOREIGN KEY (group_id) REFERENCES equipment.kitpreview_cat_group(id) DEFERRABLE INITIALLY DEFERRED

Sample rows (ascii-replaced, truncated):
```
{"id": "35", "slug": "air-exhaust-blower", "label": "air exhaust blower", "url": "http://100.90.185.31:8470/uploads/air-exhaust-blower.glb?v=1781379312", "sort": "10", "created_at": "2026-06-15 20:32:31.829941+05:30", "default_overrides": "{'bloom': {'enabled': False}, 'edges': {'color': '#000000', 'width': 1, 'opacity': 0.47, '...", "template": "{'props': {'title': 'AW Exhaust', 'topKpis': [{'id': 'blower-1', 'glow': 'Blower_1', 'tone...", "group_id": "3", "glb_file": "objects/air_exhaust_blower_final_v3.glb"}
{"id": "20", "slug": "source-overview", "label": "source overview", "url": "http://127.0.0.1:8889/media/objects/so-ct23.glb", "sort": "3", "created_at": "2026-06-15 20:32:31.822187+05:30", "default_overrides": "{'bloom': {'enabled': False}, 'edges': {'color': '#000000', 'width': 1, 'opacity': 0.47, '...", "template": "NULL", "group_id": "10", "glb_file": "objects/Source_overview_final_v3_gsfU0nD.glb"}
{"id": "12", "slug": "ht-transformer", "label": "HT transformer", "url": "http://100.90.185.31:8470/uploads/ht-transformer.glb?v=1781359398", "sort": "0", "created_at": "2026-06-15 20:32:31.817862+05:30", "default_overrides": "{'bloom': {'enabled': False}, 'edges': {'color': '#000000', 'width': 1, 'opacity': 0.47, '...", "template": "NULL", "group_id": "6", "glb_file": "objects/HT_Transformer_final_v1.glb"}
```

## equipment.kitpreview_cat_group  (6 rows)

| column | type | non-null |
|---|---|---|
| id | bigint | 6/6 |
| name | character varying | 6/6 |
| sort | integer | 6/6 |
| created_at | timestamp with time zone | 6/6 |

FK constraints: none

Sample rows (ascii-replaced, truncated):
```
{"id": "3", "name": "BMS", "sort": "0", "created_at": "2026-06-15 20:32:31.814012+05:30"}
{"id": "4", "name": "Bms_overview", "sort": "2", "created_at": "2026-06-15 20:32:31.814396+05:30"}
{"id": "5", "name": "EMS", "sort": "3", "created_at": "2026-06-15 20:32:31.814548+05:30"}
```

## equipment.kitpreview_combo  (4 rows)

| column | type | non-null |
|---|---|---|
| id | bigint | 4/4 |
| asset | character varying | 4/4 |
| name | character varying | 4/4 |
| payload | jsonb | 4/4 |
| designer | character varying | 4/4 |
| created_at | timestamp with time zone | 4/4 |

FK constraints: none

Sample rows (ascii-replaced, truncated):
```
{"id": "1", "asset": "ahu", "name": "ahu1", "payload": "{'wide': True, 'hooks': {}, 'props': {'title': 'AHU', 'height': '100%', 'labels': {}, 'top...", "designer": "saharsh", "created_at": "2026-06-15 20:32:31.836285+05:30"}
{"id": "2", "asset": "ahu", "name": "ahu2", "payload": "{'wide': True, 'hooks': {}, 'props': {'title': 'AHU', 'height': '100%', 'labels': {}, 'top...", "designer": "saharsh", "created_at": "2026-06-15 20:32:31.836649+05:30"}
{"id": "3", "asset": "pcc-2", "name": "pcc panel v1", "payload": "{'wide': False, 'hooks': {}, 'props': {'title': 'PCC - 2', 'height': '100%', 'labels': {},...", "designer": "aish", "created_at": "2026-06-15 20:32:31.836919+05:30"}
```

## equipment.kitpreview_preset  (7 rows)

| column | type | non-null |
|---|---|---|
| id | bigint | 7/7 |
| name | character varying | 7/7 |
| asset_url | text | 7/7 |
| created_at | timestamp with time zone | 7/7 |

FK constraints: none

Sample rows (ascii-replaced, truncated):
```
{"id": "2", "name": "cooling-demo", "asset_url": "/assets/3d/cooling-tower.glb", "created_at": "2026-06-15 20:32:31.831274+05:30"}
{"id": "3", "name": "tes", "asset_url": "/assets/3d/air-washer.glb", "created_at": "2026-06-15 20:32:31.831533+05:30"}
{"id": "4", "name": "test", "asset_url": "/assets/3d/air-washer.glb", "created_at": "2026-06-15 20:32:31.831686+05:30"}
```

## equipment.kitpreview_version  (10 rows)

| column | type | non-null |
|---|---|---|
| id | bigint | 10/10 |
| version_no | integer | 10/10 |
| payload | jsonb | 10/10 |
| designer | character varying | 10/10 |
| message | text | 4/10 |
| created_at | timestamp with time zone | 10/10 |
| preset_id | bigint | 10/10 |

FK constraints:
- `kitpreview_version_preset_id_7dbea7ca_fk_kitpreview_preset_id`: FOREIGN KEY (preset_id) REFERENCES equipment.kitpreview_preset(id) DEFERRABLE INITIALLY DEFERRED

Sample rows (ascii-replaced, truncated):
```
{"id": "3", "version_no": "1", "payload": "{'wide': True, 'overrides': {'ypipe': {'color': '#ff8800'}}}", "designer": "rohith", "message": "first cut", "created_at": "2026-06-15 20:32:31.832449+05:30", "preset_id": "2"}
{"id": "4", "version_no": "2", "payload": "{'wide': False, 'overrides': {'bloom': {'intensity': 1.6}}}", "designer": "abhishek", "message": "bumped bloom", "created_at": "2026-06-15 20:32:31.832718+05:30", "preset_id": "2"}
{"id": "5", "version_no": "1", "payload": "{'wide': True, 'props': {'title': 'Air Washer', 'height': '100%', 'labels': {}, 'topKpis':...", "designer": "asdaa", "message": "sdsd", "created_at": "2026-06-15 20:32:31.832920+05:30", "preset_id": "3"}
```

## equipment.kitpreview_viewer_rule  (49 rows)

| column | type | non-null |
|---|---|---|
| id | bigint | 49/49 |
| for_type | character varying | 49/49 |
| for_key | character varying | 49/49 |
| rating | character varying | 49/49 |
| page_type | character varying | 49/49 |
| preset | jsonb | 34/49 |
| updated_at | timestamp with time zone | 49/49 |
| model_id | bigint | 49/49 |

FK constraints:
- `kitpreview_viewer_ru_model_id_d7ae15c7_fk_kitprevie`: FOREIGN KEY (model_id) REFERENCES equipment.kitpreview_cat_asset(id) DEFERRABLE INITIALLY DEFERRED

Sample rows (ascii-replaced, truncated):
```
{"id": "25", "for_type": "dg", "for_key": "", "rating": "", "page_type": "individual", "preset": "{'bloom': {'enabled': False}, 'edges': {'color': '#000000', 'width': 1, 'opacity': 0.47, '...", "updated_at": "2026-06-26 01:44:49.722243+05:30", "model_id": "15"}
{"id": "28", "for_type": "distribution_panel", "for_key": "", "rating": "", "page_type": "individual", "preset": "{'bloom': {'enabled': False}, 'edges': {'color': '#000000', 'width': 1, 'opacity': 0.47, '...", "updated_at": "2026-06-26 01:44:49.722263+05:30", "model_id": "11"}
{"id": "37", "for_type": "lt_panel", "for_key": "", "rating": "", "page_type": "individual", "preset": "{'bloom': {'enabled': False}, 'edges': {'color': '#000000', 'width': 1, 'opacity': 0.47, '...", "updated_at": "2026-06-26 01:44:49.722421+05:30", "model_id": "18"}
```

## equipment.mfm  (303 rows)

| column | type | non-null |
|---|---|---|
| id | bigint | 303/303 |
| name | character varying | 303/303 |
| role | character varying | 303/303 |
| table_name | character varying | 303/303 |
| series_id | character varying | 303/303 |
| sheet_row | integer | 302/303 |
| section | character varying | 303/303 |
| zone | character varying | 303/303 |
| created_at | timestamp with time zone | 303/303 |
| updated_at | timestamp with time zone | 303/303 |
| data_source_id | bigint | 303/303 |
| reference_id | bigint | 303/303 |
| equipment_id | bigint | 242/303 |
| asset_category | character varying | 303/303 |
| load_profile | character varying | 303/303 |
| parent_series | character varying | 303/303 |
| rated_capacity_kva | double precision | 302/303 |
| energy_direction | character varying | 303/303 |
| energy_scale | double precision | 303/303 |
| power_scale | double precision | 303/303 |

FK constraints:
- `mfm_data_source_id_eb7d2073_fk_data_source_id`: FOREIGN KEY (data_source_id) REFERENCES equipment.data_source(id) DEFERRABLE INITIALLY DEFERRED
- `mfm_equipment_id_036c3009_fk_equipment_id`: FOREIGN KEY (equipment_id) REFERENCES equipment.equipment(id) DEFERRABLE INITIALLY DEFERRED
- `mfm_reference_id_41d2abea_fk_equipment_id`: FOREIGN KEY (reference_id) REFERENCES equipment.equipment(id) DEFERRABLE INITIALLY DEFERRED

Sample rows (ascii-replaced, truncated):
```
{"id": "82", "name": "HHF-02 (Type-02)", "role": "outgoing", "table_name": "gic_04_n6_hhf_02_apfcr_02_p1", "series_id": "PEFC-082", "sheet_row": "82", "section": "2B", "zone": "South", "created_at": "2026-06-05 20:45:31.572193+05:30", "updated_at": "2026-06-09 17:32:55.973185+05:30", "data_source_id": "2", "reference_id": "48", "equipment_id": "147", "asset_category": "HHF", "load_profile": "hhf_filter", "parent_series": "PEFC-067", "rated_capacity_kva": "400.0", "energy_direction": "import", "energy_scale": "0.01", "power_scale": "1.0"}
{"id": "88", "name": "UPS-07 (600KVA)", "role": "outgoing", "table_name": "gic_06_n3_ups_07_cl_600_kva_p1", "series_id": "PEFC-088", "sheet_row": "88", "section": "3A", "zone": "North", "created_at": "2026-06-05 20:45:31.576062+05:30", "updated_at": "2026-06-25 17:13:43.840523+05:30", "data_source_id": "2", "reference_id": "62", "equipment_id": "73", "asset_category": "UPS", "load_profile": "ups_backed", "parent_series": "PEFC-086", "rated_capacity_kva": "600.0", "energy_direction": "net", "energy_scale": "0.1", "power_scale": "0.1"}
{"id": "51", "name": "Axial Fan Panel-1", "role": "outgoing", "table_name": "gic_03_n2_axial_fan_panel_1_p1", "series_id": "PEFC-051", "sheet_row": "51", "section": "2A", "zone": "South", "created_at": "2026-06-05 20:45:31.550655+05:30", "updated_at": "2026-06-09 17:32:55.955509+05:30", "data_source_id": "2", "reference_id": "43", "equipment_id": "87", "asset_category": "LT Panel", "load_profile": "cleanroom_hvac", "parent_series": "PEFC-048", "rated_capacity_kva": "500.0", "energy_direction": "sum", "energy_scale": "1.0", "power_scale": "1.0"}
```

## equipment.nameplate  (432 rows)

| column | type | non-null |
|---|---|---|
| id | bigint | 432/432 |
| key | character varying | 432/432 |
| value | text | 432/432 |
| unit | character varying | 432/432 |
| normalized_value | character varying | 432/432 |
| confidence | double precision | 432/432 |
| source | character varying | 432/432 |
| created_at | timestamp with time zone | 432/432 |
| equipment_id | bigint | 432/432 |

FK constraints:
- `nameplate_equipment_id_e009ff81_fk_equipment_id`: FOREIGN KEY (equipment_id) REFERENCES equipment.equipment(id) DEFERRABLE INITIALLY DEFERRED

Sample rows (ascii-replaced, truncated):
```
{"id": "1", "key": "email", "value": "marketing@transconind.com, Ph. 9440384090.", "unit": "", "normalized_value": "9440384090", "confidence": "1.0", "source": "1. HT Transformer Details / 1.1 HT Transformer_Nameplate_Details.png.jpg", "created_at": "2026-07-01 16:33:05.717731+05:30", "equipment_id": "162"}
{"id": "2", "key": "transformer_to_is", "value": "2026-2011", "unit": "", "normalized_value": "2026", "confidence": "1.0", "source": "1. HT Transformer Details / 1.1 HT Transformer_Nameplate_Details.png.jpg", "created_at": "2026-07-01 16:33:05.722166+05:30", "equipment_id": "162"}
{"id": "3", "key": "voltage", "value": "50V", "unit": "V", "normalized_value": "50", "confidence": "1.0", "source": "1. HT Transformer Details / 1.1 HT Transformer_Nameplate_Details.png.jpg", "created_at": "2026-07-01 16:33:05.724052+05:30", "equipment_id": "162"}
```

## equipment.rtm_threshold  (18 rows)

| column | type | non-null |
|---|---|---|
| id | bigint | 18/18 |
| metric | character varying | 18/18 |
| low_max | double precision | 18/18 |
| normal_max | double precision | 18/18 |
| moderate_max | double precision | 18/18 |
| high_max | double precision | 18/18 |
| equipment_id | bigint | 0/18 |
| panel_type_id | bigint | 18/18 |

FK constraints:
- `rtm_threshold_equipment_id_e1131819_fk_equipment_id`: FOREIGN KEY (equipment_id) REFERENCES equipment.equipment(id) DEFERRABLE INITIALLY DEFERRED
- `rtm_threshold_panel_type_id_c7ac64a9_fk_core_paneltype_id`: FOREIGN KEY (panel_type_id) REFERENCES equipment.core_paneltype(id) DEFERRABLE INITIALLY DEFERRED

Sample rows (ascii-replaced, truncated):
```
{"id": "1", "metric": "kw", "low_max": "40.0", "normal_max": "60.0", "moderate_max": "80.0", "high_max": "95.0", "equipment_id": "NULL", "panel_type_id": "1"}
{"id": "2", "metric": "kvar", "low_max": "20.0", "normal_max": "40.0", "moderate_max": "60.0", "high_max": "80.0", "equipment_id": "NULL", "panel_type_id": "1"}
{"id": "4", "metric": "volt", "low_max": "1.0", "normal_max": "2.0", "moderate_max": "3.0", "high_max": "5.0", "equipment_id": "NULL", "panel_type_id": "1"}
```

# Part 2: Empirical proofs

## 1. feeder.source_id/target_id reference

pg_constraint says BOTH FK to equipment.equipment(id) (feeder_source_id_0983cb75_fk_equipment_id, feeder_target_id_0f6be5d5_fk_equipment_id).
Empirical: 194 edges; 194/194 resolve both ends via equipment.equipment; 187/194 would resolve both ends if (mis)joined to equipment.mfm ids (id-space overlap only).

Sample edges joined via equipment.equipment (source -> target):
```
feeder 379: 11KV HT Panel-01 -> Feeder ? HT Panel-M1 (kind=feed, metered=True)
feeder 380: 11KV HT Panel-01 -> Feeder ? HT Panel-M2 (kind=feed, metered=True)
feeder 381: 11KV HT Panel-01 -> Feeder ? 11kV APFCR Panel-1 (5000 KVAR) (kind=feed, metered=True)
feeder 382: DG Sync incomer -> 11 kV HT Bus (kind=feed, metered=True)
feeder 383: Feeder ? HT Panel-M1 -> Feeder ? HT Panel-M2 (kind=coupler, metered=True)
feeder 384: Feeder ? HT Panel-M1 -> 2500 KVA Tx-1 (kind=feed, metered=True)
feeder 385: Feeder ? HT Panel-M1 -> 2500 KVA Tx-2 (kind=feed, metered=True)
feeder 386: Feeder ? HT Panel-M1 -> 2500 KVA Tx-3 (kind=feed, metered=True)
```
Same ids (mis)joined to equipment.mfm (nonsense pairs, proving the FK target):
```
feeder 379: Air Compressor Panel (1600 KW) -> Feeder ? Tx-1 (PCC-1A)
feeder 380: Air Compressor Panel (1600 KW) -> Chiller & CHW CWP-4
feeder 381: Air Compressor Panel (1600 KW) -> Feeder ? HT Panel-M2
feeder 382: Solar Incomer-2 -> Feeder ? Tx-7 (PCC-4A)
feeder 383: Feeder ? Tx-1 (PCC-1A) -> Chiller & CHW CWP-4
```

## 2. Direction semantics (verified on real PCC panels)

PCC-named equipment nodes: 16
```
id=20 key=apfcr-pcc2-hhf01 name=LT APFCR Panel (Type-02,750KVAR) - PCC-2 HHF-01
id=43 key=pcc-2a name=PCC-2A
id=47 key=pcc-1a name=PCC-1A
id=48 key=pcc-2b name=PCC-2B
id=62 key=pcc-3a name=PCC-3A
id=65 key=pcc-4a name=PCC-4A
id=80 key=apfcr-pcc2-hhf02 name=LT APFCR Panel (Type-02,750KVAR) - PCC-2 HHF-02
id=95 key=apfcr-pcc3-hhf02 name=LT APFCR Panel (Type-01,600KVAR) - PCC-3 HHF-02
id=100 key=apfcr-pcc1-hhf01 name=LT APFCR Panel (Type-01,600KVAR) - PCC-1 HHF-01
id=113 key=apfcr-pcc4-hhf01 name=LT APFCR Panel (Type-02,750KVAR) - PCC-4 HHF-01
id=130 key=apfcr-pcc3-hhf01 name=LT APFCR Panel (Type-01,600KVAR) - PCC-3 HHF-01
id=133 key=apfcr-pcc4-hhf02 name=LT APFCR Panel (Type-02,750KVAR) - PCC-4 HHF-02
id=139 key=pcc-4b name=PCC-4B
id=150 key=pcc-3b name=PCC-3B
id=154 key=apfcr-pcc1-hhf02 name=LT APFCR Panel (Type-01,600KVAR) - PCC-1 HHF-02
id=160 key=pcc-1b name=PCC-1B
```

### Panel: LT APFCR Panel (Type-02,750KVAR) - PCC-2 HHF-01 (equipment.id=20)
INCOMERS (target_id=20, i.e. sources feeding the panel) - SQL: SELECT se.name FROM equipment.feeder f JOIN equipment.equipment se ON se.id=f.source_id WHERE f.target_id=20:
```
  <- HHF-01 (Type-02) (feeder 547, kind=feed)
```
OUTGOERS (source_id=20, i.e. loads the panel feeds) - SQL: SELECT te.name FROM equipment.feeder f JOIN equipment.equipment te ON te.id=f.target_id WHERE f.source_id=20:
```
  (none)
```

### Panel: PCC-2A (equipment.id=43)
INCOMERS (target_id=43, i.e. sources feeding the panel) - SQL: SELECT se.name FROM equipment.feeder f JOIN equipment.equipment se ON se.id=f.source_id WHERE f.target_id=43:
```
  <- 2500 KVA Tx-3 (feeder 408, kind=feed)
  <- Solar Plant (feeder 409, kind=feed)
```
OUTGOERS (source_id=43, i.e. loads the panel feeds) - SQL: SELECT te.name FROM equipment.feeder f JOIN equipment.equipment te ON te.id=f.target_id WHERE f.source_id=43:
```
  -> CSU-02 (feeder 410, kind=feed)
  -> Axial Fan Panel-1 (feeder 411, kind=feed)
  -> Utility Panel-1 (feeder 412, kind=feed)
  -> Canteen Building (feeder 413, kind=feed)
  -> STP Panel (feeder 414, kind=feed)
  -> AHU-05 (feeder 415, kind=feed)
  -> MRPDB (feeder 416, kind=feed)
  -> AHU-06 (feeder 417, kind=feed)
  -> AHU-07 (feeder 418, kind=feed)
  -> AHU-08 (feeder 419, kind=feed)
  -> Admin+IT+Other Emergency (feeder 420, kind=feed)
  -> BPDB-03 Lam-05&06 (feeder 421, kind=feed)
  -> HHF-01 (Type-02) (feeder 422, kind=feed)
```

### Panel: PCC-1A (equipment.id=47)
INCOMERS (target_id=47, i.e. sources feeding the panel) - SQL: SELECT se.name FROM equipment.feeder f JOIN equipment.equipment se ON se.id=f.source_id WHERE f.target_id=47:
```
  <- 2500 KVA Tx-1 (feeder 394, kind=feed)
  <- Solar Plant (feeder 395, kind=feed)
```
OUTGOERS (source_id=47, i.e. loads the panel feeds) - SQL: SELECT te.name FROM equipment.feeder f JOIN equipment.equipment te ON te.id=f.target_id WHERE f.source_id=47:
```
  -> UPS-01 (feeder 396, kind=feed)
  -> UPS-02 (feeder 397, kind=feed)
  -> UPS-03 (feeder 398, kind=feed)
  -> BPDB-01 Lam-01&02 (feeder 399, kind=feed)
  -> HHF-01 (Type-01) (feeder 400, kind=feed)
```

### Panel: PCC-2B (equipment.id=48)
INCOMERS (target_id=48, i.e. sources feeding the panel) - SQL: SELECT se.name FROM equipment.feeder f JOIN equipment.equipment se ON se.id=f.source_id WHERE f.target_id=48:
```
  <- 2500 KVA Tx-4 (feeder 423, kind=feed)
  <- Solar Plant (feeder 424, kind=feed)
```
OUTGOERS (source_id=48, i.e. loads the panel feeds) - SQL: SELECT te.name FROM equipment.feeder f JOIN equipment.equipment te ON te.id=f.target_id WHERE f.source_id=48:
```
  -> FCBC-1 (feeder 425, kind=feed)
  -> Air Washer Exhaust-04 (feeder 426, kind=feed)
  -> Air Washer Exhaust-05 (feeder 427, kind=feed)
  -> Air Washer-5 (feeder 428, kind=feed)
  -> Air Washer-6 (feeder 429, kind=feed)
  -> FCBC-2 (feeder 430, kind=feed)
  -> Air Washer Exhaust-06 (feeder 431, kind=feed)
  -> Elec Room North Side (feeder 432, kind=feed)
  -> Frisking+Security (feeder 433, kind=feed)
  -> Axial Fan Panel-2 (feeder 434, kind=feed)
  -> Air Washer-4 (feeder 435, kind=feed)
  -> MLDB (feeder 436, kind=feed)
  -> BPDB-04 Lam-07&08 (feeder 437, kind=feed)
  -> HHF-02 (Type-02) (feeder 438, kind=feed)
```

feeder.kind distribution: feed=192, coupler=2
feeder.metered distribution: False=17, True=177

## 3. table_name bridge census (equipment.mfm <-> public.registry_lt_mfm)

equipment.mfm: 303 rows, table_name non-null 303, distinct 285 -> 18 rows involved in dup groups on the mfm side
public.registry_lt_mfm: 320 rows, table_name non-null 320, distinct 320
Duplicated table_name groups in equipment.mfm: 18
```
  gic_03_n1_curing_line_csu_02_p1 x2
  gic_05_n11_frisking_security_p1 x2
  gic_02_n6_ups_05_cl_600kva_p1 x2
  gic_05_n10_elec_room_north_p1 x2
  gic_03_n4_canteen_building_p1 x2
  gic_01_n3_ups_01_p1 x2
  gic_01_n4_ups_02_p1 x2
  gic_10_n10_pcw_panel_p1 x2
  gic_02_n5_ups_04_cl_600kva_p1 x2
  gic_10_n5_general_exhaust_p1 x2
  gic_02_n7_ups_06_cl_600kva_p1 x2
  gic_06_n5_ups_09_p1 x2
  gic_08_n2_curing_line_csu_01_p1 x2
  gic_01_n5_ups_03_p1 x2
  gic_20_n3_fg_shed_qc_pdi_p1 x2
  gic_08_n9_elec_room_ext_south_p1 x2
  gic_25_n13_utility_02_ng x2
  gic_07_n7_ups_12_cl_600_kva_p1 x2
```
Duplicated table_name groups in public.registry_lt_mfm: 0
Empty/NULL table_name: equipment.mfm=0, registry_lt_mfm=0

BRIDGEABLE nodes (table_name unique on both sides AND present on both): 183
equipment.mfm unique-table rows with NO registry match: 84
registry_lt_mfm unique-table rows with NO equipment.mfm match: 119
Sample mfm-only table_names (no registry match):
```
  gic_30_n1_33kv_main_transformer_1_feeder_pm8000
  gic_30_n2_11kv_power_transformer_grid_inc_pm8000
  gic_30_n3_11kv_ht_dg_incomer_pm8000
  gic_30_n5_apfcr_se
  gic_30_n6_ht_panel_m2_se
  gic_30_n7_ht_panel_m1_se
  gic_30_n8_spare_se
  mfm_pefc_008
  mfm_pefc_033
  mfm_pefc_034
  mfm_pefc_035
  mfm_pefc_036
  mfm_pefc_044
  mfm_pefc_045
  mfm_pefc_046
```

Spot-check bridge: equipment.mfm id=13 name='Feeder ? Tx-1 (PCC-1A)' table=gic_15_n3_pcc_01_transformer_01_se -> registry_lt_mfm id=171 name='GIC-15-N3-PCC-01 (Transformer-01) [Secure Elite300...'

## 4. mfm <-> equipment <-> feeder linkage coverage

equipment.mfm by data_source_id: ds1=69, ds2=234  (ds1=premier_energies MOCK, ds2=loggerfast target_version1 REAL)
equipment.mfm by role: outgoing=136, incoming=105, spare=60, coupler=2
equipment nodes with >=1 mfm meter (mfm.equipment_id): 148 of 182
distinct mfm.reference_id values (panel the meter belongs to?): 84
PCC-1A (equipment.id=47): mfm rows with reference_id=47: 14; with equipment_id=47: 1
mfm rows with reference_id=PCC-1A (i.e. meters mounted ON the panel):
```
  mfm 26 role=incoming: Tx-1 (LV)
  mfm 27 role=incoming: Solar Incomer-1
  mfm 28 role=outgoing: UPS-01 (600KVA)
  mfm 29 role=outgoing: UPS-02 (600KVA)
  mfm 30 role=outgoing: UPS-03 (600KVA)
  mfm 31 role=outgoing: BPDB-01 Lam-01&02
  mfm 32 role=outgoing: HHF-01 (Type-01)
  mfm 33 role=spare: Spare-01
  mfm 34 role=spare: Spare-02
  mfm 35 role=spare: Spare-06
  mfm 36 role=spare: Spare-07
  mfm 315 role=spare: Spare feeder (reserve-1)
```
feeder edges: 194; target node has >=1 mfm meter: 177; source node has >=1 mfm meter: 183

## 5. kitpreview_cat_asset payload detail (ascii-safe summary)

url hosts: total=55; http://100.90.185.31:8470/uploads/*.glb = 33; http://127.0.0.1:8889/media/* = 1; other = 21
  other url: 
  other url: 
  other url: 
  other url: 
  other url: 
glb_file: 40 distinct, 39/55 under 'objects/' (relative media paths, e.g. objects/HT_Transformer_final_v1.glb)
default_overrides: present 55/55, size bytes min/med/max = 1757/6108/7554
  top-level keys (count): toneMap=55, lighting=55, environment=55, bloom=36, edges=36, flowAnim=36, animProps=36, flowMixes=36, materials=36, background=36, pills=35, camera=34, flowAnimByStream=1
template: present 25/55, size bytes min/med/max = 1299/1814/3173
  top-level keys (count): props=25
  slugs WITH template: ahu, ahu-overview, air-compressor, air-compressor-assembly-new, air-dryer, air-dryer-overview, air-exhaust-blower, air-washer, air-washer-overview, chiller, chiller-overview, cooling-tower, csu, csu-overview, general-air-exhaust, general-air-exhaust-overview, pcc-1a, pcc-1b, pcc-2a, pcc-2b, pcc-3a, pcc-3b, pcc-4a, pcc-4b, pcw-assembly
  example template.props keys: title, topKpis, subtitle, defaultDetail
  example topKpis[0] keys: id, glow, tone, unit, label, style, anchor, bottom, source
  assets per group: Ems_overview=15, Bms_overview=11, BMS=10, EMS=8, Source_overview=6, Source=5

## 6. Bridge verdict + dup-pair explanation

- public.registry_lt_mfm (320 rows) has ZERO duplicated table_names; equipment.mfm (303) has 18 duplicated groups (x2 each = 36 rows).
- The 18 dup pairs are the SAME physical meter registered TWICE from two panel viewpoints: one row role=outgoing (on the feeding panel) + one row role=incoming (on the fed panel), both data_source_id=2 (real). Example gic_01_n3_ups_01_p1 = mfm ids 28 (outgoing) + 303 (incoming). Attributes other than role/reference differ per row, so a table_name join to these is AMBIGUOUS -> per the bridge rule these 36 rows are UN-BRIDGEABLE (skip honestly). Note the underlying gic table itself is still uniquely present in the registry.
- BRIDGEABLE: 183 equipment.mfm rows (table_name unique on both sides + present on both).
- UN-BRIDGEABLE mfm rows: 120 = 36 dup-group rows + 84 unique-but-unmatched (69 mfm_pefc_* = ds1 premier_energies MOCK meters, 7 gic_30_* = new 33kV/HT PM8000/SE meters absent from the registry mirror, 8 misc).
- Registry side: 119 registry rows have no equipment.mfm row at all; 18 more match only dup groups. So equipment metadata can enrich at most 183+ambiguous of the 320 canonical meters.
- THE ONLY SAFE BRIDGE IS table_name equi-join with a uniqueness guard on BOTH sides:
  `WITH m AS (SELECT table_name FROM equipment.mfm GROUP BY 1 HAVING count(*)=1) SELECT ... FROM equipment.mfm JOIN public.registry_lt_mfm USING (table_name) WHERE table_name IN (SELECT table_name FROM m)`

## 7. Per-table proposed pipeline use

| table | rows | verdict |
|---|---|---|
| mfm | 303 | USE: metadata enrichment of canonical meters via table_name bridge (183 safe) — role/section/zone/load_profile/asset_category/rated_capacity_kva as FACTS lines to Layer-2; energy_direction/energy_scale/power_scale surfaced as FACTS ONLY (never silent multiplication, hard rule 1). Also the mfm.equipment_id hop into the feeder graph. |
| feeder | 194 | USE: richer topology than the 93-edge lt_mfm_outgoing mirror. Edges are equipment.equipment-id based; map each endpoint to canonical meters via equipment.mfm.equipment_id -> table_name bridge. Direction: source_id feeds target_id (incomers of panel P = WHERE target_id=P; outgoers = WHERE source_id=P; verified on PCC-1A/2A/2B). kind: feed=192, coupler=2; metered flag on 177. |
| breaker | 301 | USE: per-feeder breaker rating (rating_a on 168, ACB=202/MCCB=99) as overload-%% denominator FACT + glb_node ties a breaker to the 3D panel model (panel_key like 'panel-1a'). Join breaker.mfm_id -> equipment.mfm -> table_name bridge. |
| rtm_threshold | 18 | USE: RTM status banding (kw/kvar/volt/amp/pf/i_unbal x 3 panel types; low/normal/moderate/high maxima). equipment_id is all-NULL -> per-panel-TYPE defaults only. Feed to Layer-2 as banding FACTS or a derivation registered in ems_exec/derivations/registry.py. |
| equipment | 182 | USE: the topology node table (name/key/distribution_panel/metered/panel_type/asset_type). Needed as the join hub for feeder/nameplate/equipment_config; also a human-name alias source (keys like 'pcc-1a'). |
| equipment_config | 120 | PARTIAL: only rated_kva (113), nominal_voltage_v (8), voltage_statutory_deviation_pct (7), rated_kw (1), rating (1, '660A') carry data. Everything else (contracted_kw, critical_load_kw, thd limits, demand_limit_kw, ...) is 100%% NULL = no data upstream — do NOT wire those columns. |
| nameplate | 432 | USE (carefully): OCR'd nameplate key/values for 74 equipment nodes (current_rating x51, power_kw x49, voltage x22, ...). Noisy OCR (emails, ISO numbers, '50V' on an HT transformer) -> surface as low-trust FACTS only where key is in a vetted whitelist; do NOT overwrite public.asset_nameplate (already consumed at runtime) — enrich around it. |
| core_assettype | 15 | USE: class vocabulary (grid/dg/ups/...) for equipment.asset_type_id; join-dimension only. |
| core_paneltype | 3 | USE: distribution_panel / transformer / lt_panel vocabulary; the rtm_threshold banding key. |
| asset_meter | 29 | SKIP for EMS numbers: table_name=register_* on data_source 1 (premier_energies mock DSN via /run/postgresql, unreachable as configured). Metadata (rated_capacity_kva, role, section) could serve as FACTS for DG/HT assets, but readings are not the neuract feed. |
| bms_meter | 38 | SKIP for now: BMS meters (meter_chiller_01 etc) on data_source 1 (mock premier DSN); the pipeline's data plane is neuract gic_*. Metadata (rated_capacity_kva, load_group, tariff_rate) is plausible future FACT material if/when a BMS feed exists. |
| bms_meter_limit | 15 | SKIP: per-asset-category warn/trip limits for BMS metrics (winding/bearing/motor temps); meter_id all-NULL; only useful if bms_meter is wired. |
| asset_threshold | 6 | HOLD: per-asset-TYPE warn/trip for DG-ish metrics (oilTemp/intake/exhaust...); equipment_id all-NULL. Usable as class-default banding FACTS if those metrics ever flow; tiny. |
| data_source | 2 | REFERENCE only: DSN registry proving ds1=premier mock, ds2=loggerfast neuract real. Never dial these DSNs from new code (rule: local reads only). |
| kitpreview_cat_asset | 55 | USE for 3D: slug/label/glb_file (39/55 relative objects/*.glb; url column is 33 stale absolute 100.90.185.31:8470 links + 21 EMPTY + 1 localhost:8889 — prefer glb_file) + default_overrides (55/55 viewer JSON: toneMap/lighting/environment/bloom/edges/flowAnim/camera..., 1.7-7.5 KB) + template (25/55, props.title/topKpis[{id,glow,tone,unit,label,anchor,source}] = KPI overlay spec incl. all 8 pcc-XY slugs). Candidate to fill the EMPTY lt_asset_3d/asset_3d_model gap in ems_exec/renderers/asset_3d.py. |
| kitpreview_cat_group | 6 | USE with cat_asset: grouping dimension (EMS/BMS/overviews). |
| kitpreview_viewer_rule | 49 | USE for 3D: maps for_type (dg/distribution_panel/lt_panel/...) + page_type to a cat_asset model_id + preset JSON -> the class->model resolver asset_3d needs. |
| kitpreview_app_kv | 2 | USE for 3D: viewer_defaults JSON + default_panel_model knob. |
| kitpreview_combo | 4 | HOLD: 4 hand-authored full payloads (ahu x2, pcc-2, ...) — design references, not pipeline inputs. |
| kitpreview_preset | 7 | SKIP: demo presets pointing at /assets/3d/*.glb; superseded by cat_asset. |
| kitpreview_version | 10 | SKIP: designer version history of presets. |
| kitpreview_asset_rules | 1 | SKIP: single empty rules row (cooling-tower, rules=[]). |

