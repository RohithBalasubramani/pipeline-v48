"""grounding/meaningful.py — THE one shared has_meaningful_data(asset, page) probe.

`present ∧ non_null ∧ MEANINGFUL` — the honest has-data signal every layer must agree on. A meter can have rows and
even non-null columns yet carry NOTHING renderable for the page:
  · padded-0 power (a feeder whose active_power_total_kw is a real 0, or denormalized-float garbage -4.6e-44 ≈ 0)   [DS-06]
  · all-NULL THD (harmonic/voltage-THD columns NULL in 100% of latest rows) on a power-quality page                [DS-04]
  · reversed-CT energy (active_energy_import_kwh uniformly 0 while export holds the real MWh) — so 0 is NOT no-data  [DS-05]
  · a SCADA feedbacks table (breaker flags only) pinned to an energy/power page (no metric of that class at all)    [DS-07]

THE RULE (deterministic, no AI): probe the LATEST row of the page's required-class routed columns and decide against the
EDITABLE knobs in cmd_catalog.data_quality_policy (value_min, meaningful_min_power_kw, meaningful_min_energy_delta_kwh,
denorm_epsilon, reversed_ct_import_max). NO magic numbers here — every threshold is a DB row read via config.quality_policy.
This NAMES a verdict + a machine cause; it never emits a fetched number to the card.

Covers: DS-01, DS-04, DS-06, VC-09, and the has_data≠meaningful gap. Route/fingerprint from grounding.schema_route,
class requirements from config.metric_class, energy register from grounding.energy_register.
"""
from __future__ import annotations

from config import metric_class as mc
from config import quality_policy as qp
from config.databases import DATA_DB, DATA_SCHEMA
from data.db_client import q
from grounding import schema_route as sr
from grounding.schema_fingerprint import fingerprint, is_known
from layer1b.resolve.has_data import value_counts, VALUE_MIN

# power-family quantities whose magnitude must clear the meaningful floor (not padded-0 / not denorm garbage).
_POWER_QUANTITIES = ("active_power", "apparent_power", "reactive_power")


def _esc(s):
    return str(s).replace("'", "''")


def _num(x):
    if x in (None, "", "NULL"):
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _latest_row(table, columns):
    """{column: value} for the meter's LATEST row over `columns` (one indexed read). {} for empty/missing table.

    columns must be real physical columns (already routed) — the caller only ever passes routed columns, so the SELECT
    can never reference an absent column.
    """
    cols = [c for c in columns if c]
    if not table or not cols:
        return {}
    sel = ", ".join(f'"{c}"' for c in cols)
    try:
        rows = q(DATA_DB,
                 f'SELECT {sel} FROM {DATA_SCHEMA}."{_esc(table)}" '
                 'ORDER BY "timestamp_utc" DESC LIMIT 1')
    except Exception:
        return {}                                     # unreadable row → treated as no meaningful reading (honest-blank)
    if not rows or not rows[0]:
        return {}
    return dict(zip(cols, rows[0]))


def _meaningful_power(val):
    """A power reading is meaningful when |val| clears the floor AND is not denormalized-float garbage."""
    v = _num(val)
    if v is None:
        return False
    mag = abs(v)
    denorm_eps = qp.num("denorm_epsilon", 1e-30)
    if mag < denorm_eps:                              # -4.6e-44 style garbage ≈ 0 → not a real reading  [DS-06]
        return False
    return mag > qp.num("meaningful_min_power_kw", 0.0)


def _meaningful_energy(table):
    """Meaningful energy exists when the correct register (import OR reversed-CT export) is non-zero.  [DS-05]

    Uses grounding.energy_register to pick the live register so a reversed-CT meter (import≈0, export=300MWh) is NOT
    mistaken for no-data. Falls back to a direct latest-value probe if the register engine is unavailable.
    """
    imp = sr.route(table, "energy_import_kwh")
    exp = sr.route(table, "energy_export_kwh")
    cols = [c for c in (imp, exp) if c]
    if not cols:
        return False
    row = _latest_row(table, cols)
    reg_max = qp.num("reversed_ct_import_max", 1.0)
    iv = _num(row.get(imp)) if imp else None
    ev = _num(row.get(exp)) if exp else None
    # meaningful if either cumulative register carries real energy above the reversed-CT floor.
    if iv is not None and iv > reg_max:
        return True
    if ev is not None and ev > reg_max:
        return True
    return False


def _meaningful_quantity(table, required_class, row_cache):
    """Is `required_class` MEANINGFULLY present on `table`'s latest row (not just non-null)?"""
    slots = sr.columns_for_quantity(table, _canonical(required_class))
    # gather every routed column whose quantity satisfies this class (power spans active/apparent/reactive).
    routed = sr.routed_map(table)
    cols = [meta["column_name"] for meta in routed.values()
            if _class_hits(required_class, meta.get("quantity"))]
    if not cols:
        return False
    # energy uses the register-aware cumulative check (0 import can still be meaningful export).
    if required_class == "energy":
        return _meaningful_energy(table)
    row = _latest_row(table, cols)
    row_cache.update(row)
    if required_class == "power":
        return any(_meaningful_power(row.get(c)) for c in cols)
    # thd / voltage / current / breaker: meaningful == at least one non-null reading (all-null THD → not meaningful).
    return any(_num(row.get(c)) is not None for c in cols)


def _class_hits(required_class, quantity):
    if not required_class or not quantity:
        return False
    rc, qn = required_class.lower(), quantity.lower()
    return rc == qn or rc in qn.split("_")


def _canonical(required_class):
    """schema_map stores 'active_power' etc.; for slots_for_quantity we pass the class through unchanged (matching is
    done token-wise in _class_hits), so this is identity — kept as a seam if a class↔quantity table is added later."""
    return required_class


def _asset_table(asset):
    if isinstance(asset, str):
        return asset or None
    if isinstance(asset, dict):
        return asset.get("table") or asset.get("table_name") or None
    return None


def probe(asset, page_key):
    """Full meaningfulness verdict for the fact-sheet: {ok, present, non_null, meaningful, cause, fingerprint}.

    ok = present ∧ non_null ∧ meaningful-for-the-page. cause is a SEEDED reason_template key the caller renders:
      · 'no_data'          — 0 rows / all-null latest row (nothing to show)
      · 'denorm_garbage'   — the only power reading is denormalized-float garbage
      · 'structurally_null'— required-class columns exist but are all NULL (e.g. voltage-THD/harmonic on power-quality)
      · 'no_class'         — the schema has no column of the page's class at all (SCADA/tm on the wrong page)
      · 'schema_stub'      — the table is a sch_stub (unknown shape) — nothing routes
    """
    table = _asset_table(asset)
    if not table:
        return {"ok": False, "present": False, "non_null": False, "meaningful": False,
                "cause": "no_data", "fingerprint": None}
    fp = fingerprint(table)
    if not is_known(fp):
        return {"ok": False, "present": True, "non_null": False, "meaningful": False,
                "cause": "schema_stub", "fingerprint": fp}

    # present ∧ non_null via the shared value-count probe (rows + >= value_min non-null metric columns in the latest row).
    vmin = int(qp.num("value_min", VALUE_MIN))
    counts = value_counts([table])
    non_null_n = counts.get(table, 0)
    present = non_null_n > 0 or _has_rows(table)
    non_null = non_null_n >= vmin
    if not non_null:
        return {"ok": False, "present": present, "non_null": False, "meaningful": False,
                "cause": "no_data", "fingerprint": fp}

    # MEANINGFUL: every required class for the page has a real reading. Unconstrained page → non-null is enough.
    required = mc.required_classes(page_key)
    row_cache: dict = {}
    if not required:
        return {"ok": True, "present": present, "non_null": True, "meaningful": True,
                "cause": None, "fingerprint": fp}

    missing_class = [rc for rc in required if not sr.has_quantity(table, _canonical(rc))
                     and not any(_class_hits(rc, m.get("quantity")) for m in sr.routed_map(table).values())]
    if missing_class:
        return {"ok": False, "present": present, "non_null": True, "meaningful": False,
                "cause": "no_class", "fingerprint": fp, "missing_class": missing_class}

    meaningful = all(_meaningful_quantity(table, rc, row_cache) for rc in required)
    if meaningful:
        return {"ok": True, "present": present, "non_null": True, "meaningful": True,
                "cause": None, "fingerprint": fp}

    # non-null columns exist for the class but they read as padded-0 / denorm / all-null → structurally not meaningful.
    cause = "denorm_garbage" if _only_denorm_power(table, required, row_cache) else "structurally_null"
    return {"ok": False, "present": present, "non_null": True, "meaningful": False,
            "cause": cause, "fingerprint": fp}


def _only_denorm_power(table, required, row_cache):
    """True when a power class was required and every populated power column read as sub-epsilon garbage.

    Re-probes the power columns directly (independent of which required class failed first) so a meter whose ONLY defect
    is denormalized-float garbage gets the precise 'denorm_garbage' cause rather than a generic 'structurally_null'.
    """
    if "power" not in required:
        return False
    routed = sr.routed_map(table)
    cols = [m["column_name"] for m in routed.values() if _class_hits("power", m.get("quantity"))]
    if not cols:
        return False
    row = row_cache if all(c in row_cache for c in cols) else _latest_row(table, cols)
    denorm_eps = qp.num("denorm_epsilon", 1e-30)
    vals = [v for v in (_num(row.get(c)) for c in cols) if v is not None]
    return bool(vals) and all(abs(v) < denorm_eps for v in vals)


def _has_rows(table):
    try:
        rows = q(DATA_DB, f'SELECT EXISTS(SELECT 1 FROM {DATA_SCHEMA}."{_esc(table)}")')
        return bool(rows) and str(rows[0][0]).strip().lower() in ("t", "true", "1")
    except Exception:
        return False


def has_meaningful_data(asset, page_key):
    """The boolean the whole pipeline shares: True ⇒ this meter can render the page with REAL data; False ⇒ honest-blank.

    A thin wrapper over probe() so callers that only need the gate don't unpack the dict. `page_key` may be None/'' for
    a class-agnostic 'does this meter carry ANY renderable metric' check.
    """
    return bool(probe(asset, page_key)["ok"])
