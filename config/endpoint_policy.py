"""config/endpoint_policy.py — thin reader over cmd_catalog.endpoint_policy (page × scope → endpoint + shape).

For a page and the resolved asset scope (single_asset / panel_aggregate), which ems_backend endpoint to open, the frame
SHAPE the card's fill mapper reads (queue | buckets | widgets), and whether it is a date-navigable history endpoint.
Feeds the endpoint/shape pre-validation + the frame_shape_mismatch detection. NO hardcoded endpoint/shape map in logic
code — READS this table (which is itself seeded from endpoint_registry, the single source of truth). [ER-1/2/4/5/7/8]
"""
from data.db_client import q

_COLS = ["page_key", "resolver_scope", "endpoint", "expected_shape", "is_history"]


def policy(page_key, resolver_scope):
    """{endpoint, expected_shape, is_history} for a (page, scope), or None if unconfigured."""
    rows = q("cmd_catalog",
             "SELECT endpoint, expected_shape, is_history FROM endpoint_policy "
             f"WHERE page_key='{_esc(page_key)}' AND resolver_scope='{_esc(resolver_scope)}'")
    if not rows:
        return None
    ep, shape, is_hist = rows[0]
    return {"endpoint": ep, "expected_shape": shape, "is_history": _bool(is_hist)}


def endpoint(page_key, resolver_scope):
    p = policy(page_key, resolver_scope)
    return p["endpoint"] if p else None


def expected_shape(page_key, resolver_scope):
    p = policy(page_key, resolver_scope)
    return p["expected_shape"] if p else None


def is_history(page_key, resolver_scope):
    p = policy(page_key, resolver_scope)
    return bool(p and p["is_history"])


def all_policies():
    rows = q("cmd_catalog", "SELECT " + ",".join(_COLS) + " FROM endpoint_policy ORDER BY page_key, resolver_scope")
    return [{"page_key": r[0], "resolver_scope": r[1], "endpoint": r[2],
             "expected_shape": r[3], "is_history": _bool(r[4])} for r in rows]


def _bool(x):
    return str(x).strip().lower() in ("t", "true", "1", "yes")


def _esc(s):
    return str(s).replace("'", "''")
