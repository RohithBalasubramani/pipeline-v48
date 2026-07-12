"""layer2/emit/instructions/consumer_binding/domain.py — a card's VALID endpoint set (its canonical live screen + that domain's
date-capable history variants) shown to the AI as a STRONG preference, plus the RETIRED-names prompt emphasis. The AI
must pick ONE of `domain_endpoints` (live for a now card, a history variant for a trend card); RETIRED_ENDPOINTS are
folded-away legacy names the AI must never emit (build() does not snap — the prompt forbids them). [config → DB]"""
from layer2.emit.instructions.endpoint_registry import HISTORY_BY_DOMAIN
from config.app_config import cfg

from layer2.emit.instructions.consumer_binding.screen_map import canonical_screen

_HISTORY_BY_DOMAIN = HISTORY_BY_DOMAIN                                # alias for domain_endpoints() below

def _retired_endpoints():
    """RETIRED legacy names (folded into power-quality-summary) — kept ONLY as PROMPT EMPHASIS (the AI confuses these with
    real endpoints from its training). The ACTUAL rule is "must be a LIVE endpoint" (endpoint_registry.LIVE_ENDPOINTS);
    build() does not snap (the AI owns the endpoint), so the prompt forbids these names + shows the live set as closed.
    [config → DB] Read per call (an import-time read pinned the boot value for process life)."""
    return set(cfg("routes.retired_endpoints", ["power-quality-history", "distortion-harmonics", "harmonics-pq", "power-quality"]))


def __getattr__(name):
    if name == "RETIRED_ENDPOINTS":     # kept as a module attr (the package barrel re-exports it) — re-read per access
        return _retired_endpoints()
    raise AttributeError(f"module 'layer2.emit.instructions.consumer_binding.domain' has no attribute {name!r}")


def domain_endpoints(backend_strategy):
    """The card's VALID endpoints = its canonical live screen + that domain's date-capable history variants. The AI must
    pick ONE of these (live for a now card, a history variant for a trend card) — anything else is off-domain & wrong."""
    live = canonical_screen(backend_strategy)
    return {"live": live, "history": _HISTORY_BY_DOMAIN.get(live, [])}
