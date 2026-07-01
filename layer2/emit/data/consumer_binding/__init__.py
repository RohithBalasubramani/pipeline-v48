"""layer2/emit/data/consumer_binding/ — assemble the consumer-driving params the DATA-fill helper passes to V48's
`ems_backend/` WS dispatcher (`ws/mfm/<mfm_id>/<endpoint>/`). The AI (Layer 2) AUTHORS the fetch spec — endpoint
(live vs date-capable history), window/range/sampling, metrics, selection. This package only ASSEMBLES the AI's spec
with the one non-AI key, `mfm_id` (1b's resolved asset = the WS path key). NO deterministic fallbacks/guesses.
[design-notes 'Layer 2 DATA source — reuse ems_backend', findings/ems_backend_hardcoding.md]

BARREL — this package REPLACES the old `consumer_binding.py` module. Every public name the old module exposed is
re-exported here so `from layer2.emit.data.consumer_binding import build, page_endpoint, canonical_screen,
domain_endpoints, RETIRED_ENDPOINTS, PAGE_PRIMARY, HISTORY_BY_DOMAIN, HISTORY_ENDPOINTS` keeps working unchanged.

Single-purpose modules:
  screen_map  — page_endpoint, canonical_screen  (FE/backend_strategy → ems screen)
  domain      — domain_endpoints, RETIRED_ENDPOINTS  (a card's valid endpoint set + retired-name prompt emphasis)
  builder     — build  (assemble the AI fetch spec + mfm_id into the dispatcher params)

ENDPOINT TRUTH is DERIVED — never hand-maintained here. Which endpoints exist (live screens, their date-capable history
variants, the page→endpoint map) is read from `endpoint_registry`, which parses ems_backend's OWN `_PAGES` route table.
`PAGE_PRIMARY`, `HISTORY_BY_DOMAIN`, `HISTORY_ENDPOINTS` are re-exported from there for back-compat (the old module
re-exported them)."""
# re-exported endpoint truth (the old module re-exported these — kept for back-compat)
from layer2.emit.data.endpoint_registry import PAGE_PRIMARY, HISTORY_BY_DOMAIN, HISTORY_ENDPOINTS  # noqa: F401

from layer2.emit.data.consumer_binding.screen_map import page_endpoint, canonical_screen
from layer2.emit.data.consumer_binding.domain import domain_endpoints, RETIRED_ENDPOINTS
from layer2.emit.data.consumer_binding.builder import build

__all__ = [
    "page_endpoint",
    "canonical_screen",
    "domain_endpoints",
    "RETIRED_ENDPOINTS",
    "build",
    "PAGE_PRIMARY",
    "HISTORY_BY_DOMAIN",
    "HISTORY_ENDPOINTS",
]
