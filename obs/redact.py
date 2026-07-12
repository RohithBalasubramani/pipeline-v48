"""obs/redact.py — the ONE size-bounding concern: keep every logged inputs/outputs/prompt field structured and
queryable but never unbounded. bound() walks a JSON-ish structure preserving its SHAPE (dict keys, list heads,
scalar types) and truncates long strings / long lists with an explicit marker, so a stage event stays a few KB even
when a card payload or a 22K-token prompt rides through it. Deterministic, fail-open (worst case: repr snippet)."""
import json

_MARK = "…[truncated]"


def _cap_str(s, n):
    s = str(s)
    return s if len(s) <= n else s[: max(0, n - len(_MARK))] + _MARK


def bound(value, max_bytes=16384, _depth=0):
    """`value` size-bounded to ~max_bytes of JSON while keeping its shape. Scalars pass through; long strings are
    capped; dicts/lists are walked with a per-child budget and cut with an explicit truncation marker."""
    try:
        if value is None or isinstance(value, (bool, int, float)):
            return value
        if isinstance(value, str):
            return _cap_str(value, max_bytes)
        if _depth > 8:
            return _cap_str(repr(value), 200)
        if isinstance(value, dict):
            out, spent, budget = {}, 0, max(256, max_bytes)
            for i, (k, v) in enumerate(value.items()):
                if spent >= budget or i >= 64:
                    out["_truncated"] = f"{len(value) - i} more key(s) dropped"
                    break
                child = bound(v, max(128, (budget - spent) // 2), _depth + 1)
                out[str(k)[:120]] = child
                try:
                    spent += len(json.dumps(child, default=str))
                except Exception:
                    spent += 64
            return out
        if isinstance(value, (list, tuple)):
            out, spent, budget = [], 0, max(256, max_bytes)
            for i, v in enumerate(value):
                if spent >= budget or i >= 64:
                    out.append(f"{_MARK} {len(value) - i} more item(s)")
                    break
                child = bound(v, max(128, (budget - spent) // 2), _depth + 1)
                out.append(child)
                try:
                    spent += len(json.dumps(child, default=str))
                except Exception:
                    spent += 64
            return out
        return _cap_str(repr(value), 300)                      # sets, objects, DataFrames… — a labeled snippet
    except Exception:
        try:
            return _cap_str(repr(value), 200)
        except Exception:
            return "<unloggable>"


def digest(value):
    """A tiny structural summary for very large objects (type, size, top keys) — used where even a bounded copy is
    too much (e.g. a whole layer output already logged stage-by-stage)."""
    try:
        if isinstance(value, dict):
            return {"_type": "dict", "n": len(value), "keys": [str(k)[:60] for k in list(value)[:20]]}
        if isinstance(value, (list, tuple)):
            return {"_type": type(value).__name__, "n": len(value)}
        if isinstance(value, str):
            return {"_type": "str", "n": len(value), "head": value[:120]}
        return {"_type": type(value).__name__}
    except Exception:
        return {"_type": "unknown"}
