"""layer2/emit/instructions/consumer_binding/screen_map.py — map a FE page_key / a card's backend_strategy to its live
screen/endpoint. Two pure lookups over the DERIVED endpoint truth (endpoint_registry): the LIVE page endpoint
(`page_endpoint`, back-compat page-level live_frame) and the card's canonical live screen (`canonical_screen`, shown to
the AI as a hint). ENDPOINT TRUTH is never hand-maintained here — it comes from endpoint_registry, which parses
the endpoint_registry route table (legacy-EMS-derived), so this follows it automatically (no drift)."""
from layer2.emit.instructions.endpoint_registry import PAGE_PRIMARY
from config.app_config import cfg

def _page_tail_alias():
    """FRONTEND page-tail → endpoint page CODE, ONLY where the names differ (a frontend naming convention, NOT endpoint
    truth): the Harmonics/PQ tab is `harmonics-pq` in the FE but the ems page code is `power-quality`; the SLD tab is
    `overview-sld-3d` → the `overview` screen. Every other tail already equals its ems page code. [config → DB]
    Read per call (an import-time read pinned the boot value for process life)."""
    return cfg("routes.page_tail_alias", {"harmonics-pq": "power-quality", "overview-sld-3d": "overview"})


def page_endpoint(page_key):
    """FE page_key → its LIVE fetch endpoint (derived from PAGE_PRIMARY). Back-compat page-level live_frame."""
    tail = (page_key or "").rsplit("/", 1)[-1]
    return PAGE_PRIMARY.get(_page_tail_alias().get(tail, tail), tail)


def canonical_screen(backend_strategy):
    """`consumers/<dir>/<panel>.py` → `<dir-hyphenated>` (real_time_monitoring → real-time-monitoring). The card's
    canonical legacy-EMS screen, SHOWN TO THE AI as a hint (the AI still decides the endpoint, incl. a history variant)."""
    if not backend_strategy:
        return None
    parts = str(backend_strategy).strip("/").split("/")
    try:
        return parts[parts.index("consumers") + 1].replace("_", "-")
    except (ValueError, IndexError):
        return None
