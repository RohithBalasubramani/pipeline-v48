"""data_db_link.py — the MFM/Asset `db_link` DEFAULT. Delegates to the ONE shared DB config (config/databases.py), so the
database is edited in a SINGLE place (the PG_* block there, or the PG_* env vars). The Django model field default + the
migrations reference `default_db_link` here — keep that name."""
import os
import sys

# bootstrap pipeline_v48 onto sys.path so ems_backend can read the one shared DB config
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # → pipeline_v48
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from config.databases import db_link as _db_link  # noqa: E402


def default_db_link() -> str:
    """The libpq db_link for the time-series DATA — built from config/databases.py (the single source of truth)."""
    return _db_link()
