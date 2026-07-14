"""tests/test_member_registry_facts.py — T2.1-1: restore the member type_code/load_group facts the stale
`registries` import killed, behind roster.member_registry_facts (default off = dead-{}, byte-identical).

Flag off: _meter_row returns {} for every id (today's runtime reality — the fact-keyed matchers stay dead).
Flag on: _meter_row returns the real row via data.neuract_live.meters.meter_by, so members carry type/load_group
and the FACT-keyed matchers (match.types / match.load_groups) fire again."""
from unittest.mock import patch

import ems_exec.executor.members as M


def test_flag_off_returns_empty_row():
    with patch("config.app_config.flag_on", lambda k: False):
        assert M._meter_row(11) == {}


def test_flag_on_returns_real_facts():
    fake_row = {"id": 11, "type_code": "ups", "load_group": "GIC-01", "table_name": "gic_01_n3_ups_01"}
    with patch("config.app_config.flag_on", lambda k: k == "roster.member_registry_facts"), \
         patch("data.neuract_live.meters.meter_by", lambda ref: fake_row if ref == 11 else None):
        row = M._meter_row(11)
    assert row["type_code"] == "ups" and row["load_group"] == "GIC-01"


def test_flag_on_unknown_id_still_empty():
    with patch("config.app_config.flag_on", lambda k: k == "roster.member_registry_facts"), \
         patch("data.neuract_live.meters.meter_by", lambda ref: None):
        assert M._meter_row(9999) == {}


def test_flag_on_door_outage_fails_open_to_empty():
    def boom(ref):
        raise RuntimeError("neuract door down")
    with patch("config.app_config.flag_on", lambda k: k == "roster.member_registry_facts"), \
         patch("data.neuract_live.meters.meter_by", boom):
        assert M._meter_row(11) == {}                 # honest-degrade, never raises


def test_types_matcher_dead_off_alive_on():
    # the CONFIRMED bug: match={'types':['ups']} matches a ups member only when facts flow (flag on)
    member = {"name": "GIC-01-N3-UPS-01", "table": "gic_01_n3_ups_01", "type": "ups", "load_group": "GIC-01"}
    match = {"types": ["ups"]}
    # _spec_match is the members-side matcher; it reads member['type'] (stamped from _meter_row.type_code)
    assert M._spec_match(member, match) is True       # with the type fact present it matches
    dead_member = {**member, "type": None}
    assert M._spec_match(dead_member, match) is False  # facts dead (type None) → the types matcher never fires
