"""Deterministic name / unit / kind text helpers.

Turn raw live-table and neuract column names into clean human labels, panel/feeder
locations, inferred units and measured-vs-derived kinds — the offline fallbacks used
when the model is down (see also metrics._derive_metric_labels for the AI path).
Mirrors the naming convention in layer1b/describe.py (compat columns have no name col).
"""
import re

# device_mappings tables that are NOT user-facing assets: test/dev fixtures + transport-duplicate
# meters (esp32_/mqtt_ mirror the canonical mfm_* meters).
_SKIP_ASSET = re.compile(
    r"^(last_test|latest_test|test_meter|e2e_|march|my_mfm$|meter_\d+_data$|"
    r"edge_unmapped$|device_mappings$|esp32_mfm|mqtt_mfm)", re.I)

# redundant GIC location prefix on the resolver's name (load_group already carries it)
_GIC_PREFIX = re.compile(r"^GIC-\d+-N\d+-\s*", re.I)

# --- v48 metric naming (compat columns have no name column; synthesize like layer1b/describe.py) ---
_UNIT_SUFFIX = [
    ("_kwh", "kWh"), ("_kvah", "kVAh"), ("_kvarh", "kVArh"), ("_mwh", "MWh"),
    ("_kw", "kW"), ("_kva", "kVA"), ("_kvar", "kVAr"), ("_hz", "Hz"),
    ("_pct", "%"), ("_rpm", "rpm"), ("_min", "min"), ("_hr", "hr"), ("_a", "A"),
]
_DERIVED_HINTS = ("_pct", "_unbalance", "_deviation", "_avg", "_min", "_max", "_spread",
                  "_share", "_count", "_status", "_today", "_this_", "_events")


def _fallback_asset_name(tbl):
    """Deterministic name when the model is down: strip the gic_<panel>_n<node>_ wrapper and the
    _pN phase / _mfm / _feedbacks suffixes, then title-case."""
    s = re.sub(r"^gic_\d+_n\d+_", "", tbl)
    s = re.sub(r"_p\d+$", "", s)
    s = re.sub(r"_(mfm|feedbacks)$", "", s)
    return s.replace("_", " ").strip().title() or tbl


def _asset_location(tbl):
    """Deterministic panel/feeder position from the live table name: 'gic_01_n3_...' -> 'GIC-01 N3'."""
    gm = re.match(r"^gic_0*(\d+)_n0*(\d+)_", tbl)
    return f"GIC-{gm.group(1)} N{gm.group(2)}" if gm else ""


def _tidy(name):
    """Trim the redundant 'GIC-NN-NN-' location prefix from the resolver name for display
    (kept in load_group + full name in keywords). 'GIC-01-N10-HHF-01 ...' -> 'HHF-01 ...'."""
    return _GIC_PREFIX.sub("", name).strip() or name


def _infer_unit(col):
    c = col.lower()
    if c.startswith("voltage") or c.endswith("_v"):
        return "V"
    if c.startswith("current") or c.endswith("_a"):
        return "A"
    if "temperature" in c or c.endswith("_c"):
        return "°C"
    for suf, u in _UNIT_SUFFIX:
        if c.endswith(suf):
            return u
    return ""


def _infer_kind(col):
    c = col.lower()
    return "derived" if any(h in c for h in _DERIVED_HINTS) else "measured"


def _title(col):
    return col.replace("_", " ").title()
