"""ems_exec/serve/run.py — the THIN host-facing entry into the per-card executor. NO WebSocket, NO daphne, NO frames.

The host calls one plain function per card:

    completed = run_card(exact_metadata, data_instructions, asset_table, window=None)

Given a card's L2 output (exact_metadata payload + data_instructions) and its resolved neuract table (+ optional date
window), it builds the executor ctx and returns the COMPLETED CMD_V2 payload — real where neuract has it, honest
None/'—' everywhere else, with every seed number stripped. The frontend renders this payload directly.

HONEST-GAP REASON CHANNEL: the executor classifies WHY each declared leaf blanked (column_absent / structurally_null /
derivation_unbound / no_nameplate / denorm_garbage — cmd_catalog.reason_template rows) and rides the records on the
completed payload under fill.GAPS_KEY. run_card passes them through UNCHANGED; the host pops them at the serve boundary
(fill.pop_gaps) into render.reason / render.gaps — telemetry, never a FE prop, never a render gate.

PER-CARD ONLY (no aggregation / fan-out). Never raises: any failure honest-blanks the payload rather than crashing the
page (the strip+complete still runs, so no seed leaks even on a fetch error). [ems_exec serve — plain function]
"""
from __future__ import annotations

from ems_exec.executor import fill as _fill
from ems_exec.executor.roster_modes_sankey import _prune_dark_edges as _prune_sankey


# ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
#  SANKEY SERVE-SAFETY SWEEP — the LAST word: never ship a null-endpoint sankey link (d3-sankey.find 'missing: —' crash)
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# The roster builder writes resolvable endpoints, but a later post-fill class killer can blank a link's source/target
# string when it byte-matches the default's structural stage id (a sankey endpoint IS topology identity, not a reading —
# but it collides with the narrative 'source' key the seed-leak class polices). An unresolved endpoint makes d3-sankey's
# computeNodeLinks() find() throw and crash the WHOLE card — NOT the per-leaf degrade contract. This sweep runs on the
# COMPLETED payload (after every fill pass) and drops any link whose source OR target no longer resolves to a real node,
# then omits any node left edge-less. Generic (zero card ids): walks the payload for ANY {nodes,links} sankey. Per-leaf
# degrade — the live member flows stay, only edges to dark/blanked endpoints vanish; d3-sankey only sees resolvable ids.

def _sweep_sankeys(node):
    """Recurse the completed payload; prune dark-endpoint links on every sankey ({nodes,links} dict). In place."""
    if isinstance(node, dict):
        if isinstance(node.get("links"), list) and "nodes" in node:
            _prune_sankey(node)
        for v in node.values():
            _sweep_sankeys(v)
    elif isinstance(node, list):
        for v in node:
            _sweep_sankeys(v)


def build_ctx(asset_table, *, db_link=None, window=None, mfm_id=None, asset_name=None, card_id=None):
    """The executor ctx: {asset_table, db_link?, window?, mfm_id?, asset_name?, card_id?}. window = (start,end) tuple
    or {start,end} dict, or None. mfm_id/asset_name/card_id activate the generic ROSTER interpreter seam (member-scope
    panel cards) inside fill() — harmless for single-meter cards (no roster instruction/recipe → no-op)."""
    ctx = {"asset_table": asset_table}
    if db_link is not None:
        ctx["db_link"] = db_link
    if window is not None:
        ctx["window"] = window
    if mfm_id is not None:
        ctx["mfm_id"] = mfm_id
    if asset_name is not None:
        ctx["asset_name"] = asset_name
    if card_id is not None:
        ctx["card_id"] = card_id
    return ctx


def run_card(exact_metadata, data_instructions, asset_table, *, db_link=None, window=None, default_payload=None,
             mfm_id=None, asset_name=None, card_id=None, shape_ref=None):
    """Fill ONE card's payload from neuract. Returns the completed CMD_V2 payload (never raises).

    Args:
      exact_metadata    : the card's payload skeleton (= the CMD_V2 component props) from Layer 2.
      data_instructions : the L2 data recipe; only `.fields[]` (+ optional `.window`) are consumed.
      asset_table       : the resolved neuract gic_* table_name (from 1b) — the ONE meter this card reads.
      db_link           : the asset's connection string (optional; passed through in ctx, unused per-card).
      window            : the card's (start,end) date window, or {start,end}, or None (= full logged range).
      default_payload   : the card's SEEDLESS default skeleton (from L2 `_default_payload`). Lets the executor GRAFT
                          the DATA-tier containers the byte-identity gate elided (roster/series arrays) so a declared
                          history series leaf is fillable. Optional; without it those elided leaves honest-blank.
      shape_ref         : the card's RAW harvested default payload — a SHAPE ORACLE for the post-fill passes (clock
                          axes, tick label types, normalized-series contracts). NEVER a value source (no seed can ride
                          it into the completed payload). Optional; without it those passes use weaker evidence.
      mfm_id/asset_name/card_id : the panel's registry id + display name + the card id — activate the generic ROSTER
                          interpreter (member-scope fan-out) when the card has a roster instruction / card_fill_recipe
                          row AND app_config roster.interpreter_enabled != 'off'. Optional; no-op for ordinary cards.

    On ANY error the payload is still stripped + shape-completed (so no seed number survives) and returned."""
    if mfm_id is None:
        # IDENTITY FALLBACK: the host's plain per-card call carries no mfm_id, but the emission itself does (the
        # consumer/binding it authored) — without it the roster interpreter seam is inert for every non-special card
        # (and for every /api/frame date re-fetch). Derive it from data_instructions; explicit kwarg always wins.
        di = data_instructions or {}
        consumer = di.get("consumer") if isinstance(di.get("consumer"), dict) else {}
        binding = di.get("binding") if isinstance(di.get("binding"), dict) else {}
        mfm_id = consumer.get("mfm_id") if consumer.get("mfm_id") is not None else binding.get("asset_id")
    ctx = build_ctx(asset_table, db_link=db_link, window=window, mfm_id=mfm_id, asset_name=asset_name,
                    card_id=card_id)
    try:
        out = _fill.fill(exact_metadata, data_instructions, ctx, default_payload=default_payload,
                         shape_ref=shape_ref)
    except Exception:
        # honest-degrade: still strip the seed + complete the shape so a fetch failure never leaks demo numbers
        try:
            out = _fill.fill(exact_metadata, {"fields": []}, ctx, default_payload=default_payload,
                             shape_ref=shape_ref)
        except Exception:
            out = exact_metadata or {}
    try:
        _sweep_sankeys(out)                                   # LAST word: never ship a null-endpoint sankey link
    except Exception:
        pass
    return out
