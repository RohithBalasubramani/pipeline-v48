"""config/databases.py — THE SINGLE PLACE for DB wiring. Edit the connection HERE (or set the PG_* env vars); both the
pipeline AND ems_backend read this one module (ems_backend imports it via a sys.path bootstrap). Nothing else hard-codes
a host/port/db/schema."""
import os

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  THE LIVE LOGGING DB  —  edit these four (or the PG_* env vars) and everything follows
#  target_version1 / schema `neuract` (321 tables, actively writing). archbox tunnel: 127.0.0.1:5433. postgres, no pwd.
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
PG_HOST     = os.environ.get("PG_HOST", "127.0.0.1")        # archbox tunnel host (local Postgres → "localhost")
PG_PORT     = os.environ.get("PG_PORT", "5433")             # archbox tunnel port (local Postgres → "5432")
PG_DB       = os.environ.get("PG_DB", "target_version1")    # the live logging database
PG_SCHEMA   = os.environ.get("PG_SCHEMA", "neuract")        # the logged-meter schema
PG_USER     = os.environ.get("PG_USER", "postgres")
PG_PASSWORD = os.environ.get("PG_PASSWORD", "")             # localhost trust → empty


# the DATA-TABLE SHAPE (the live per-meter tables' timestamp column + whether rows are multi-panel). neuract gic_*
# tables are ONE meter per table with a `timestamp_utc` column and NO panel_id. Flip these if the data shape changes.
DATA_TS_COL       = os.environ.get("DATA_TS_COL", "timestamp_utc")     # the timestamp column in the live data tables
DATA_TS_CAST      = os.environ.get("DATA_TS_CAST", "::timestamptz")    # neuract stores ts as ISO-8601 TEXT → cast for time math ('' if already timestamptz)
DATA_HAS_PANEL_ID = os.environ.get("DATA_HAS_PANEL_ID", "0") == "1"    # neuract = per-meter tables → no panel_id filter

# (the panel→feeder TOPOLOGY now reads the canonical registry via data/registry/lt_mfm.py — cmd_catalog registry_*
#  mirror-first, live neuract fallback. The old TOPOLOGY_OUTGOING knob is retired with the private-id-space era.)


def db_link():
    """The libpq connection string ems_backend pins per MFM to read the time-series DATA (search_path=PG_SCHEMA)."""
    opts = f"-c search_path={PG_SCHEMA}".replace(" ", "%20").replace("=", "%3D")
    return f"postgresql://{PG_USER}@{PG_HOST}:{PG_PORT}/{PG_DB}?options={opts}"


def django_db():
    """The ems_backend Django `DATABASES['default']` dict — same one connection."""
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": PG_DB, "USER": PG_USER, "PASSWORD": PG_PASSWORD,
        "HOST": PG_HOST, "PORT": PG_PORT,
        "OPTIONS": {"options": f"-c search_path={PG_SCHEMA}"},
    }


# ── pipeline CATALOG db (card/page structure — separate metadata, NOT the logging DB above) ─────────────────────────
PSQL_USER   = PG_USER
CMD_CATALOG = os.environ.get("CMD_CATALOG_DB", "cmd_catalog")   # card/page catalog (1a/1b/Layer2 structure)

# ── asset REGISTRY — the CANONICAL CMD_V2 registry (neuract lt_mfm/asset/device_mappings et al), MIRRORED into
# cmd_catalog as registry_* by scripts/sync_neuract_registry.py and read via data/registry/lt_mfm.py (mirror-first,
# live fallback). The old meta_data_version1 shadow registry (private row_number id-space) is RETIRED. [directives c+d]

# the live time-series DATA database + schema (== the logging DB above).
DATA_DB         = PG_DB
DATA_SCHEMA     = PG_SCHEMA
CONSUMER_SCHEMA = PG_SCHEMA                                     # schema the column/data reads use (== the logging schema)
TEST_DB     = os.environ.get("TEST_DB", "")                     # OPEN: built after the pipeline
DB_TARGET   = os.environ.get("DB_TARGET", "live")              # "live" (DATA_DB) | "test" (TEST_DB fixture)


def data_db():
    """The time-series DATA database the Layer-2 worker/helper reads when DB_TARGET='live'."""
    return TEST_DB if DB_TARGET == "test" and TEST_DB else DATA_DB


# ── connection ROUTING — which endpoint each db lives on (the single source q() reads) ──────────────────────────────
# DATA + REGISTRY + lineage are on the archbox tunnel (PG_HOST:PG_PORT, :5433). The CATALOG (cmd_catalog) + test
# fixtures are on the LOCAL endpoint. q() picks per-db so the pipeline reads each db from the right place.
CATALOG_HOST = os.environ.get("CATALOG_HOST", "127.0.0.1")     # local endpoint for cmd_catalog
CATALOG_PORT = os.environ.get("CATALOG_PORT", "5432")
_TUNNEL_DBS = {DATA_DB, "meta_data_version1", "target_version1", "target_version1_meta"}


def conn_env(db):
    """PGHOST/PGPORT/PGUSER/PGPASSWORD for `db` — routes the live tunnel (DATA+REGISTRY) vs the local catalog endpoint."""
    host, port = (PG_HOST, PG_PORT) if db in _TUNNEL_DBS else (CATALOG_HOST, CATALOG_PORT)
    return {"PGHOST": host, "PGPORT": str(port), "PGUSER": PG_USER, "PGPASSWORD": PG_PASSWORD}
