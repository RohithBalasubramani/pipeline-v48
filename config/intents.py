"""config/intents.py — the analytical-intent enum (strict). Add/remove intents here.

LAZY module attributes (PEP 562): each access re-reads cfg(), so a DB row edit + app_config.reload() reaches consumers
without a process restart."""
from config.app_config import cfg

_LAZY = {
    "INTENT_DEFAULT": lambda: cfg("intents.default", "trend"),
    "INTENT_VOCAB":   lambda: set(cfg("intents.vocab", ["trend", "distribution", "snapshot", "table", "events"])),
}


def __getattr__(name):
    if name in _LAZY:
        return _LAZY[name]()
    raise AttributeError(f"module 'config.intents' has no attribute {name!r}")
