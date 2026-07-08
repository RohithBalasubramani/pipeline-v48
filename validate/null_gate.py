"""validate/null_gate.py — the >MAX_NULL_RATE gate POLICY + event/counter/boolean column semantics (non-AI). [validate]

USER DIRECTIVE (2026-07-07): a basket column that is >50% null over the probe window is NOT a defect by itself.
Event/counter columns are SPARSE BY NATURE (dg_1_mfm current_imbalance_event_active: 99.85% null = a 12-min event
burst; NULL means 'no event'), and even a genuinely dead electrical register is per-leaf telemetry, never the page
banner's 'N fail'. So the >50%-null check no longer produces verdict=fail — an informational warn AT MOST.

TWO DB-DRIVEN KNOBS (cmd_catalog.app_config via cfg(); seed: db/seed_validate_null_gate.sql):
  validate.null_gate_mode         'fail' | 'warn' | 'off'          (code default 'warn')
      what the >MAX_NULL_RATE check produces for a NON-event column: legacy fail / informational warn / nothing.
      'off' silences the whole null-rate annotation for a mostly-null column (the separate >WARN_NULL_RATE
      annotation covers only the (WARN, MAX] band, as before); the latest-row warn is untouched.
  validate.event_semantic_tokens  JSON name-token list             (code default ["_event_", "_count", "_active", "_flag"])
      a column whose lowercased name matches a token (a token ending '_' matches ANYWHERE in the name, any other
      token matches as a SUFFIX) — or whose dtype is boolean — carries EVENT/COUNTER/BOOLEAN semantics:
      NULL = 'no event' ≡ 0, so null-rate sparsity is NORMAL (verdict pass with an informational reason) and the
      'no value in latest row' warn does not apply (a null latest row means 'no event now').

COERCION BOUNDARY (fence): validate/ applies the null≡0 semantics ONLY to its own verdict statistics
(coerce_event_nulls below). The actual read-path NULL→0 fill belongs to the EXECUTOR, outside this fence — the
hook would go in ems_exec/data/neuract.py (the latest/window/bucket readers around _num) and/or
ems_exec/executor/recipe.py (per-leaf binding), keyed by is_event_semantic(). Electrical quantities are NEVER
coerced anywhere — a null voltage is NOT 0 V (honest-blank per leaf, as today).
"""
from config.app_config import cfg

_MODES = ("fail", "warn", "off")
DEFAULT_MODE = "warn"
DEFAULT_EVENT_TOKENS = ("_event_", "_count", "_active", "_flag")


def null_gate_mode():
    """The >MAX_NULL_RATE verdict policy: DB row validate.null_gate_mode, else 'warn'. Unknown values fall back
    to the default (never a surprise fail from a typo'd row)."""
    m = str(cfg("validate.null_gate_mode", DEFAULT_MODE)).strip().lower()
    return m if m in _MODES else DEFAULT_MODE


def event_semantic_tokens():
    """The event/counter/flag name-token vocabulary: DB row validate.event_semantic_tokens (json list), else the
    code default. Malformed rows honest-degrade to the default so the gate NEVER widens on a bad row: a non-list JSON
    value (a fat-fingered "_burst" string, a dict, a number, null) must NOT be iterated — a bare "_burst" string would
    fan out into per-char tokens ['_','b',...] and '_' (a trailing-'_' token) then matches EVERY underscore-bearing
    column, coercing null voltage/power to 0 (the exact fabrication the directive forbids). Type-guard first, then
    normalize; an empty/all-blank list also degrades to the default."""
    toks = cfg("validate.event_semantic_tokens", list(DEFAULT_EVENT_TOKENS))
    if not isinstance(toks, (list, tuple)):        # scalar / dict / null JSON row → keep the code-default vocab
        return list(DEFAULT_EVENT_TOKENS)
    toks = [str(t).strip().lower() for t in toks if str(t).strip()]
    return toks or list(DEFAULT_EVENT_TOKENS)


def is_event_semantic(column, dtype=None):
    """EVENT/COUNTER/BOOLEAN semantics for a column: NULL means 'no event' (≡ 0), NOT missing data.
    Signals: the DB-driven name-token vocab (trailing-'_' token → substring, else suffix) OR a boolean dtype.
    STRICTLY name/dtype semantics — an electrical quantity (voltage/current/power/energy) never matches
    (verified against the live neuract information_schema: only *_event_*, *_count, *_flag, *_active and
    boolean status/breaker columns hit)."""
    name = str(column or "").lower()
    if str(dtype or "").lower().startswith("bool"):
        return True
    for t in event_semantic_tokens():
        if (t in name) if t.endswith("_") else name.endswith(t):
            return True
    return False


def coerce_event_nulls(s):
    """The validate-LOCAL coercion point: the VERDICT statistics of an event-semantic column read NULL as 0
    ('no event happened in this sample'). Returns a coerced COPY (the frame is never mutated); the report keeps
    the RAW null_rate as honest sparsity telemetry. Callers must gate on is_event_semantic() — electrical
    columns are never passed here. (An all-NULL column arrives object-dtyped from read_sql; the no-downcast
    option keeps fillna silent — only notna-based stats are read, the dtype is irrelevant.)"""
    import pandas as pd
    try:
        with pd.option_context("future.no_silent_downcasting", True):
            return s.fillna(0)
    except Exception:                       # older pandas without the option / extension dtypes rejecting a 0 fill
        try:
            return s.fillna(0)
        except Exception:
            return s.astype("object").fillna(0)
