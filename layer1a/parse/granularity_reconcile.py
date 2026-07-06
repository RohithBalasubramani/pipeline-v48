"""layer1a/parse/granularity_reconcile.py — POST-RESOLUTION granularity safety-net (single purpose).

THE DEFECT it fixes [batch 3, pages 07/07-family]: Layer 1a routes the SHELL from the prompt TEXT, in PARALLEL with
Layer 1b's asset resolution — so at route time it does NOT know whether the resolved asset is a single meter or an
aggregate panel. A generic electrical prompt naming a single-meter device ('real time monitoring for GIC-01-N3-UPS-01',
has_feeders=False) can land on a `Panel overview shell` page whose panel-AGGREGATE cards then fan out to 0 members
(wrong-asset topology bleed). The mirror also breaks: a PANEL subject on the single-meter shell has no per-meter story.

The router prompt already tries to route by SUBJECT GRANULARITY, but it is blind to `has_feeders`. This module is the
deterministic reconciliation that runs AFTER both layers settle and BEFORE Layer 2: if the routed page's SHELL
granularity contradicts the resolved asset's `has_feeders`, it returns the MIRROR page in the correct-granularity shell
(same analytical tail), so the harness can re-route 1a to a page whose cards this asset can actually populate.

DB-DRIVEN / generic — no card ids, no per-asset vocab:
  · the shell→granularity pairing is a cmd_catalog.app_config row (`routes.granularity_shells`, json) with the code
    default below; edit the row to add/rename a shell pair.
  · the analytical-tail equivalence (harmonics-pq ≡ power-quality) reuses the EXISTING `routes.page_tail_alias` row.
Only fires on a CONFIDENT mismatch (both the shell is a known-granularity shell AND has_feeders is decisive); anything
ambiguous is left untouched (the router's choice stands). Returns None when there is nothing to reconcile.
"""
from config.app_config import cfg

# code-default shell→granularity pairing (live value = app_config 'routes.granularity_shells'). Each pair declares the
# PANEL-granularity shell (aggregate, has_feeders=True) and its MIRROR SINGLE-METER shell (has_feeders=False). Shell
# labels are the page_specs.shell strings verbatim, so the two vocabularies stay aligned.
_GRANULARITY_SHELLS = {
    "panel": ["Panel overview shell"],
    "meter": ["Individual feeder / meter shell"],
}


def _shells():
    v = cfg("routes.granularity_shells", _GRANULARITY_SHELLS)
    return v if isinstance(v, dict) and v.get("panel") and v.get("meter") else _GRANULARITY_SHELLS


from config.asset_granularity import belongs_on_panel as _belongs_on_panel   # shared DB-driven class policy


def _tail_aliases():
    """Bidirectional tail-equivalence map from the EXISTING routes.page_tail_alias row (e.g. harmonics-pq↔power-quality).
    A tail is equivalent to itself plus any alias in either direction."""
    m = cfg("routes.page_tail_alias", {}) or {}
    out = {}
    if isinstance(m, dict):
        for a, b in m.items():
            out.setdefault(str(a), set()).add(str(b))
            out.setdefault(str(b), set()).add(str(a))
    return out


def _tail(page_key):
    return str(page_key or "").rsplit("/", 1)[-1]


def _equiv_tails(tail):
    aliases = _tail_aliases()
    eq = {tail} | aliases.get(tail, set())
    return eq


def target_shell(routed_shell, has_feeders, asset_class=None):
    """The granularity group that SHOULD serve this asset (the TARGET to re-route TO), given the routed page's shell,
    the asset's has_feeders, and its CLASS. Returns (want_group, mismatch) — want_group ∈ {'panel','meter'} is the
    CORRECT-granularity group (may equal the routed group when already correct), mismatch True iff the routed shell is
    the WRONG granularity. Returns (None, False) when the routed shell is not a known granularity shell.
      · a PANEL-class asset → an aggregate panel → the 'panel' group is correct.
      · everything else (Transformer/DG/UPS/single meter) → the 'meter' group is correct, EVEN with downstream feeders."""
    shells = _shells()
    panel_shells = set(shells.get("panel", []))
    meter_shells = set(shells.get("meter", []))
    belongs = _belongs_on_panel(has_feeders, asset_class)
    if routed_shell in panel_shells:
        # correct only when the asset truly belongs on the panel-aggregate shell; else mirror to the meter shell.
        return ("panel" if belongs else "meter", not belongs)
    if routed_shell in meter_shells:
        # a single asset on the meter shell is correct; only a genuine PANEL-class aggregate should mirror to panel.
        return ("panel" if belongs else "meter", belongs)
    return (None, False)


def mirror_page_key(routed_page_key, routed_shell, has_feeders, live_specs, asset_class=None):
    """The correct-granularity mirror page_key, or None when no reconciliation is needed / possible.

    routed_page_key/routed_shell = the 1a route; has_feeders = the resolved asset (1b); live_specs = read_page_specs()
    rows (each {page_key, shell, ...}). Only returns a page that (a) lives in the target-granularity shell and (b) shares
    the routed page's analytical tail (via the tail-alias). None when the granularity already matches, the routed shell
    isn't a known granularity shell, has_feeders is None (undecidable), or no mirror page exists."""
    if has_feeders is None and not asset_class:
        return None
    want, mismatch = target_shell(routed_shell, has_feeders, asset_class)
    if not want or not mismatch:
        return None
    shells = _shells()
    target_shells = set(shells.get(want, []))
    eq = _equiv_tails(_tail(routed_page_key))
    for s in live_specs:
        if s.get("shell") in target_shells and _tail(s.get("page_key")) in eq:
            if s.get("page_key") != routed_page_key:
                return s.get("page_key")
    return None
