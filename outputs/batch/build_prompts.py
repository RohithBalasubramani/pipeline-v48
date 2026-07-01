"""outputs/batch/build_prompts.py — generate a GROUNDED coverage matrix of NL prompts.
Covers: every asset CLASS + ~50 real named assets, every EMS page/intent, and every one of the ~40
compat metric columns at least once. Each prompt is TAGGED {asset, klass, intent, page_hint, metric_cols}
so coverage is measurable against the run results. Deterministic (no RNG) → reproducible."""
import json
import os

OUT = os.environ.get("BATCH_PROMPTS_OUT", os.path.join(os.path.dirname(__file__), "prompts.json"))
ROT = int(os.environ.get("BATCH_ROTATE", "0"))   # rotate asset order + phrasing -> a fresh, same-coverage list

# ── REAL named assets (from lt_mfm; all carry neuract compat data) ─────────────────────────────
TRANSFORMERS = [f"Transformer {i}" for i in range(1, 9)] + ["HT Transformer 1"]
PCC = ["PCC Panel 1 A", "PCC Panel 1 B", "PCC Panel 2 A", "PCC Panel 2 B",
       "PCC Panel 3 A", "PCC Panel 3 B", "PCC Panel 4"]
DG = [f"Diesel Generator-0{i}" for i in range(1, 9)]
APFC = [f"APFC Panel-{i}" for i in range(1, 5)]
HT = ["Main HT Panel", "HT Panel M1", "HT Panel M2", "DG Sync Panel"]
UPS = ["UPS 01", "UPS 02", "UPS 03", "UPS 04", "UPS 05", "UPS 06"]
LT = ["MLDB", "AHU-1", "AHU-2", "AHU-10", "BusCoupler-12", "Bus Coupler-19",
      "solar incomer 1", "solar incomer 2", "BPDB-01 For Lamination-01&02", "HHF-01 (TYPE-01) 300A +600KVAR"]

KLASS = {}
for a in TRANSFORMERS: KLASS[a] = "Transformer"
for a in PCC: KLASS[a] = "LT Panel (PCC)"
for a in DG: KLASS[a] = "Diesel Generator"
for a in APFC: KLASS[a] = "APFC"
for a in HT: KLASS[a] = "HT Panel"
for a in UPS: KLASS[a] = "UPS"
for a in LT: KLASS[a] = "LT Panel"

# ── INTENT FACETS — (intent, page_hint, [NL templates with {asset}], [metric columns exercised]) ──
# templates are natural-language; metric_cols are the compat columns the intent should touch.
FACETS = [
    ("realtime",      "panel-overview-shell/real-time-monitoring",
     ["real time monitoring for {asset}", "live status of {asset} right now", "{asset} real-time dashboard"],
     ["active_power_total_kw", "current_avg", "voltage_ln_avg", "power_factor_total"]),
    ("energy-power",  "panel-overview-shell/energy-power",
     ["energy and power overview for {asset}", "active power trend for {asset}", "{asset} power consumption"],
     ["active_power_total_kw", "reactive_power_total_kvar", "apparent_power_total_kva", "power_factor_total"]),
    ("energy-kwh",    "panel-overview-shell/energy-power",
     ["energy consumption in kWh for {asset}", "how much energy has {asset} used", "{asset} imported vs exported energy"],
     ["active_energy_import_kwh", "active_energy_export_kwh", "reactive_energy_import_kvarh", "reactive_energy_export_kvarh"]),
    ("demand",        "demand-profile",
     ["demand profile for {asset} over the last week", "{asset} load demand pattern", "peak demand history for {asset}"],
     ["active_power_total_kw", "apparent_power_total_kva"]),
    ("distribution",  "panel-overview-shell/energy-distribution",
     ["energy distribution breakdown for {asset}", "where does the power go in {asset}", "{asset} feeder-level distribution"],
     ["active_power_total_kw", "active_power_r_kw", "active_power_y_kw", "active_power_b_kw"]),
    ("voltage",       "panel-overview-shell/voltage-current",
     ["voltage and current for {asset}", "phase voltages on {asset}", "{asset} line voltage trend"],
     ["voltage_r_n", "voltage_y_n", "voltage_b_n", "voltage_ln_avg"]),
    ("voltage-ll",    "panel-overview-shell/voltage-current",
     ["line-to-line voltage for {asset}", "{asset} L-L voltage RY YB BR", "phase-to-phase voltage on {asset}"],
     ["voltage_ry", "voltage_yb", "voltage_br", "voltage_ll_avg"]),
    ("current",       "panel-overview-shell/voltage-current",
     ["phase currents for {asset}", "current per phase on {asset}", "{asset} current loading R Y B"],
     ["current_r", "current_y", "current_b", "current_avg"]),
    ("voltage-hist",  "voltage-history",
     ["voltage history for {asset} last 7 days", "{asset} voltage trend over the month", "how has voltage on {asset} changed"],
     ["voltage_ln_avg", "voltage_r_n", "voltage_y_n", "voltage_b_n"]),
    ("current-hist",  "current-history",
     ["current history for {asset} this month", "{asset} current trend over time", "current loading history of {asset}"],
     ["current_avg", "current_r", "current_y", "current_b"]),
    ("harmonics",     "panel-overview-shell/harmonics-pq",
     ["harmonic distortion THD for {asset}", "{asset} power quality and harmonics", "voltage THD on {asset}"],
     ["thd_voltage_r_pct", "thd_voltage_y_pct", "thd_voltage_b_pct"]),
    ("current-thd",   "panel-overview-shell/harmonics-pq",
     ["current THD for {asset}", "{asset} current harmonic distortion", "TDD and current harmonics on {asset}"],
     ["thd_current_r_pct", "thd_current_y_pct", "thd_current_b_pct"]),
    ("pq-summary",    "power-quality",
     ["power quality summary for {asset}", "{asset} PQ compliance overview", "power quality assessment of {asset}"],
     ["thd_voltage_r_pct", "thd_current_r_pct", "power_factor_total", "frequency_hz"]),
    ("powerfactor",   "panel-overview-shell/energy-power",
     ["power factor for {asset}", "{asset} pf per phase", "is {asset} running at good power factor"],
     ["power_factor_total", "power_factor_r", "power_factor_y", "power_factor_b"]),
    ("frequency",     "panel-overview-shell/real-time-monitoring",
     ["frequency reading for {asset}", "{asset} grid frequency", "frequency stability on {asset}"],
     ["frequency_hz"]),
    ("reactive",      "panel-overview-shell/energy-power",
     ["reactive power for {asset}", "{asset} kVAR demand", "reactive power per phase on {asset}"],
     ["reactive_power_total_kvar", "reactive_power_r_kvar", "reactive_power_y_kvar", "reactive_power_b_kvar"]),
    ("apparent",      "panel-overview-shell/energy-power",
     ["apparent power for {asset}", "{asset} kVA loading", "apparent power per phase on {asset}"],
     ["apparent_power_total_kva", "apparent_power_r_kva", "apparent_power_y_kva", "apparent_power_b_kva"]),
    ("perphase-pwr",  "panel-overview-shell/energy-power",
     ["per-phase active power for {asset}", "{asset} R Y B phase power split", "phase-wise kW on {asset}"],
     ["active_power_r_kw", "active_power_y_kw", "active_power_b_kw"]),
    ("unbalance",     "panel-overview-shell/voltage-current",
     ["voltage and current unbalance for {asset}", "{asset} phase unbalance", "is {asset} balanced across phases"],
     ["voltage_unbalance_pct", "current_unbalance_pct"]),
    ("anomaly",       "load-anomalies",
     ["load anomalies for {asset}", "{asset} abnormal load events", "any anomalies on {asset} recently"],
     ["active_power_total_kw", "current_avg"]),
    ("overview-sld",  "panel-overview-shell/overview-sld-3d",
     ["single line diagram for {asset}", "{asset} SLD overview", "topology and overview of {asset}"],
     ["active_power_total_kw"]),
    ("compare",       "panel-overview-shell/energy-power",
     ["compare power across {asset} phases", "{asset} phase comparison R vs Y vs B", "how do the three phases of {asset} compare"],
     ["active_power_r_kw", "active_power_y_kw", "active_power_b_kw", "current_r", "current_y", "current_b"]),
]

# class-appropriate intents (some intents only make sense for some classes — but EMS pages are panel-centric,
# so most facets apply to any metered asset; we still bias asset choice so every class appears across facets).
ALL_ASSETS = TRANSFORMERS + PCC + DG + APFC + HT + UPS + LT


def build():
    prompts = []
    pid = 0
    # rotate the asset order + the phrasing template by ROT so a second run is a genuinely NEW prompt list
    # (different asset×facet pairings + different wording) while covering the exact same scenario space.
    r = ROT % len(ALL_ASSETS)
    assets = ALL_ASSETS[r:] + ALL_ASSETS[:r]
    ai = 0  # asset round-robin cursor
    # 1) every facet × cycling assets so all facets are exercised and assets spread across facets
    for fi, (intent, page_hint, templates, cols) in enumerate(FACETS):
        for t_i, tmpl in enumerate(templates):
            asset = assets[ai % len(assets)]
            tmpl = templates[(t_i + ROT) % len(templates)]   # rotate phrasing too
            ai += 1
            pid += 1
            prompts.append({
                "id": pid, "prompt": tmpl.format(asset=asset), "asset": asset,
                "klass": KLASS[asset], "intent": intent, "page_hint": page_hint, "metric_cols": cols,
            })
    # 2) ensure EVERY named asset appears at least once — sweep remaining assets across rotating facets
    seen = {p["asset"] for p in prompts}
    for asset in assets:
        if asset in seen:
            continue
        intent, page_hint, templates, cols = FACETS[ai % len(FACETS)]
        ai += 1
        pid += 1
        prompts.append({
            "id": pid, "prompt": templates[ROT % len(templates)].format(asset=asset), "asset": asset,
            "klass": KLASS[asset], "intent": intent, "page_hint": page_hint, "metric_cols": cols,
        })
    return prompts


if __name__ == "__main__":
    ps = build()
    json.dump(ps, open(OUT, "w"), indent=1)
    # coverage self-report
    cols = set(c for p in ps for c in p["metric_cols"])
    print(f"{len(ps)} prompts")
    print("classes:", sorted({p['klass'] for p in ps}))
    print("intents:", len({p['intent'] for p in ps}), "| page_hints:", len({p['page_hint'] for p in ps}))
    print("distinct assets:", len({p['asset'] for p in ps}), "| metric cols touched:", len(cols))
    print("->", OUT)
