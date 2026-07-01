"""validate/leaf_classify.py — classify payload leaves DATA vs METADATA by TYPE only (non-AI).

DATA   = the measured values a worker fills: numbers, numeric arrays, time-series.
METADATA = design chrome the AI morphs: strings (labels/units/colors), booleans (flags).
The morph is per-LEAF (most content objects are 'mixed'), so we walk to the leaves and decide by type.
"""
from config.validation import SMALL_ARRAY_MAX

_BOOL = (bool,)


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, _BOOL)


def _all_numeric(lst):
    return bool(lst) and all(_is_num(x) for x in lst)


def classify(payload):
    """Return {data_leaves:[{path,kind}], metadata_leaves:int, demand:{scalars,arrays,series}}.
    kind in {scalar, array, series}."""
    data, meta = [], [0]

    def walk(o, path):
        if _is_num(o):
            data.append({"path": path, "kind": "scalar"}); return
        if isinstance(o, str) or isinstance(o, _BOOL) or o is None:
            meta[0] += 1; return
        if isinstance(o, list):
            if not o:
                meta[0] += 1; return
            if _all_numeric(o):
                data.append({"path": path, "kind": "array" if len(o) <= SMALL_ARRAY_MAX else "series"}); return
            if all(isinstance(x, dict) for x in o):
                # list of objects: a series if any object carries a numeric leaf.
                # If so, those per-object numeric leaves ARE the series — don't recurse (no double-count).
                if any(any(_is_num(v) for v in x.values()) for x in o):
                    data.append({"path": path, "kind": "series"}); return
                for i, x in enumerate(o[:3]):
                    walk(x, f"{path}[{i}]")
                return
            for i, x in enumerate(o[:3]):
                walk(x, f"{path}[{i}]")
            return
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, f"{path}.{k}" if path else k)
            return
        meta[0] += 1

    walk(payload, "")
    demand = {"scalars": sum(1 for d in data if d["kind"] == "scalar"),
              "arrays": sum(1 for d in data if d["kind"] == "array"),
              "series": sum(1 for d in data if d["kind"] == "series")}
    return {"data_leaves": data, "metadata_leaves": meta[0], "demand": demand}
