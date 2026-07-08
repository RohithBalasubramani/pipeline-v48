"""layer2/swap/gate_force_renderable.py — the RENDERABILITY ENFORCER (user rule 1, per-card).

Layer 2 owns per-card enforcement: a SELECTED card that is UNRENDERABLE must not ship. card_feasibility.verdict IN
('drop','no_data') = UNRENDERABLE ('static_chrome' RENDERS its header/controls → renderable; 'render_real' is fine).
The swap pool (candidates.py) is ALREADY render_real-only, so ANY pool candidate is a renderable replacement.

DETERMINISTIC (not AI-dependent):
  - current card renderable ('render_real'/'static_chrome'/unknown) → no forced action (AI's own swap stands).
  - current card UNRENDERABLE + a render_real candidate exists → FORCE origin='swapped' to the closest candidate
    NOT already claimed by another slot (pool is ordered closest-size-first; `already_chosen` targets are skipped so
    two force-swapped slots never land on the same card [META-04]).
  - current card UNRENDERABLE + NO unclaimed candidate → KEEP it (honest, never fabricate) + flag forced_kept_unrenderable.

The unrenderable-verdict vocabulary is the DB-driven knob config.feasibility.UNRENDERABLE_VERDICTS
(cmd_catalog.app_config 'feasibility.unrenderable_verdicts'), NOT a hardcoded list here.
This runs AFTER the AI/gate decision in decide.gate, and OVERRIDES it only for the unrenderable case. [user rule 1]

SETTLE PRIORITY: the parallel runner settles target collisions HIGHEST-CONFIDENCE-FIRST (grounding.swap_settle). A
forced swap is MANDATORY (the loser of a revert would ship an unrenderable card) while an AI stylistic swap is
OPTIONAL (its KEEP still renders), so a forced decision is stamped confidence = FORCED_SWAP_CONFIDENCE — a DB knob
(cmd_catalog.app_config 'swap.forced_swap_confidence', default 2.0, deliberately > the AI's [0,1] range) — and the
AI's own value is preserved as `ai_confidence` for audit. Without the stamp a forced swap inherits the AI's KEEP
(confidence 0.0), sorts LAST in the settle, loses every collision, and the unrenderable card ships. [META-04 x rule 1]"""
from config.app_config import cfg
from config.feasibility import UNRENDERABLE_VERDICTS, DATALESS_ANSWERABILITY, FORCE_SWAP_ON_DATALESS

# settle-ordering priority for a FORCED swap — must exceed any AI confidence (the AI emits within [0,1]).
FORCED_SWAP_CONFIDENCE = cfg("swap.forced_swap_confidence", 2.0)


def is_unrenderable(verdict):
    """True iff this card cannot render at all. static_chrome renders (headers/controls) → renderable; render_real →
    renderable; a missing/unknown verdict is treated as renderable (honest: we only force on a KNOWN unrenderable)."""
    return verdict in UNRENDERABLE_VERDICTS


def is_dataless(answerability):
    """True iff the AI declared THIS card WHOLLY unfillable for THIS asset (answerability='none') AND the dataless-swap
    knob is on. This is the per-asset render-gate the static verdict cannot express: a catalog-renderable card whose
    every data leaf honest-blanks because the asset's schema has no matching column. [#1 dataless swap]"""
    return FORCE_SWAP_ON_DATALESS and answerability in DATALESS_ANSWERABILITY


def enforce(decision, *, verdict, pool, already_chosen=None, answerability=None):
    """Override `decision` when the CURRENT card cannot render REAL DATA — EITHER the static catalog verdict is
    unrenderable (config.feasibility.UNRENDERABLE_VERDICTS) OR the AI declared it dataless for THIS asset
    (answerability='none', the DATALESS-swap knob). Returns (decision, forced_kept_unrenderable:bool).

    `pool` = the slot's swap_candidates (list of {card_id,title,...}), already render_real-only + closest-first.
    `already_chosen` = final render ids claimed by other slots — skipped, so a forced swap never duplicates a card
    another slot already swapped to [META-04]. Non-mutating on the input; returns a fresh dict. When there is NO
    unclaimed candidate (a whole-page data dead-end) it KEEPS the card honestly (never fabricates)."""
    d = dict(decision or {})
    _dataless = is_dataless(answerability) and not is_unrenderable(verdict)   # pure per-asset dataless (not a catalog verdict)
    if not (is_unrenderable(verdict) or is_dataless(answerability)):
        return d, False                       # render_real / static_chrome / unknown + fillable → leave AI decision intact
    # UNRENDERABLE: a selected card that can't render must be force-swapped to a renderable alternative.
    taken = {int(x) for x in (already_chosen or set())}
    for tgt in pool or []:                    # closest-first (pool is ordered by size distance); skip claimed targets
        if int(tgt["card_id"]) in taken:
            continue
        d.update(action="swap", origin="swapped",
                 swap_to_id=int(tgt["card_id"]), swap_to_title=tgt.get("title"),
                 forced_renderable=True,
                 # a DATALESS-forced swap (the target is only CATALOG-render_real; its per-asset fillability is unknown
                 # until it re-emits) carries this marker so run_card can REVERT if the target is ALSO dataless — never
                 # swap one honest-empty card for another (a whole-page data dead-end keeps the honest original). [#1]
                 forced_dataless=_dataless,
                 # MANDATORY swap outranks every optional stylistic swap in the settle ordering [META-04 x rule 1]
                 ai_confidence=d.get("confidence"), confidence=FORCED_SWAP_CONFIDENCE)
        return d, False
    # No renderable replacement offered — KEEP honestly (never invent a card) and flag for the marker/reflect-loop.
    d.update(action="keep", origin="kept", swap_to_id=None, swap_to_title=None,
             forced_renderable=False, forced_kept_unrenderable=True)
    return d, True
