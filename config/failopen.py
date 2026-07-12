"""config/failopen.py — THE guarded cfg readers (dedup D3, refactor campaign 2026-07-12).

Home for the try-import-cfg-except-default shim that was copy-pasted 12× (obs/event, obs/bus, obs/sink_pg,
executor/roster_eval, executor/load_factor_fill, executor/measurable_resolve, renderers/panel_aggregate, llm/client,
+ the guarded-import variants in derivations/power, derivations/nameplate, config/nameplates) and the byte-identical
`_cfg_num` pair (executor/norm_series, executor/yscale).

The import of config.app_config stays INSIDE the functions, so importing THIS module never pulls the DB chain and
never fails — the exact guarded-import property every copy existed for. Pure-fn modules that must import even
without the config package on sys.path (derivations/*) keep their own one-line guarded import OF this module.

NOT repointed here (intentional variants): renderers/_insight's `_env` fallback stub (a DB→env→default chain with
its own namespacing) and derivations/power's clamped knob getters (they pass their own bounds via cfg_num now).
"""


def cfg_safe(key, default):
    """cfg(key, default) that never raises and never blocks import: config unavailable / DB down → `default`."""
    try:
        from config.app_config import cfg
        return cfg(key, default)
    except Exception:
        return default


def cfg_num(key, default, positive=False):
    """A DB-backed numeric knob, else `default` — the code-default mirror. `positive` rejects a non-positive DB value
    (a mis-typed 0/negative band would collapse an axis) and falls back; otherwise negatives fall back. Never raises."""
    try:
        v = float(cfg_safe(key, default))
        if positive:
            return v if v > 0 else default
        return v if v >= 0 else default
    except (TypeError, ValueError):
        return default
