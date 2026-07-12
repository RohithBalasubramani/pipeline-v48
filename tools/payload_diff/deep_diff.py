"""tools/payload_diff/deep_diff.py — generic JSON deep-diff, tuned for live-data payloads. Every entry is classified
STRUCTURAL (keys/shape/type changed — what a code or emit change looks like) or VALUE (same shape, different scalar —
what live data always does), so a before/after code-change diff isn't drowned by moving numbers. Two VALUE subkinds
carry the honesty signal: 'emptied' (real → blank: the REAL→EMPTY regression headline) and 'filled' (blank → real).
Scalar series of equal length collapse to ONE summary entry. Numeric tolerance (relative) mutes jitter on request."""

EMPTY_SCALARS = (None, "", "—", "--", "-")


def is_empty(v):
    return v in EMPTY_SCALARS


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _within_tol(a, b, tol):
    if not tol or not (_num(a) and _num(b)):
        return False
    if a == b:
        return True
    base = max(abs(a), abs(b))
    return base > 0 and abs(a - b) / base <= tol


def _entry(path, kind, a, b, cls, sub=None, note=None):
    e = {"path": path, "kind": kind, "a": a, "b": b, "cls": cls}
    if sub:
        e["sub"] = sub
    if note:
        e["note"] = note
    return e


def _value_entry(path, a, b):
    sub = "emptied" if (not is_empty(a) and is_empty(b)) else ("filled" if (is_empty(a) and not is_empty(b)) else None)
    return _entry(path, "value", a, b, "value", sub=sub)


def _scalar_list(v):
    return isinstance(v, list) and all(not isinstance(x, (dict, list)) for x in v)


def _diff_scalar_lists(path, a, b, tol, out):
    if len(a) != len(b):
        out.append(_entry(path, "length", len(a), len(b), "structural", note="series length changed"))
    changed = emptied = filled = 0
    for x, y in zip(a, b):
        if x == y or _within_tol(x, y, tol):
            continue
        changed += 1
        if not is_empty(x) and is_empty(y):
            emptied += 1
        elif is_empty(x) and not is_empty(y):
            filled += 1
    if changed:
        sub = "emptied" if emptied and emptied >= filled and emptied == changed else None
        out.append(_entry(path, "series", f"{changed}/{min(len(a), len(b))} points differ",
                          {"changed": changed, "emptied": emptied, "filled": filled}, "value", sub=sub,
                          note="scalar series — per-point values elided"))


def diff(a, b, path="", tol=0.0, out=None, max_entries=400):
    """Diff two JSON values → list of entries (bounded by max_entries; a final 'truncated' entry marks overflow)."""
    if out is None:
        out = []
    if len(out) >= max_entries:
        return out
    if type(a) is not type(b) and not (_num(a) and _num(b)):
        # a cross-type change where one side is a blank scalar (None/''/'—') is a fill/empty transition, not a shape
        # change — 42 → '—' is the emptied-leaf headline, not a type error
        if is_empty(a) or is_empty(b):
            out.append(_value_entry(path, a, b))
        else:
            out.append(_entry(path, "type", type(a).__name__, type(b).__name__, "structural"))
        return out
    if isinstance(a, dict):
        for k in a.keys() | b.keys():
            if len(out) >= max_entries:
                out.append(_entry(path, "truncated", None, None, "structural", note=f"diff capped at {max_entries} entries"))
                return out
            p = f"{path}.{k}" if path else str(k)
            if k not in b:
                out.append(_entry(p, "removed", a[k], None, "structural"))
            elif k not in a:
                out.append(_entry(p, "added", None, b[k], "structural"))
            else:
                diff(a[k], b[k], p, tol, out, max_entries)
        return out
    if isinstance(a, list):
        if _scalar_list(a) and _scalar_list(b):
            _diff_scalar_lists(path, a, b, tol, out)
            return out
        if len(a) != len(b):
            out.append(_entry(path, "length", len(a), len(b), "structural"))
        for i in range(min(len(a), len(b))):
            if len(out) >= max_entries:
                out.append(_entry(path, "truncated", None, None, "structural", note=f"diff capped at {max_entries} entries"))
                return out
            diff(a[i], b[i], f"{path}[{i}]", tol, out, max_entries)
        return out
    if a != b and not _within_tol(a, b, tol):
        out.append(_value_entry(path, a, b))
    return out


def split(entries):
    """entries → {structural, value, emptied, filled} buckets (emptied/filled are also counted inside value)."""
    return {
        "structural": [e for e in entries if e["cls"] == "structural"],
        "value": [e for e in entries if e["cls"] == "value"],
        "emptied": [e for e in entries if e.get("sub") == "emptied"],
        "filled": [e for e in entries if e.get("sub") == "filled"],
    }
