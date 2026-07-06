"""layer1b/resolve/empty_fallback.py — the honest no-match fallback (logged). [#17, RN-06]

Two distinct empty states the resolver can land in:
  · pure-metric prompt (no asset, no class named at all)          → how='empty', no candidates (Layer 2 runs metric-only).
  · asset WAS implied but nothing matched / AI returned nothing   → how='ambiguous' over the browse-all registry, so the
                                                                     picker opens on the full list instead of a dead end.
This file owns the SECOND: it logs the no-match (stderr, machine-readable) and returns the browse-all candidate outcome,
device-identity de-duplicated + populated-preferred, so the user always has a real list to pick from. The reason string
is read from the editable cmd_catalog.reason_template channel (no hardcoded sentence in logic). [RN-06]
"""
import sys

from layer1b.resolve.asset_candidates import asset_candidates
from layer1b.resolve.ambiguous_candidates import ambiguous_candidates
from config.reason_templates import reason


def empty_fallback(prompt, prefer_data=True, rows=None):
    """The logged no-match outcome: browse-all registry as an ambiguous candidate list. `prefer_data` restricts the
    browse list to data-bearing meters first (so the picker leads with renderable assets), falling back to the full
    registry when none are data-bearing. `rows` (optional) overrides the browse list — asset_resolve passes the
    CLASS-NARROWED rows when a class prior exists, so a 'dg ...' prompt browses DG meters, not the whole plant.
    Logs the machine-readable no-match reason to stderr."""
    cands = asset_candidates()
    if rows is None:
        rows = [c for c in cands if c[6]] if prefer_data else cands
        rows = rows or cands
    why = reason("no_data", asset=(str(prompt)[:60] if prompt else "your query"))
    sys.stderr.write(f"[empty_fallback] no confident asset match — browse-all registry offered "
                     f"({len(rows)} candidates). prompt={prompt!r} reason={why!r}\n")
    return ambiguous_candidates(rows, cands)
