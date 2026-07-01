"""run/degrade_gate.py — the INFRA-OUTAGE honest terminal (single purpose).

Render-guarantee root-cause fix: when Layer 1a/1b raises because a LIVE data source is unreachable (the DATA/registry
tunnel :5433 down, a psql connection refused / could-not-connect, a timeout), the pipeline must NOT silently emit
verdict-less 1a card shells while claiming ok=True. That is a hole in the "0 crashes → honest-blank + machine reason"
invariant: a whole-page infra outage is just the extreme case of "no data", and the contract says every card renders
OR honest-blanks with a machine-readable reason — never a silent dead-end.

This module is the ONE place that (a) recognises a layer error as an INFRA/DB outage (not a logic bug) and (b) turns it
into the honest `data_unavailable` gate + a DB-driven reason sentence (cmd_catalog.reason_template, via
config.reason_templates — NO hardcoded reason string here). The FE already treats a page-level gate as an honest
terminal (App.tsx), so setting it makes the page show an honest notice instead of dark verdict-less cards.

DB-driven / atomic: the human sentence is an editable `reason_template` row (cause='data_unavailable'); the outage
FINGERPRINTS are an editable list here (the only policy this file owns) — extend the list, don't scatter string checks.
"""

# The substrings that identify a LIVE-DATA-SOURCE outage inside a layer's exception text. Editable policy (the single
# home for "what a DB/tunnel outage looks like"); every fingerprint is a connection/transport failure, never a query
# or logic error. A logic error (bad SQL, missing table, KeyError) is deliberately NOT matched → it stays a real error
# surfaced in out["errors"], not silently absorbed as "no data".
_OUTAGE_FINGERPRINTS = (
    "connection refused",
    "could not connect",
    "connection to server",
    "no route to host",
    "network is unreachable",
    "connection timed out",
    "timed out",
    "connection reset",
    "server closed the connection",
    "terminating connection",
    "the database system is",          # starting up / shutting down / in recovery
)

# The layers whose failure means "we never even reached ground truth" → the page is a data_unavailable terminal.
_INFRA_LAYERS = ("layer1a", "layer1b")


def is_outage_error(detail):
    """True iff an exception detail string looks like a LIVE-DATA-SOURCE outage (transport/connection failure), not a
    logic bug. Case-insensitive substring match against the editable fingerprint list."""
    if not detail:
        return False
    d = str(detail).lower()
    return any(fp in d for fp in _OUTAGE_FINGERPRINTS)


def apply(out):
    """Inspect a run_pipeline `out` AFTER 1a/1b settle. If an INFRA layer failed with an outage-shaped error, mark the
    page as the honest `data_unavailable` terminal with a machine-readable reason (from the DB reason_template) so the
    FE shows an honest notice instead of dark verdict-less cards. Returns the (possibly-annotated) `out` unchanged in
    the common case. Never raises — a reason-channel hiccup must not sink the page."""
    errors = out.get("errors") or {}
    for layer in _INFRA_LAYERS:
        detail = errors.get(layer)
        if detail and is_outage_error(detail):
            out["data_unavailable"] = True
            out["degrade"] = {"kind": "data_unavailable", "layer": layer, "detail": str(detail)[:400]}
            try:
                from config.reason_templates import reason
                out["degrade"]["reason"] = reason("data_unavailable", layer=layer, detail=str(detail)[:200])
            except Exception:
                # reason channel unavailable (e.g. catalog also down) — keep the machine cause key, never crash
                out["degrade"]["reason"] = "data_unavailable"
            return out
    return out
