"""payload_db/page_map.py — single source: Storybook (shell, page) -> cmd_catalog page_key. Edit here only. [atomic]"""

SHELL_TO_KEY = {
    "Panel Overview": "panel-overview-shell",
    "Equipment Detail": "individual-feeder-meter-shell",
}
PAGE_TO_SLUG = {
    "Energy & Distribution": "energy-distribution",
    "Energy & Power": "energy-power",
    "Harmonics & PQ": "harmonics-pq",
    "Real-Time Monitoring": "real-time-monitoring",
    "Voltage & Current": "voltage-current",
    "Power Quality": "power-quality",
}


def to_page_key(shell, page):
    s = SHELL_TO_KEY.get((shell or "").strip())
    p = PAGE_TO_SLUG.get((page or "").strip())
    return f"{s}/{p}" if s and p else None
