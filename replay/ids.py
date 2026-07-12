"""replay/ids.py — trace-ref resolution: accept a full trace_id, a legacy run_id (r_xxxxxxxxxx — resolves to the
NEWEST bundle whose manifest lists it), or 'last' (newest non-replay bundle). One concern: ref → bundle dir."""
import json
import os

TRACES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs", "traces")


def _manifest(d):
    try:
        with open(os.path.join(d, "manifest.json")) as f:
            return json.load(f)
    except Exception:
        return None


def bundles_newest_first():
    """[(dir, manifest)] for every readable bundle, newest started_at first."""
    out = []
    try:
        for name in os.listdir(TRACES_DIR):
            d = os.path.join(TRACES_DIR, name)
            m = _manifest(d)
            if m and m.get("trace_id"):
                out.append((d, m))
    except FileNotFoundError:
        pass
    out.sort(key=lambda dm: dm[1].get("ts_start") or 0, reverse=True)
    return out


def resolve(ref):
    """ref ('last' | trace_id | run_id) → (bundle_dir, manifest). Raises LookupError with what WAS available."""
    ref = (ref or "").strip()
    all_bundles = bundles_newest_first()
    if ref in ("", "last", "latest"):
        for d, m in all_bundles:
            if m.get("kind") != "replay":
                return d, m
        raise LookupError(f"no trace bundles under {TRACES_DIR}")
    direct = os.path.join(TRACES_DIR, ref)
    m = _manifest(direct)
    if m:
        return direct, m
    for d, m in all_bundles:                                   # run_id (or prefix of a trace_id)
        if ref in (m.get("run_ids") or []) or m["trace_id"].startswith(ref):
            return d, m
    raise LookupError(f"no bundle for {ref!r} under {TRACES_DIR} "
                      f"({len(all_bundles)} bundles exist — try `python3 -m replay.cli list`)")
