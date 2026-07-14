"""config/neuract_dsn.py — the ONE DB-driven accessor for the NEURACT live-data DSN the ems_exec executor reads.

Single concern: hand back the libpq connection string (+ its parts) for the per-device gic_* time-series tables. Every
knob is a cmd_catalog.app_config row (via config.app_config.cfg) with the current config/databases.py constant as the
CODE-DEFAULT fallback — so this behaves identically until a row exists, and a DB row overrides it with no code edit.

The DSN target (user-locked):
    postgresql://postgres@127.0.0.1:5433/target_version1?options=-csearch_path%3Dneuract

Nothing else in ems_exec hard-codes a host/port/db/schema — data/neuract.py imports THIS. [DB-driven; atomic]
"""
from urllib.parse import quote

from config.app_config import cfg
from config import databases as _db


def host():
    return cfg("neuract.host", _db.PG_HOST)


def port():
    return str(cfg("neuract.port", _db.PG_PORT))


def dbname():
    return cfg("neuract.db", _db.PG_DB)


def schema():
    return cfg("neuract.schema", _db.PG_SCHEMA)


def user():
    return cfg("neuract.user", _db.PG_USER)


def password():
    return cfg("neuract.password", _db.PG_PASSWORD)


def ts_col():
    """The timestamp column on every gic_* table (neuract = `timestamp_utc`, NOT `ts`)."""
    return cfg("neuract.ts_col", _db.DATA_TS_COL)


def ts_cast():
    """The cast suffix for time math (neuract stores ISO-8601 TEXT → '::timestamptz'; '' if already a timestamp type)."""
    return cfg("neuract.ts_cast", _db.DATA_TS_CAST)


def ts_index_fn():
    """The IMMUTABLE schema-qualified wrapper fn for the ts EXPRESSION INDEX [R3 / audit F1]. EMPTY by default → reads
    use the raw '::timestamptz' cast (current behavior, no index dependency). Set to 'ts_imm' AFTER
    db/create_neuract_ts_indexes.py has created neuract.ts_imm() + the per-table indexes: reads then order/filter on
    neuract.ts_imm(timestamp_utc), which MATCHES the index expression, turning the seq scans into index scans. The
    query expression and the index expression must be identical, so this is the paired code side of that DDL."""
    return str(cfg("neuract.ts_index_fn", "")).strip()


def ts_order_expr(col=None):
    """The knob-aware ORDER BY / time expression for a timestamp column — ONE source of truth for every read that must
    hit the ts EXPRESSION INDEX [R3 / audit F1]. `col` is a bare column name (default: the configured ts_col); it is
    double-quoted here. When neuract.ts_index_fn is set (e.g. 'ts_imm') returns the schema-qualified IMMUTABLE wrapper
    `neuract.ts_imm("timestamp_utc")` so the expression MATCHES the index and the read is an index scan; otherwise the
    raw cast `"timestamp_utc"::timestamptz`. The two are byte-identical in ordering (ts_imm(t) IS `SELECT t::timestamptz`),
    so switching is a pure speed change — proved over the full registry (docs/latency_audit_20260714/prove_probe_neutral.py:
    147 tables, 0 mismatches). This is the shared twin of ems_exec/data/neuract._tsexpr() for the q()-path probes
    (value_probe, col_dict, validate) that don't go through the ems_exec neuract door."""
    q = '"%s"' % (col or ts_col())
    fn = ts_index_fn()
    if fn:
        return f'{schema()}.{fn}({q})'
    return f'{q}{ts_cast()}'


def dsn():
    """The full libpq DSN string (search_path pinned to the neuract schema). This is the user-locked target by default."""
    opts = quote(f"-csearch_path={schema()}", safe="")
    pw = password()
    auth = f"{user()}:{pw}" if pw else user()
    return f"postgresql://{auth}@{host()}:{port()}/{dbname()}?options={opts}"


def conn_kwargs():
    """psycopg2.connect(**kwargs) for the neuract DB — used by BOTH pooled doors (ems_exec/data/neuract.py and
    data/neuract_live/_db.py), so a knob edited here moves both.

    HALF-DEAD-TUNNEL GUARD [2026-07-12]: the neuract DB rides an SSH tunnel on :5433 that is documented to flap
    (config/databases.py). Without these, a half-open socket (TCP established, forwarding dead) parks a connect for the
    OS TCP timeout (~2 min) and a mid-query stall for the kernel retransmission timeout (~15 min) — HOLDING the pooled
    connection's lock so EVERY other executor thread wedges behind it. `connect_timeout` + TCP keepalives turn that into
    a fast failure the honest-degrade path converts to `data_unavailable` in seconds. These only fire on a genuinely
    dead socket, so the healthy path is byte-identical. All DB-knob-driven with safe code defaults.

    `statement_timeout` is opt-in (code default 0 = unlimited, i.e. current behavior) because a too-tight value would
    blank slow-but-working queries; set `neuract.statement_timeout_ms` once the ::timestamptz index work (audit F1/P3)
    lands so no legitimate read is near the limit."""
    opts = f"-c search_path={schema()}"
    st_ms = int(cfg("neuract.statement_timeout_ms", 0))
    if st_ms > 0:
        opts += f" -c statement_timeout={st_ms}"
    return {
        "dbname": dbname(),
        "user": user(),
        "password": (password() or None),
        "host": host(),
        "port": port(),
        "options": opts,
        "connect_timeout": int(cfg("neuract.connect_timeout_s", 5)),
        "keepalives": 1,
        "keepalives_idle": int(cfg("neuract.keepalives_idle_s", 10)),
        "keepalives_interval": int(cfg("neuract.keepalives_interval_s", 5)),
        "keepalives_count": int(cfg("neuract.keepalives_count", 3)),
    }
