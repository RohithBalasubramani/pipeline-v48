"""EMS Query Copilot — configuration (env-overridable).

This layer is fully standalone: it does NOT import anything from the pipeline
(pipeline.py / layer2_swap.py / column_resolve.py / l6.py / L1/L2/L3). It only
*reads* the same Postgres metadata the pipeline reads, via its own psql helper.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX_PATH = os.path.join(HERE, "copilot_index.sqlite")

# --- model serving (its OWN endpoint, never the pipeline's 35B on :8200) ---
LLM_URL = os.getenv("COPILOT_LLM_URL", "http://localhost:8201/v1")
LLM_MODEL = os.getenv("COPILOT_LLM_MODEL", "Qwen/Qwen3-4B-Instruct-2507-FP8")
LLM_TIMEOUT = float(os.getenv("COPILOT_LLM_TIMEOUT", "8"))  # request timeout

# --- service ---
PORT = int(os.getenv("COPILOT_PORT", "8772"))

# --- source databases (read-only) — TWO sources only ---
#  1) target_version1.neuract @ 127.0.0.1:5433 (LIVE logging DB, ~321 tables) — the ASSET + METRIC
#     universe (device_mappings.table_name / field_key, AI-named). NOT the stale local :5432 copy.
#  2) cmd_catalog @ local :5432 — the EMS card/design catalog: cards, pages/templates, areas, and the
#     exemplar questions that ground suggestion phrasing (this is design metadata, NOT device data).
# lt_panels_db / lt_mfm / lt_parameter are NO LONGER used — the live neuract table names are richer.
CMD_DB = os.getenv("COPILOT_CMD_DB", "cmd_catalog")         # local :5432 (EMS card/design catalog)
DATA_DB = os.getenv("COPILOT_DATA_DB", "target_version1")   # LIVE logging DB (tunnel, below)
DATA_HOST = os.getenv("COPILOT_DATA_HOST", "127.0.0.1")
DATA_PORT = os.getenv("COPILOT_DATA_PORT", "5433")
MAP_SCHEMA = os.getenv("COPILOT_MAP_SCHEMA", "neuract")
MAP_TABLE = os.getenv("COPILOT_MAP_TABLE", "device_mappings")
PG_USER = os.getenv("COPILOT_PG_USER", "postgres")

# --- behaviour knobs ---
MAX_SUGGESTIONS = int(os.getenv("COPILOT_MAX_SUGGESTIONS", "5"))
RETRIEVE_PER_TYPE = {"asset": 12, "metric": 12, "card": 8, "page": 5, "area": 5}
RETRIEVE_QUESTIONS = int(os.getenv("COPILOT_RETRIEVE_QUESTIONS", "10"))
# 0 = no max_tokens cap (let the model stop at EOS — the JSON is short anyway)
LLM_MAX_TOKENS = int(os.getenv("COPILOT_LLM_MAX_TOKENS", "0"))
LLM_TEMPERATURE = float(os.getenv("COPILOT_LLM_TEMPERATURE", "0.3"))
