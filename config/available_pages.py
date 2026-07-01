"""config/available_pages.py — THE single provision to ADD/REMOVE routable pages.

Layer 1a may route ONLY to the page_keys listed here. Add a line to enable a page,
remove/comment one to disable it — no layer code changes needed.

- Empty list  -> NO restriction (all live cmd_catalog pages are routable).
- Env override -> V48_AVAILABLE_PAGES="page-key-1,page-key-2,..." wins over the list below.
"""
import os

# Currently built/available in the frontend (9). Add/remove as pages ship.
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
]


def available_page_keys():
    """The active allow-list (env override > AVAILABLE_PAGES)."""
    env = os.environ.get("V48_AVAILABLE_PAGES", "").strip()
    if env:
        return [k.strip() for k in env.split(",") if k.strip()]
    return list(AVAILABLE_PAGES)


def filter_to_available(specs):
    """Keep only page_specs whose page_key is available. Empty allow-list -> no filtering."""
    allow = set(available_page_keys())
    return specs if not allow else [s for s in specs if s["page_key"] in allow]
