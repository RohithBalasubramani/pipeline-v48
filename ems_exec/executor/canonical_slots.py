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


# ── F7 aggregate-from-phases ─────────────────────────────────────────────────────────────────────────────────────────
# A meter's OWN aggregate register (avg / unbalance) can be present-but-ALL-NULL (HT CT wiring) while the per-phase
# magnitudes are fully live. The aggregate IS the arithmetic mean / (max−min)/mean of the measured phases — real data,
# not a fabricated stand-in. Map: dead aggregate column -> (phase derivation fn, the component columns it needs).
_AGG_FROM_PHASES = {
    "current_avg":           ("phaseCurrentAvg",          ["current_r", "current_y", "current_b"]),
    "current_unbalance_pct": ("phaseCurrentUnbalancePct", ["current_r", "current_y", "current_b"]),
    "voltage_avg":           ("phaseVoltageAvg",          ["voltage_r_n", "voltage_y_n", "voltage_b_n"]),
    "voltage_unbalance_pct": ("phaseVoltageUnbalancePct", ["voltage_r_n", "voltage_y_n", "voltage_b_n"]),
}


def _agg_on():
    """fill.derive_aggregate_from_phases [F7, default off]: when a raw field is bound to an aggregate column that is NULL
    on this meter but its per-phase components ARE present, swap the bind to the phase-derivation. Fail-open to OFF."""
    try:
        from config.app_config import flag_on
        return flag_on("fill.derive_aggregate_from_phases", False)
    except Exception:
        return False


def _swap_aggregate_from_phases(fields, asset_table):
    """Rewrite in place any raw field bound to a dead (all-NULL-on-this-meter) aggregate column whose per-phase
    components are present → a derived phase-aggregate. Fact-gated: reads ONE latest row; a swap fires ONLY when the
    aggregate is null AND every component is non-null (else the field is left exactly as the emit bound it → honest-blank
    stays honest). Returns the number of fields swapped."""
    try:
        cand = [f for f in fields if isinstance(f, dict) and (f.get("kind") or "raw").lower() == "raw"
                and f.get("column") in _AGG_FROM_PHASES]
        if not cand:
            return 0
        from ems_exec.data import neuract as _nx
        need = set()
        for f in cand:
            _fn, comps = _AGG_FROM_PHASES[f["column"]]
            need.add(f["column"]); need.update(comps)
        row = _nx.latest(asset_table, sorted(need)) if asset_table else {}
        n = 0
        for f in cand:
            col = f["column"]
            fn, comps = _AGG_FROM_PHASES[col]
            if row.get(col) is None and all(row.get(c) is not None for c in comps):
                f["kind"] = "derived"
                f["fn"] = fn
                f["column"] = None            # the derived path reads the phase columns from ctx, not a single column
                f["_canonical"] = "agg_from_phases"
                n += 1
        return n
    except Exception:
        return 0


# ── F6 statutory-band geometry (sibling voltage cards: history maxLine/minLine + expected range) ──────────────────────
# The Voltage History / DG-voltage cards draw the SAME IS-12360 band as the Voltage Monitor, but on differently-named
# slots (…maxLine.value / …minLine.value / …expectedMax / …expectedMin) at card-specific depths. Fill them from the same
# nameplate-first statutory band, matched by the leaf's OWN key suffix (no per-card paths). const value + a "Max/Min"
# label sibling where present.
_BAND_GEO = {"maxline.value": "max", "minline.value": "min", "expectedmax": "max", "expectedmin": "min"}


def _band_geo_on():
    """fill.canonical_band_geometry [F6, default off]: fill unbound statutory-band geometry leaves (maxLine/minLine/
    expectedMax/expectedMin) on sibling voltage cards from the nameplate band. Fail-open to OFF."""
    try:
        from config.app_config import flag_on
        return flag_on("fill.canonical_band_geometry", False)
    except Exception:
        return False


def _walk_scalar_leaves(node, prefix=""):
    """Yield (slot_path_from_ROOT, key_lastsegment_lower, value) for every scalar leaf. The path uses the payload's OWN
    root keys (card 37 → 'data.thresholds[0].value'; card 44 → 'history.data.expectedMax') so it matches the di slot
    convention regardless of whether the card nests its chart under 'data' or another root key."""
    if isinstance(node, dict):
        for k, v in node.items():
            p = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, (dict, list)):
                yield from _walk_scalar_leaves(v, p)
            else:
                yield (p, str(k).lower(), v)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            p = f"{prefix}[{i}]" if prefix else f"[{i}]"
            if isinstance(v, (dict, list)):
                yield from _walk_scalar_leaves(v, p)
            else:
                yield (p, "", v)


def _skeleton_is_voltage(exact_metadata, bound_cols):
    """A voltage card, detected robustly for ARBITRARY nesting: a bound voltage_* column, or a 'Voltage' y-axis anywhere
    in the skeleton (the chart may sit under history.data / health.data, not the top-level data)."""
    if any(str(c or "").startswith("voltage") for c in bound_cols):
        return True
    for _p, key, val in _walk_scalar_leaves(exact_metadata):
        if key in ("yaxislabel", "unit") and isinstance(val, str) and "voltage" in val.lower():
            return True
    return False


def _band_geometry_add(exact_metadata, di, asset_table):
    """const fills for UNBOUND statutory-band geometry leaves on a voltage card, from the nameplate band. [] otherwise.
    Walks from the payload ROOT (not exact_metadata['data']) — the Voltage History / DG-voltage charts nest under
    history.data / their own root key, so a 'data'-rooted walk would miss every band leaf."""
    if not isinstance(exact_metadata, dict):
        return []
    fields = [f for f in (di.get("fields") or []) if isinstance(f, dict)]
    bound = {str(f.get("slot") or "") for f in fields}
    if not _skeleton_is_voltage(exact_metadata, [f.get("column") for f in fields if f.get("column")]):
        return []
    # collect candidate band-geometry leaves first (cheap) before paying for the band read
    cands = []
    for path, _key, _val in _walk_scalar_leaves(exact_metadata):
        tail2 = ".".join(path.lower().split(".")[-2:])       # e.g. 'maxline.value'
        tail1 = path.lower().split(".")[-1]                  # e.g. 'expectedmax'
        which = _BAND_GEO.get(tail2) or _BAND_GEO.get(tail1)
        if which and path not in bound:
            cands.append((path, which))
    if not cands:
        return []
    band = _statutory_band(asset_table)
    if not band or band.get("max") is None or band.get("min") is None:
        return []
    add = [{"slot": path, "kind": "const", "value": band[which], "_canonical": "band_geometry"}
           for (path, which) in cands]
    # fill a sibling *Line.label ONLY when it is a bare SCALAR leaf (card-67 shape 'Max: +5%'); a structured label object
    # (card-44 {prefix,value,unit}) is not a scalar leaf here, so it is left for its own value leaf to drive.
    scalar_paths = {p for p, _k, _v in _walk_scalar_leaves(exact_metadata)}
    for path, which in cands:
        if path.lower().endswith("line.value"):
            lbl = path[: -len(".value")] + ".label"
            if lbl not in bound and lbl in scalar_paths:
                tag = "Max" if which == "max" else "Min"
                add.append({"slot": lbl, "kind": "const", "value": f"{tag}: {band[which]:g}V", "_canonical": "band_geometry"})
    return add


def _voltage_canonical_add(data, di, asset_table):
    """The UNBOUND voltage-monitor contract binds to APPEND (phase legend, avg/max/min rail, statutory ±band). [] when
    the card isn't a voltage-monitor shape or nothing is missing. Never touches an AI-bound slot."""
    fields = [f for f in (di.get("fields") or []) if isinstance(f, dict)]
    bound = {str(f.get("slot") or "") for f in fields}
    bound_cols = [f.get("column") for f in fields if f.get("column")]
    if not _is_voltage_card(data, bound_cols):
        return []
    add = []

    def _raw(slot, col):
        if col and slot not in bound:
            add.append({"slot": slot, "kind": "raw", "column": col, "metric": col,
                        "source": "live", "_canonical": True})

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
    return add


def inject(exact_metadata, data_instructions, asset_table):
    """Return data_instructions with the deterministic contract-fill passes applied. A COPY is returned only when a pass
    actually changes something (the caller's dict is never mutated); otherwise the input is returned unchanged. Each pass
    is independently flag-gated; fail-open on any error → the original data_instructions.

    Passes: (1) fill.canonical_slots — voltage-monitor legend/metrics/band fill of UNBOUND slots; (2)
    fill.derive_aggregate_from_phases [F7] — swap a raw field bound to a dead aggregate column to a phase-derivation."""
    try:
        di = data_instructions if isinstance(data_instructions, dict) else {}
        out = None                                   # lazily deep-copied on the first real mutation

        # PASS 1 — voltage-card canonical fill (append unbound contract binds)
        if _on() and isinstance(exact_metadata, dict) and isinstance(exact_metadata.get("data"), dict):
            add = _voltage_canonical_add(exact_metadata["data"], di, asset_table)
            if add:
                out = copy.deepcopy(di) if di else {"fields": []}
                out["fields"] = list(out.get("fields") or []) + add

        # PASS 2 — aggregate-from-phases swap (rewrite dead-aggregate binds; any card type)
        if _agg_on():
            probe = out if out is not None else (copy.deepcopy(di) if di else {"fields": []})
            if _swap_aggregate_from_phases(probe.get("fields") or [], asset_table):
                out = probe

        # PASS 3 — statutory-band geometry fill on sibling voltage cards (maxLine/minLine/expected range)
        if _band_geo_on() and isinstance(exact_metadata, dict):
            add = _band_geometry_add(exact_metadata, (out or di), asset_table)
            if add:
                out = out if out is not None else (copy.deepcopy(di) if di else {"fields": []})
                out["fields"] = list(out.get("fields") or []) + add

        return out if out is not None else data_instructions
    except Exception:
        return data_instructions
