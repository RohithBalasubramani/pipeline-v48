"""ems_exec/executor/canonical_slots.py — DETERMINISTIC completion of a voltage-monitor card's CONTRACT slots.

A voltage-monitor card's structural slots are a FIXED CONTRACT, not open-ended prompt meaning:
  * the phase LEGEND is the three L-N phase magnitudes (voltage_r_n / voltage_y_n / voltage_b_n),
  * the METRICS rail is average / max / min (voltage_avg / voltage_max / voltage_min),
  * the THRESHOLD band is the IS-12360 statutory ±band around the asset's nominal L-N voltage — the SHADED region.

Per the doctrine (deterministic owns facts / math / CONTRACT; the AI decides open-ended meaning), this pass fills any of
those canonical slots the L2 emit LEFT UNBOUND. It NEVER touches a slot the AI already bound, so it can only COMPLETE a
partial/omitted emit — never override an AI decision. That fixes two observed gaps on the Transformer-01 voltage card:
  (E1) the R/Y/B legend rendering "—" when the emit omitted the per-phase legend binds (AI-emit variance), and
  (E2) the shaded ±band being absent entirely — the emit offers no band source, so the model omits the thresholds
       (→ null) or binds them to voltage_avg (→ a flat line, no band).

Honest-degrade throughout: a column the meter lacks → the legend/metric slot stays blank; no recoverable nominal → the
band stays blank (NEVER a fabricated limit). Generic — every decision reads the skeleton's OWN slot shape + labels, no
card ids. The injected binds are canonical same-quantity fills (voltage column → voltage slot; statutory band →
threshold), so they are honest by construction.

Flag fill.canonical_slots (default off = today's exact behavior). Runs at FILL time (ems_exec/serve/run.run_card),
after the L2 emit + its honesty gates — it only widens what the executor fills, never what the emit claimed."""
import copy
import re

_PHASE_RE = re.compile(r"(?i)\b([ryb])\b[\s\-]*phase|phase[\s\-]*\b([ryb])\b|^([ryb])[\s\-]")
_PHASE_COL = {"r": "voltage_r_n", "y": "voltage_y_n", "b": "voltage_b_n"}
_METRIC_COL = {"average": "voltage_avg", "avg": "voltage_avg", "mean": "voltage_avg",
               "max": "voltage_max", "maximum": "voltage_max", "peak": "voltage_max",
               "min": "voltage_min", "minimum": "voltage_min"}


def _on():
    try:
        from config.app_config import flag_on
        return flag_on("fill.canonical_slots", False)
    except Exception:
        return False


def _phase_col_for(label):
    """The L-N phase column a legend label names (B-Phase → voltage_b_n), or None. Reads the label's OWN phase letter."""
    m = _PHASE_RE.search(str(label or ""))
    if not m:
        return None
    letter = next((g for g in m.groups() if g), None)
    return _PHASE_COL.get((letter or "").lower())


def _metric_col_for(label):
    """The stat column a metrics-rail label names (Average → voltage_avg, Max → voltage_max, Min → voltage_min)."""
    t = str(label or "").strip().lower()
    for key, col in _METRIC_COL.items():
        if t == key or t.startswith(key):
            return col
    return None


def _is_voltage_card(data, bound_cols):
    """A voltage-monitor card: the y-axis says Voltage, or the emit already binds a voltage_* column. Distinguishes the
    Voltage Monitor from the sibling Current Monitor (same shape, current columns / 'Current' axis) so the voltage band
    never lands on a current card."""
    y = str((data or {}).get("yAxisLabel") or "").lower()
    if "voltage" in y:
        return True
    return any(str(c or "").startswith("voltage") for c in bound_cols)


def _statutory_band(asset_table):
    """The asset's IS-12360 statutory voltage band {min, max, nominal} (rounded), or None to honest-degrade. Reuses the
    ems_exec voltage derivation over the meter's latest row (voltage_avg + kpi_voltage_deviation_pct) + the asset_table
    (so derivation.nameplate_nominal_first can prefer the nameplate nominal). One small latest-row read; never raises."""
    try:
        from ems_exec.data import neuract as _nx
        from ems_exec.derivations import voltage as _v
        row = _nx.latest(asset_table, ["voltage_avg", "kpi_voltage_deviation_pct"]) if asset_table else {}
        return _v.statutory_band({"row": row or {}, "asset_table": asset_table})
    except Exception:
        return None


def inject(exact_metadata, data_instructions, asset_table):
    """Return data_instructions extended with the canonical voltage-monitor binds for any UNBOUND contract slot. A COPY
    is returned (the caller's dict is never mutated); the input is returned unchanged when the flag is off, the skeleton
    is not a voltage-monitor shape, or nothing is missing. Fail-open: any error → the original data_instructions."""
    try:
        if not _on() or not isinstance(exact_metadata, dict):
            return data_instructions
        data = exact_metadata.get("data")
        if not isinstance(data, dict):
            return data_instructions
        di = data_instructions if isinstance(data_instructions, dict) else {}
        fields = [f for f in (di.get("fields") or []) if isinstance(f, dict)]
        bound = {str(f.get("slot") or "") for f in fields}
        bound_cols = [f.get("column") for f in fields if f.get("column")]
        if not _is_voltage_card(data, bound_cols):
            return data_instructions

        add = []

        def _raw(slot, col):
            if col and slot not in bound:
                add.append({"slot": slot, "kind": "raw", "column": col, "metric": col,
                            "source": "live", "_canonical": True})

        # E1 — phase legend + metrics rail: bind each UNBOUND value slot from the slot's OWN label.
        legend = data.get("legendItems")
        if isinstance(legend, list):
            for i, item in enumerate(legend):
                if isinstance(item, dict):
                    _raw(f"data.legendItems[{i}].value", _phase_col_for(item.get("label")))
        metrics = data.get("metrics")
        if isinstance(metrics, list):
            for i, item in enumerate(metrics):
                if isinstance(item, dict):
                    _raw(f"data.metrics[{i}].value", _metric_col_for(item.get("label")))

        # E2 — statutory ±band → the shaded region. Only when BOTH threshold value slots are unbound (never half a band)
        # and the asset has a recoverable band (honest-blank otherwise). value + label injected as consts so the drawn
        # band and its reference-line labels are consistent (the label also gives PhaseMonitorChart a unique React key).
        thr = data.get("thresholds")
        if (isinstance(thr, list) and len(thr) >= 2
                and "data.thresholds[0].value" not in bound and "data.thresholds[1].value" not in bound):
            band = _statutory_band(asset_table)
            if band and band.get("max") is not None and band.get("min") is not None:
                hi, lo = band["max"], band["min"]
                add += [
                    {"slot": "data.thresholds[0].value", "kind": "const", "value": hi, "_canonical": True},
                    {"slot": "data.thresholds[1].value", "kind": "const", "value": lo, "_canonical": True},
                ]
                if "data.thresholds[0].label" not in bound:
                    add.append({"slot": "data.thresholds[0].label", "kind": "const",
                                "value": f"Max - {hi:g}V", "_canonical": True})
                if "data.thresholds[1].label" not in bound:
                    add.append({"slot": "data.thresholds[1].label", "kind": "const",
                                "value": f"Min - {lo:g}V", "_canonical": True})

        if not add:
            return data_instructions
        out = copy.deepcopy(di) if di else {"fields": []}
        out["fields"] = list(out.get("fields") or []) + add
        return out
    except Exception:
        return data_instructions
