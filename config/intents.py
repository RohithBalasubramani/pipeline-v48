"""config/intents.py — the analytical-intent enum (strict). Add/remove intents here."""
from config.app_config import cfg

INTENT_DEFAULT = cfg("intents.default", "trend")
INTENT_VOCAB = set(cfg("intents.vocab", ["trend", "distribution", "snapshot", "table", "events"]))
