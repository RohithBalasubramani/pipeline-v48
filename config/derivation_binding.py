"""config/derivation_binding.py — thin reader over cmd_catalog.derivation_binding (recovery fn ↔ base columns).

For a derived metric: the registry fn that computes it, the real base columns it needs, and its fidelity. A fn is only
bindable when its base_columns ⊆ the columns actually present/fetched (the caller checks that); a 'nameplate:*' pseudo-
column means the base comes from asset_nameplate, not the meter frame. NO hardcoded fn/base map in logic code — READS
this table. [DID-02/05, DS-04(ieee519)]
"""
from data.db_client import q

_COLS = ["metric", "fn", "base_columns", "fidelity", "scope"]


_UNIT_SUFFIX = None      # lazy-compiled unit-token stripper (normalize layer)
_norm_cache = {}         # normalized-form → canonical metric key (per-process; DB edits need a restart like cfg)


def _normalize(key):
    """Fold the spelling axes emit invents on: case, -/_ separators, and a trailing DIMENSIONLESS token
    (pct/percent). 'Load_Factor_PCT' → 'loadfactor'; 'active_energy_kwh' → 'activeenergykwh'. MAGNITUDE unit
    tokens (kwh/mvarh/kva…) are deliberately KEPT — folding them could silently alias across a ×1000 unit
    mismatch (reactiveEnergyKvarh onto an MVARh-outputting fn). [audit 14: ~56% of derivation_unbound named a
    computable quantity under an invented spelling]"""
    global _UNIT_SUFFIX
    if _UNIT_SUFFIX is None:
        import re
        _UNIT_SUFFIX = re.compile(r"(pct|percent)$")
    k = "".join(c for c in str(key or "").lower() if c.isalnum())
    return _UNIT_SUFFIX.sub("", k)


def _exact(metric):
    rows = q("cmd_catalog",
             "SELECT " + ",".join(_COLS) + f" FROM derivation_binding WHERE metric='{_esc(metric)}'")
    if not rows:
        return None
    _, fn, base, fidelity, scope = (list(rows[0]) + ["row"])[:5]
    return {"fn": fn, "base_columns": _split(base), "fidelity": fidelity, "scope": (scope or "row").strip() or "row"}


def binding(metric):
    """{fn, base_columns:[...], fidelity, scope} for a derived metric, or None if it isn't a registered derivation.
    `scope` ('row'|'window'|'series'|'topology') tells the executor which ctx to build — a series/window-scoped fn needs
    the windowed time-series (∫power, load-factor, peaks), not just the latest row. Defaults to 'row' (a NULL cell).

    RESOLUTION ORDER [audit 2026-07-14, 14 F1 — emit invents free-form keys; ~56% named a computable quantity]:
      1. exact match (byte-identical to the historical behavior);
      2. NORMALIZED match — case/-/_/trailing-unit-token folded against the registered metric keys, accepted only
         when it lands on exactly ONE canonical key (an ambiguous fold stays honest-unbound);
      3. the cmd_catalog.derivation_alias table (alias → canonical metric, seeded quantity-verified only), one hop.
    A miss everywhere → None → the honest derivation_unbound reason, exactly as before."""
    b = _exact(metric)
    if b is not None:
        return b
    norm = _normalize(metric)
    if not norm:
        return None
    try:
        if norm not in _norm_cache:
            rows = q("cmd_catalog", "SELECT metric FROM derivation_binding")
            folds = {}
            for r in rows or []:
                folds.setdefault(_normalize(r[0]), []).append(r[0])
            _norm_cache.update({k: (v[0] if len(v) == 1 else None) for k, v in folds.items()})
        canon = _norm_cache.get(norm)
        if canon and canon != metric:
            return _exact(canon)
    except Exception:
        pass
    try:
        # alias keys are stored in NORMALIZED form (one row covers every case/separator/unit spelling variant)
        rows = q("cmd_catalog", f"SELECT metric FROM derivation_alias WHERE alias='{_esc(norm)}'")
        if rows and rows[0] and rows[0][0]:
            return _exact(rows[0][0])
    except Exception:
        pass
    return None


def base_columns(metric):
    """The real base columns a metric's fn needs → [...] ('nameplate:rated_kva' style pseudo-cols kept as-is)."""
    b = binding(metric)
    return b["base_columns"] if b else []


def all_bindings():
    rows = q("cmd_catalog", "SELECT " + ",".join(_COLS) + " FROM derivation_binding ORDER BY metric")
    return [{"metric": r[0], "fn": r[1], "base_columns": _split(r[2]), "fidelity": r[3]} for r in rows]


_TOPOLOGY_PAIR_DEFAULT = frozenset({"hv_input_kw", "lv_output_kw"})
_topo_cache = {}


def topology_pair_columns():
    """The SYNTHETIC TOPOLOGY-PAIR column vocabulary — the base columns of every scope='topology' derivation row
    (hv_input_kw / lv_output_kw: boundary quantities computed ACROSS meters, never measured by one). The emit gate
    uses it to refuse a single-meter proxy into a boundary slot (card 41: the meter's own active power shipped as
    'HV INPUT'). Cached per process; DB outage → the code-default mirror of the seed rows (never an empty wall)."""
    if "cols" in _topo_cache:
        return _topo_cache["cols"]
    try:
        rows = q("cmd_catalog", "SELECT base_columns FROM derivation_binding WHERE scope='topology'")
        cols = frozenset(c for r in rows for c in _split(r[0]) if not c.startswith("nameplate:"))
        _topo_cache["cols"] = cols or _TOPOLOGY_PAIR_DEFAULT
    except Exception:
        return _TOPOLOGY_PAIR_DEFAULT
    return _topo_cache["cols"]


def _split(base):
    return [c.strip() for c in (base or "").split(",") if c.strip()]


from config.policy_read import esc as _esc  # the ONE shared SQL-quote escape  # noqa: E402
