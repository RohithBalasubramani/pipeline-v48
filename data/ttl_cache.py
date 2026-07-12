"""data/ttl_cache.py — RE-EXPORT FACADE: the TTL cache's home is lib/ttl_cache.py (structure move, refactor audit
2026-07-12 follow-up #2 — it is a generic in-process primitive with no data/-layer dependency; lib/ is the shared
primitives home). Byte-compatible: every existing `from data.ttl_cache import TTLCache` keeps working. New code
imports from lib.ttl_cache."""
from lib.ttl_cache import *          # noqa: F401,F403
from lib.ttl_cache import TTLCache   # noqa: F401  (explicit for greppability)
