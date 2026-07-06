"""config/vocab.py — the STRUCTURAL payload vocabularies, DB-driven (cmd_catalog.app_config). One concern.

NO column-choice heuristics live here (the AI binds columns itself from the full schema + each leaf's verbatim
label/unit/section context). What remains is purely structural/dimensional, each an app_config row
(data_type='json', section='vocab') — the DB is the SINGLE home, there are NO code literals:
    unit_quantities    — fixed dimensional lookup (kW→power) feeding ONLY the negative-power abs() convention.
    element_value_keys — which object keys carry the fillable NUMBER inside a series-of-objects (enumeration, not choice).
    time_axis_keys     — which leaf keys are the time axis (the kind='time' executor contract).
    value_keys/label_keys — the numeric-string-KPI detection in leaf_classify (data-vs-chrome, not column choice).
A NEW DATA DB / payload shape is onboarded by ADDING/EDITING ROWS, no code change:

    global row:     key = 'vocab.<name>'                 (applies to every data DB)
    per-DB row:     key = 'vocab.<db_link>.<name>'       (overrides the global for ONE data DB whose naming diverges)

On a missing row / unreachable DB the accessor returns None (honest degrade: consumers treat it as an empty
vocabulary and their behavior narrows — never a fabricated guess from a code list).
Accessors are memoized per process (the underlying cfg() table read is process-cached; the json parse here is too).
Seed: db/seed_vocab.sql. [config → DB; updatable as data DBs are added]
"""
from functools import lru_cache

from config.app_config import cfg


@lru_cache(maxsize=64)
def vocab(name, db_link=None):
    """The active vocabulary for `name` — per-DB row ('vocab.<db_link>.<name>') > global row ('vocab.<name>') > None
    (honest degrade on miss/outage). Lists/dicts come back parsed (rows are data_type='json'). Never raises."""
    try:
        if db_link:
            scoped = cfg(f"vocab.{db_link}.{name}", None)
            if scoped:
                return scoped
        return cfg(f"vocab.{name}", None)
    except Exception:
        return None




def unit_quantity(unit, db_link=None):
    """The quantity implied by an explicit unit string ('V' → voltage), or None."""
    u = (unit or "").strip().lower()
    return (vocab("unit_quantities", db_link) or {}).get(u)
