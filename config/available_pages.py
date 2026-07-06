"""config/available_pages.py — THE single provision to ADD/REMOVE routable pages (Layer 1a may route ONLY to these).

DB-DRIVEN: the active allow-list is read from cmd_catalog.routable_pages (one page_key per row) when present, so pages can
be enabled/disabled with a row edit and no code change. Resolution order:
    env V48_AVAILABLE_PAGES  >  cmd_catalog.routable_pages  >  the AVAILABLE_PAGES code-default below.
Never raises (a DB failure / missing table falls back to the code-default). Empty result -> NO restriction (all live
cmd_catalog pages routable). Seed: db/seed_routable_pages.sql.
"""
import os

# code-default fallback (used with the DB/table absent). The original 9 built pages + the 9 asset deep-tab pages.
AVAILABLE_PAGES = [
    # --- Panel Overview ---
    "panel-overview-shell/energy-distribution",   # Energy & Distribution
    "panel-overview-shell/energy-power",          # Energy & Power
    "panel-overview-shell/harmonics-pq",          # Harmonics & PQ
    "panel-overview-shell/real-time-monitoring",  # Real-Time Monitoring
    "panel-overview-shell/voltage-current",       # Voltage & Current
    # --- Equipment Detail (individual feeder / meter shell) ---
    "individual-feeder-meter-shell/voltage-current",      # Voltage & Current
    "individual-feeder-meter-shell/real-time-monitoring", # Real-Time Monitoring
    "individual-feeder-meter-shell/energy-power",         # Energy & Power
    "individual-feeder-meter-shell/power-quality",        # Power Quality
    # --- Asset deep-tab dashboards (data=neuract electrical where available, else honest-blank) ---
    "diesel-generator-asset-dashboard/engine-cooling",
    "diesel-generator-asset-dashboard/fuel-efficiency",
    "diesel-generator-asset-dashboard/operations-runtime",
    "diesel-generator-asset-dashboard/voltage-current",
    "transformer-asset-dashboard/tap-rtcc",
    "transformer-asset-dashboard/thermal-life",
    "ups-asset-dashboard/battery-autonomy",
    "ups-asset-dashboard/output-load-capacity",
    "ups-asset-dashboard/source-transfer",
]


def _db_pages():
    """Routable page_keys from cmd_catalog.routable_pages, or None if the table/DB is unavailable (never raises)."""
    try:
        from data.db_client import q
        rows = q("cmd_catalog", "SELECT page_key FROM routable_pages WHERE COALESCE(enabled, true)")
        keys = [r[0] for r in (rows or []) if r and r[0]]
        return keys or None
    except Exception:
        return None


def available_page_keys():
    """The active allow-list: env override > cmd_catalog.routable_pages > AVAILABLE_PAGES code-default."""
    env = os.environ.get("V48_AVAILABLE_PAGES", "").strip()
    if env:
        return [k.strip() for k in env.split(",") if k.strip()]
    return _db_pages() or list(AVAILABLE_PAGES)


def filter_to_available(specs):
    """Keep only page_specs whose page_key is available. Empty allow-list -> no filtering."""
    allow = set(available_page_keys())
    return specs if not allow else [s for s in specs if s["page_key"] in allow]
