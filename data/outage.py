"""data/outage.py — what a LIVE-DATA-SOURCE outage looks like (the ONE fingerprint home).

A connection/transport failure (tunnel :5433 down, psql could-not-connect, vLLM :8200 transport) is an OUTAGE — the
honest `data_unavailable` terminal. A logic error (bad SQL, missing table, KeyError) is deliberately NOT matched → it
stays a real error, never silently absorbed as "no data". Editable policy: extend the list, don't scatter string checks.

Home moved from run/degrade_gate.py (which re-exports for its callers) so the data-layer probes (data/value_probe.py)
can consume the split without importing upward into run/. [cycle-kill 2026-07-12]
"""

# Every fingerprint is a connection/transport failure, never a query or logic error.
_OUTAGE_FINGERPRINTS = (
    "connection refused",
    "could not connect",
    "connection to server",
    "no route to host",
    "network is unreachable",
    "connection timed out",
    "timed out",
    "timeout expired",                 # psycopg2 connect_timeout wording (pooled q() engine / pg_connect)
    "connection reset",
    "server closed the connection",
    "terminating connection",
    "the database system is",          # starting up / shutting down / in recovery
    "llm transport/parse failure",     # layer1a route fail-closed raise (vLLM :8200 outage / unparseable completion)
)


def is_outage_error(detail):
    """True iff an exception detail string looks like a LIVE-DATA-SOURCE outage (transport/connection failure), not a
    logic bug. Case-insensitive substring match against the editable fingerprint list."""
    if not detail:
        return False
    d = str(detail).lower()
    return any(fp in d for fp in _OUTAGE_FINGERPRINTS)


def is_outage_exc(e):
    """True iff an IN-PROCESS exception OBJECT is a LIVE-DATA-SOURCE outage. TYPE-first triage: connection/timeout
    types are outages by construction, no matter how novel the message wording; then falls back to the fingerprint
    match on str(e) for outages that surface as generic exception types (e.g. a RuntimeError wrapping psql stderr).

    Deliberately NOT a bare `isinstance(e, OSError)`: FileNotFoundError and PermissionError are OSError subclasses but
    are LOGIC bugs (missing file, bad perms) -- absorbing them as honest "no data" is exactly the silent fabrication
    this module forbids. Only the connection/timeout branches of the OSError tree count.

    Serialized boundaries (run/degrade_gate.py and anything reading a stored detail STRING) must keep using
    is_outage_error -- this triage only applies while the exception object is still in hand."""
    if isinstance(e, (ConnectionError, TimeoutError)):
        return True
    try:
        import psycopg2
        if isinstance(e, psycopg2.OperationalError):
            return True
    except ImportError:
        pass
    return is_outage_error(str(e))
