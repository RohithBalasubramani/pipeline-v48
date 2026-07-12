"""Reserved-telemetry contracts [typing F9]: (1) every `di["_*"]` key layer2/build.py writes is enumerated in
layer2/telemetry.DI_TELEMETRY_KEYS (the FE/sweep contract — a new telemetry key must be a discoverable one-line
addition, never a silent stringly side-channel); (2) telemetry_keys.pop_all strips every RESERVED payload key
order-independently and returns them by name (the enrich two-pop ordering trap)."""
import re

from layer2.telemetry import DI_TELEMETRY_KEYS
from ems_exec.executor.telemetry_keys import RESERVED_PAYLOAD_KEYS, pop_all
from ems_exec.executor.gaps import GAPS_KEY
from ems_exec.executor.roster_stats import RESERVED_KEY


def test_every_di_underscore_write_is_enumerated():
    src = open("layer2/build.py").read()
    written = set(re.findall(r'di\[\s*"(_[a-z0-9_]+)"\s*\]', src))
    # keys read-but-not-written (di.get) are covered when written elsewhere in the emit chain
    written |= set(re.findall(r'di\.get\(\s*"(_[a-z0-9_]+)"', src))
    missing = written - DI_TELEMETRY_KEYS
    assert not missing, f"undeclared di._ telemetry keys written by layer2/build.py: {sorted(missing)}"


def test_pop_all_strips_every_reserved_key_and_returns_by_name():
    payload = {"data": {"x": 1}, GAPS_KEY: [{"slot": "x"}], RESERVED_KEY: {"real": 1, "data": 2}}
    got = pop_all(payload)
    assert got == {"gaps": [{"slot": "x"}], "roster_stats": {"real": 1, "data": 2}}
    assert not any(k in payload for k in RESERVED_PAYLOAD_KEYS)
    assert pop_all(None) == {"gaps": None, "roster_stats": None}          # safe on absent payloads
