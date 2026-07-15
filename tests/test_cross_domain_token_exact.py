"""tests/test_cross_domain_token_exact.py — T2.2-S2: cross_domain classifies on token-exact quantity_class classifiers
(no substring false-positives) behind quantity.family_token_exact.

Off (default): the config.metrics.quantity_family SUBSTRING path — byte-identical, INCLUDING its false-positives.
On: token-exact slot_class/name_class + compatible() — the substring false-positive is no longer flagged, a genuine
cross-domain still is."""
from unittest.mock import patch

import layer2.cross_domain as CD


def _di(slot, column, kind="raw", fn=None):
    f = {"slot": slot, "kind": kind}
    if kind == "derived":
        f["fn"] = fn
    else:
        f["column"] = column
    return {"fields": [f]}


def _run(di, token_exact):
    with patch("config.app_config.flag_on", lambda k: token_exact and k == "quantity.family_token_exact"):
        return CD._cross_domain_fields(di)


def test_genuine_cross_domain_flagged_both_modes():
    # voltage slot fed a current column — a REAL wrong-quantity bind; must flag OFF and ON
    di = _di("trend.voltage", "current_avg")
    assert len(_run(di, False)) == 1
    assert len(_run(di, True)) == 1


def test_substring_false_positive_only_off():
    # 'boilerControl' slot: quantity_family('boiler control') -> temperature via the 'oil' substring (WRONG); fed a
    # power column -> OFF flags a spurious cross-domain. name_class('boiler control') is None (token-exact) -> ON abstains.
    di = _di("trend.boilerControl", "active_power_total_kw")
    off = _run(di, False)
    on = _run(di, True)
    assert len(off) >= 1 and off[0][1] == "temperature"      # the substring false-positive (flagged off)
    assert len(on) == 0                                      # token-exact: not classified as temperature, not flagged


def test_same_quantity_never_flagged():
    # a voltage slot fed a voltage column — same quantity, never a cross-domain flag in either mode
    di = _di("trend.voltage", "voltage_avg")
    assert _run(di, False) == [] and _run(di, True) == []


def test_flag_off_is_byte_identical_default():
    # default (no patch) == flag-off path
    di = _di("trend.voltage", "current_avg")
    assert CD._cross_domain_fields(di) == _run(di, False)
