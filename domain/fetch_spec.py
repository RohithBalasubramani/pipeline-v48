"""domain/fetch_spec.py — the ONE home for the data_instructions FETCH block name (+ its legacy alias).

The AI emits `data_instructions.fetch` — the fetch spec that drives the live data read: {endpoint, window_seconds,
interval_seconds, sample_count, range, start, end, sampling, metrics, selection}. The block was historically named
after the retired EMS media/WS service; the 2026-07-12 purge renamed it. THIS MODULE is deliberately the only place
in active code that still knows the old spelling — replay tapes and historical run dumps carry it, and they must
keep replaying byte-honestly. Everything else reads `FETCH_KEY` / calls these helpers. [rename 2026-07-12]
"""

FETCH_KEY = "fetch"
_LEGACY_KEY = "ems_backend"          # retired service's name — tapes/old dumps only; never emitted or written anew


def fetch_spec(data_instructions):
    """The fetch-spec dict of a data_instructions mapping (new key, else the legacy alias), or {} — never None."""
    di = data_instructions or {}
    spec = di.get(FETCH_KEY)
    if not isinstance(spec, dict):
        spec = di.get(_LEGACY_KEY)
    return spec if isinstance(spec, dict) else {}


def normalize(emission):
    """Rename the legacy fetch-block key IN PLACE on a parsed Layer-2 emission (a replay tape / an old cached
    emission), so every downstream reader sees only FETCH_KEY. Idempotent; a non-dict input passes through."""
    if isinstance(emission, dict):
        di = emission.get("data_instructions")
        if isinstance(di, dict) and _LEGACY_KEY in di:
            di.setdefault(FETCH_KEY, di.pop(_LEGACY_KEY))
    return emission
