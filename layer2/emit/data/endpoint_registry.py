"""layer2/emit/data/endpoint_registry.py — the SINGLE SOURCE OF TRUTH for ems_backend WS endpoints, DERIVED at
import from ems_backend's own route table (`ems_backend/lt_panels/page_registry.py` `_PAGES`). No hand-maintained
endpoint lists anywhere else: consumer_binding + the Layer-2 prompt read from here, so when ems_backend adds/retires
an endpoint the pipeline follows automatically — no drift (that was the power-quality-history straggler's root cause).

Derivation: `_PAGES` = [{code, websockets:[{endpoint_path,...}]}]. Per page the FIRST websocket is the LIVE/now
screen; the rest are its DATE-CAPABLE history variants. We AST-parse the file (no Django import — page_registry
imports the dispatcher classes at module top, which would pull channels/Django). Falls back to a baked snapshot
(loudly) only if the file is missing/unparseable, so the pipeline never hard-breaks on an ems_backend move."""
import ast
import os
import sys

_PAGES_PATH = os.environ.get(
    "EMS_PAGE_REGISTRY",
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "ems_backend", "lt_panels", "page_registry.py"),
)

# baked snapshot — ONLY used if the live parse fails (logged). Regenerated truth lives in _PAGES; keep this as a net.
_FALLBACK = [
    {"code": "overview", "eps": ["overview"]},
    {"code": "real-time-monitoring", "eps": ["real-time-monitoring"]},
    {"code": "energy-power", "eps": ["energy-power", "demand-profile", "load-anomalies", "energy-power-history"]},
    {"code": "energy-distribution", "eps": ["energy-distribution"]},
    {"code": "voltage-current", "eps": ["voltage-current", "voltage-history", "current-history"]},
    {"code": "power-quality", "eps": ["power-quality-summary"]},
]


def _parse(path):
    """AST-extract [{code, eps:[endpoint_path,...]}] from the _PAGES literal — no import, no Django."""
    tree = ast.parse(open(path).read())
    pages = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "_PAGES" for t in node.targets)):
            continue
        for elt in node.value.elts:                                  # each page dict literal
            code, eps = None, []
            for k, v in zip(elt.keys, elt.values):
                key = getattr(k, "value", None)
                if key == "code" and isinstance(v, ast.Constant):
                    code = v.value
                elif key == "websockets" and isinstance(v, ast.List):
                    for ws in v.elts:                                # each websocket dict
                        for kk, vv in zip(ws.keys, ws.values):
                            if getattr(kk, "value", None) == "endpoint_path" and isinstance(vv, ast.Constant):
                                eps.append(vv.value)
            if code and eps:
                pages.append({"code": code, "eps": eps})
    if not pages:
        raise ValueError("no _PAGES entries parsed")
    return pages


def _load():
    try:
        return _parse(_PAGES_PATH), True
    except Exception as e:                                            # pragma: no cover - defensive
        sys.stderr.write(f"[endpoint_registry] WARN: could not parse {_PAGES_PATH} ({e}); using baked fallback "
                         f"(may be stale — re-check ems_backend retirements).\n")
        return _FALLBACK, False


PAGES, DERIVED_LIVE = _load()

# ── the derived truth (everything downstream reads these) ─────────────────────────────────────────
PAGE_PRIMARY = {p["code"]: p["eps"][0] for p in PAGES}                # ems page code -> its LIVE/now endpoint
HISTORY_BY_DOMAIN = {p["eps"][0]: p["eps"][1:] for p in PAGES}        # live endpoint -> its date-capable history variants
LIVE_ENDPOINTS = {e for p in PAGES for e in p["eps"]}                 # every routable endpoint (live + history)
HISTORY_ENDPOINTS = {e for hist in HISTORY_BY_DOMAIN.values() for e in hist}   # the date-capable subset


def is_live(endpoint):
    """True iff this endpoint is a real route in ems_backend right now. Anything else is retired/invented."""
    return endpoint in LIVE_ENDPOINTS


if __name__ == "__main__":                                           # quick inspect: python -m layer2.emit.data.endpoint_registry
    import json
    print("source:", _PAGES_PATH, "| live-parse:", DERIVED_LIVE)
    print("LIVE_ENDPOINTS:", sorted(LIVE_ENDPOINTS))
    print("HISTORY_ENDPOINTS:", sorted(HISTORY_ENDPOINTS))
    print("HISTORY_BY_DOMAIN:", json.dumps(HISTORY_BY_DOMAIN, indent=1))
    print("PAGE_PRIMARY:", json.dumps(PAGE_PRIMARY, indent=1))
