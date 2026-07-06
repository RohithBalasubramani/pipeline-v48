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


def dsn():
    """The full libpq DSN string (search_path pinned to the neuract schema). This is the user-locked target by default."""
    opts = quote(f"-csearch_path={schema()}", safe="")
    pw = password()
    auth = f"{user()}:{pw}" if pw else user()
    return f"postgresql://{auth}@{host()}:{port()}/{dbname()}?options={opts}"


def conn_kwargs():
    """psycopg2.connect(**kwargs) for the neuract DB — used by data/neuract.py's pool (search_path via options)."""
    return {
        "dbname": dbname(),
        "user": user(),
        "password": (password() or None),
        "host": host(),
        "port": port(),
        "options": f"-c search_path={schema()}",
    }
