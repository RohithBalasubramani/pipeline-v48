"""ems_exec/executor/telemetry_keys.py — the ONE enumeration of reserved in-payload telemetry keys + the one pop
[typing F9, 2026-07-12].

Two modules each smuggle a reserved `_`-prefixed key into the COMPLETED payload (gaps.GAPS_KEY='_blank_gaps',
roster_stats.RESERVED_KEY='_roster_stats') and the serve boundary had to pop both, in the right order, before the
render-verdict leaf scan — a new reserved key one consumer forgets to pop is silently counted as a blank data leaf.
pop_all() dissolves the ordering problem: ONE call strips every reserved key and returns them by name. The keys stay
defined in their owner modules (this module re-reads them — no second literal to drift).

The Layer-2 `data_instructions._*` telemetry family is enumerated in layer2/telemetry.py (its writer's layer).
[atomic; behavior-identical to the old two-pop sequence]
"""
from ems_exec.executor.gaps import GAPS_KEY, pop_gaps
from ems_exec.executor.roster_stats import RESERVED_KEY as ROSTER_STATS_KEY
from ems_exec.executor import roster_stats as _rstats

RESERVED_PAYLOAD_KEYS = (GAPS_KEY, ROSTER_STATS_KEY)


def pop_all(payload):
    """Strip EVERY reserved telemetry key off a completed payload (order-independent) and return them by name:
    {'gaps': <records|None>, 'roster_stats': <dict|None>}. Safe on None/non-dict (returns both None)."""
    return {"roster_stats": _rstats.pop(payload), "gaps": pop_gaps(payload)}
