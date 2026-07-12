"""lib/blank.py — the ONE 'this leaf carries no real data' predicate + the em-dash sentinel.

The blank trio (None / '—' / '') is a cross-layer WIRE CONTRACT: the executor writes '—', the render verdict and the
FE read it. It was re-implemented 8× (gaps, roster_gaps, roster consts, scalar_mean_fill, scalar_tile_fill, xaxis,
render_verdict, host/enrich) with drifting list/[]-extensions — a ninth spelling that forgot '—' would mis-verdict
filled-vs-blank. The intentional per-module EXTENSIONS stay in their owners (tile-placeholder-0.0 in scalar_tile_fill,
the sankey DB-sentinel list in roster_modes_sankey) but build ON these.

Home moved from ems_exec/executor/blank.py (sys.modules-alias facade kept there) — grounding/validate/layer1b consume
this and the cross-package back-imports kept whole-package pairs circular. [cycle-kill 2026-07-12]
"""

#: The honest-blank display sentinel (METRIC_PLACEHOLDER) — what a blanked scalar leaf renders as.
DASH = "—"


def is_blank_scalar(v):
    """A scalar leaf that carries NO real data: None / '—' / ''."""
    return v is None or v == DASH or v == ""


def is_blank(v, *, empty_list=True, all_none_list=False):
    """Scalar blanks plus the list extensions the executor passes need:
      empty_list     — [] counts as blank (roster_gaps' `== []`).
      all_none_list  — an empty OR all-None list counts as blank (gaps' bucketed-read-over-dark-column case;
                       implies empty_list)."""
    if isinstance(v, list):
        if all_none_list:
            return not v or all(x is None for x in v)
        return empty_list and not v
    return is_blank_scalar(v)
