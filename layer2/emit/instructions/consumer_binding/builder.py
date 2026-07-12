"""layer2/emit/instructions/consumer_binding/builder.py — assemble the consumer-driving params the DATA-fill helper passes to
the legacy EMS WS dispatcher (`ws/mfm/<mfm_id>/<endpoint>/`). The AI (Layer 2) AUTHORS the fetch spec — endpoint
(live vs date-capable history), window/range/sampling, metrics, selection. `build()` only ASSEMBLES the AI's spec with
the one non-AI key, `mfm_id` (1b's resolved asset = the WS path key). NO deterministic fallbacks/guesses.
[design-notes 'Layer 2 DATA source'; docs/findings history]"""
from layer2.emit.instructions.endpoint_registry import HISTORY_ENDPOINTS


def build(catalog_row, asset, page_key, window=None, ai_spec=None):
    """The params the legacy EMS dispatcher needed to render this card's DATA. The AI (Layer 2) authors the WHOLE fetch
    spec — endpoint (live vs date-capable history), window/range/sampling, metrics, selection — that is Layer 2's job.
    `mfm_id` is NOT the AI's call: it is 1b's resolved asset (the WS path key). A non-data card simply has no legacy-EMS
    block (endpoint None). The helper drives `ws/mfm/<mfm_id>/<endpoint>/` with these. NO deterministic endpoint/window
    fallbacks — if the AI didn't spec a data card, that is an honest logged gap, never a guessed default."""
    asset = asset or {}
    ai = ai_spec or {}
    endpoint = ai.get("endpoint")                              # ★ AI's call (Layer 2), used AS-IS; None for a non-data card.
    # NO deterministic domain-snap / fallback. The AI OWNS the endpoint — the prompt shows it this card's natural-domain
    # endpoints (domain_endpoints) as a STRONG preference, and an off-domain pick is fixed in the PROMPT, never overridden
    # here. (user: no fallbacks anywhere; the whole purpose of Layer 2 is that the AI decides.)
    return {
        "mfm_id": asset.get("mfm_id"),                         # 1b's RESOLVED ASSET (not a Layer-2 call) — the WS path key
        "endpoint": endpoint,                                  # ★ AI: the consumer screen (live vs history)
        "is_history": endpoint in HISTORY_ENDPOINTS,           # date-capable? (a fact about the endpoint → query format)
        "backend_strategy": catalog_row.get("backend_strategy"),  # reference consumer file; dispatcher picks class-correct
        "resolver_scope": catalog_row.get("resolver_scope"),  # meter | panel | asset — drives single vs aggregate fill
        # LIVE trailing-window (real-time endpoints):
        "window_seconds": ai.get("window_seconds"),           # ★ AI: how far back the live history reaches
        "interval_seconds": ai.get("interval_seconds"),       # ★ AI: sampling cadence
        "sample_count": ai.get("sample_count"),               # ★ AI: history depth (number of samples)
        # DATE-WINDOW (history endpoints — the host OVERRIDES range/start/end with the user's date pick at fetch):
        "range": ai.get("range"),                             # ★ AI: today|yesterday|last-7-days|this-month|custom-range
        "start": ai.get("start"),                             # ★ AI: ISO/bare-date when range=custom-range
        "end": ai.get("end"),
        "sampling": ai.get("sampling"),                       # ★ AI: hourly|2hour|shift|day|week
        "metrics": ai.get("metrics"),                         # ★ AI: which metrics the card's history needs
        "selection": ai.get("selection"),                     # ★ AI: initial selected entity/section/bucket
    }
