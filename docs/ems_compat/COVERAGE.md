# neuract → ems_backend column coverage (truth table)

> From the `neuract-column-contract` workflow (12 extractors + map + adversarial verify, `wf_e3fc1ded-450`), verifier-corrected. Decides what each page can truthfully render off the clean neuract meter vs what blanks / needs another source.

## Headline
neuract's uniform 40-col meter = the **shared electrical CORE** (power · voltage · current · PF · frequency · per-phase THD · cumulative kWh/kVARh). The compat view covers **46 consumer columns** (20 direct · 4 alias · 22 derived). **33 column families have NO neuract source.** Every endpoint is therefore **partial**; the `assets` (transformer/UPS) cards are **coverage: none**.

## Covered (compat view supplies)
- **Direct (20):** active/reactive/apparent power (total), `power_factor_total`, `frequency_hz`, `current_avg`, `current_r/y/b`, `voltage_r_n/y_n/b_n`, per-phase THD (V+I), cumulative energy import.
- **Alias (key one):** `voltage_avg` ← `voltage_ln_avg` (line-to-neutral, **not** `voltage_ll_avg`). `ts` ← `timestamp_utc::timestamptz`.
- **Derived (22):** min/max/spread (V,I), `current_unbalance_pct`, `voltage_unbalance_pct`, per-phase deviation %, `kpi_voltage_deviation_pct`, `thd_compliance_v/i_avg` (null-tolerant 3-phase mean).

## NOT covered (blanks unless sourced elsewhere)
| family | examples | why / where it must come from |
|---|---|---|
| **neutral** | `current_neutral`, `kpi_neutral_to_phase_ratio_pct` | neuract has no neutral current; **not** derivable from R/Y/B magnitudes (needs phase angles). Genuinely missing. |
| **event-flag booleans** | `sag/swell/current_imbalance/neutral_stress_event_active`, 6 PQ flags, `sustained_thd_breach_active`, `apfc_compensation_flag` | no boolean columns in neuract. Hard event timelines blank; consumers degrade to **threshold-derived** counts at the bucket layer. |
| **per-order harmonics** | `harmonic_3/5/7/11/13_pct`, `k_factor`, `harmonic_loss_factor_fhl`, `dominant_harmonic_order`, `phase_angle_deg` | neuract has aggregate THD only — per-order/waveform absent. PQ radar/signature blank. |
| **nameplate/config** | `kpi_kw_load_pct_of_rated`, `rated_kva/rated_kw/voltage_nominal_v`, thermal thresholds | never in a meter schema — JOIN `transformer_config`/`ups_config` or EAV `mfm.get_config()` separately. |
| **period & apparent energy** | `*_today/_this_week/_this_month_kwh/kvarh`, all `*_kvah` | neuract has cumulative kWh/kVARh only and **no kVAh counter**. Period = window-delta at services layer; apparent ≈ √(act²+react²) of deltas. |
| **demand / rate-of-change** | `demand_present/avg/max_*`, `*_rate_change_*_per_min`, `peak_demand_*` | sliding-window/derivative — computed at consumer, not stored. |
| **transformer** | loss breakdown (copper/iron/stray), efficiency, regulation, RUL, all thermal temps/aging | asset-model schema; zero overlap with meter. → `assets` cards blank. |
| **UPS / solar / APFC** | battery SoC/autonomy, DC bus, inverter/transfer; irradiance/strings/yield; cap-bank health/economics | separate device schemas — entirely absent from neuract meters. |
| **status / SLD** | `breaker_state`, `health_status`, `alerts_*`, `*_communication_status` | operational state, not telemetry. |

## Per-endpoint (the 9 routable pages)
| endpoint | coverage | the gaps that matter |
|---|---|---|
| real-time-monitoring | **partial (strong)** | electrical core ✓; missing neutral, `kpi_kw_load_pct_of_rated` (nameplate), rate-of-change, trend labels |
| voltage-current | **partial (strong)** | V/I/unbalance/deviation ✓ (derived); missing neutral, 4 event flags, rate-of-change |
| energy-distribution | **partial (strong)** | import-kWh delta ✓; missing EAV incoming/outgoing live-load config |
| energy-power | **partial** | instantaneous power ✓; period energies (window-delta), load%/load-factor (nameplate), apparent-energy all missing |
| harmonics-pq / power-quality | **partial (weak)** | aggregate THD ✓ + compliance avg (derived); per-order harmonics, k-factor, 6 event flags, neutral all missing |
| overview | **partial** | core electrical ✓; solar/UPS/APFC/thermal/status families + nameplate all missing |
| voltage-history / current-history | **partial (strong)** | per-phase + unbalance/deviation ✓; event flags + rolling counters missing |
| assets (transformer/UPS/DG cards) | **none** | transformer thermal/loss + UPS battery families have zero neuract overlap |

**Takeaway:** neuract powers the **electrical-core pages well** (RTM, V-C, energy-distribution, histories — strong partial), `energy-power` and PQ are **meaningfully partial** (computable rollups + genuinely-absent PQ detail), and **asset-specific cards (transformer thermal/loss, UPS battery, solar, APFC) cannot be served from neuract at all** — they need their own device tables. Template: `compat_view_template.sql`.
