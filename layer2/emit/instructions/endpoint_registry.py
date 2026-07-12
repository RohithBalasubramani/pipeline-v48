"""layer2/emit/instructions/endpoint_registry.py — the SINGLE SOURCE OF TRUTH for the LIVE fetch-endpoint names (the fetch spec's closed set). The baked
snapshot below is the CANONICAL endpoint truth: consumer_binding + the Layer-2 prompt read from here, so there is
one hand-verified endpoint list and no drift (that was the power-quality-history straggler's root cause).

Layout: per page the FIRST endpoint is the LIVE/now screen; the rest are its DATE-CAPABLE history variants."""

# canonical snapshot of the legacy-EMS WS endpoint names (live screen first, then its date-capable history variants).
_FALLBACK = [
    {"code": "overview", "eps": ["overview"]},
    {"code": "real-time-monitoring", "eps": ["real-time-monitoring"]},
    {"code": "energy-power", "eps": ["energy-power", "demand-profile", "load-anomalies", "energy-power-history"]},
    {"code": "energy-distribution", "eps": ["energy-distribution"]},
    {"code": "voltage-current", "eps": ["voltage-current", "voltage-history", "current-history"]},
    {"code": "power-quality", "eps": ["power-quality-summary"]},
]


PAGES = _FALLBACK

# ── the derived truth (everything downstream reads these) ─────────────────────────────────────────
PAGE_PRIMARY = {p["code"]: p["eps"][0] for p in PAGES}                # ems page code -> its LIVE/now endpoint
HISTORY_BY_DOMAIN = {p["eps"][0]: p["eps"][1:] for p in PAGES}        # live endpoint -> its date-capable history variants
LIVE_ENDPOINTS = {e for p in PAGES for e in p["eps"]}                 # every routable endpoint (live + history)
HISTORY_ENDPOINTS = {e for hist in HISTORY_BY_DOMAIN.values() for e in hist}   # the date-capable subset


if __name__ == "__main__":                                           # quick inspect: python -m layer2.emit.instructions.endpoint_registry
    import json
    print("LIVE_ENDPOINTS:", sorted(LIVE_ENDPOINTS))
    print("HISTORY_ENDPOINTS:", sorted(HISTORY_ENDPOINTS))
    print("HISTORY_BY_DOMAIN:", json.dumps(HISTORY_BY_DOMAIN, indent=1))
    print("PAGE_PRIMARY:", json.dumps(PAGE_PRIMARY, indent=1))
