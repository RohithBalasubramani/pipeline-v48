"""derivations/_coerce.py — the ONE float-or-None coercer for the derivation library (pure, imports nothing).

Home for the six byte-identical private `_f` copies that lived in energy/voltage/power/current/power_quality/topology
(dedup D4, refactor campaign 2026-07-12). Import as `from ._coerce import f as _f` so call sites stay byte-identical.

Deliberately DIVERGENT variants that must NOT be repointed here (drift documented so nobody assumes interchangeable):
  · ems_exec/derivations/breaker.py `_num`     — treats ''/None as None BEFORE float() (accepts numeric 0 unchanged)
  · registries/neuract/nameplate.py `_num`     — returns the ORIGINAL value on coercion failure
  · config/nameplates.py                       — RAISES on non-numeric text (loud config error is the point)
  · ems_exec/renderers/_agg.py `num`           — finite-only (NaN/inf → None) for executor/renderer paths
  · ems_exec/executor/trend_badge.py           — is-number predicate, not a coercer
  · ems_exec/derivations/evaluate.py           — raises _Degrade (the expression interpreter's contract)
"""


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None
