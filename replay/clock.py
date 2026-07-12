"""replay/clock.py — the ONE behavior-affecting wall-clock seam. Normal runs: now(tz) == datetime.now(tz), byte-
identical. During replay the engine freezes it to the ORIGINAL request's wall-clock instant, so the five now()-
dependent behaviors reproduce: the L2 window anchor fallback (layer2/build._window_anchor), the asset-facts age
string that lands in L2 PROMPT BYTES (layer2/emit/asset_facts), the executor freshness badge
(ems_exec/executor/freshness), and the host preset/range resolvers (host/server._window_from_preset,
host/exec_cards._resolve_range_span). Fail-open: freeze state can never break a live request."""
import datetime as _dt

_FROZEN = None                                                 # aware datetime (UTC) or None = live


def freeze(instant):
    """Pin now() to `instant` (aware datetime or ISO string). Engine-only."""
    global _FROZEN
    if isinstance(instant, str):
        instant = _dt.datetime.fromisoformat(instant)
    if instant is not None and instant.tzinfo is None:
        instant = instant.replace(tzinfo=_dt.timezone.utc)
    _FROZEN = instant


def unfreeze():
    global _FROZEN
    _FROZEN = None


def frozen():
    return _FROZEN is not None


def now(tz=None):
    """datetime.now(tz) — or the frozen instant (converted to tz) during replay."""
    if _FROZEN is not None:
        try:
            return _FROZEN.astimezone(tz) if tz is not None else _FROZEN.replace(tzinfo=None)
        except Exception:
            pass
    return _dt.datetime.now(tz)
