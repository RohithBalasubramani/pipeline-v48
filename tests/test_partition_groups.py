"""Partition — union-find unit + live RTM group (orphan 160 via fallback)."""
from layer1a.db_reads.cards_intent import read_page_cards
from layer1a.partition.group_detect import _union_find, detect_groups

RTM = "panel-overview-shell/real-time-monitoring"


def test_union_find_unit():
    comps = _union_find([1, 2, 3, 4], [(1, 2, "x"), (2, 3, "x")])
    sets = sorted((sorted(s) for s in comps), key=len)
    assert [4] in sets and [1, 2, 3] in sets


def test_rtm_group_includes_orphan_160():
    cards = read_page_cards(RTM)
    groups, standalone, dims = detect_groups(RTM, cards)
    assert len(groups) == 1
    assert set(groups[0]) == {5, 6, 7, 8, 9, 10, 11, 160}
    assert standalone == []
    assert "feeder" in dims
