"""tests/test_compare_overlay_unique_tokens.py -- T0-4: the H1 silent data-loss fix (deterministic_audit_20260714).

comparand_token is a per-name heuristic with no uniqueness guarantee -- 'PCC-Panel-1' and 'Pump-1' both yield 'P1'
(pinned by test_compare_overlay_tokens_characterization) -- and merge_overlay keys per-comparand payloads by token
(per = {tok: ...}), so two same-token comparands used to OVERWRITE each other: one panel's data silently vanished
from the merged overlay card. The fix: host/multi_asset builds tokens_by_id via unique_comparand_tokens over the
WHOLE comparand set (collision-free, deterministic in lane order) before merge_all. These tests pin the fix:
per-set uniqueness + head widening, determinism, the suffix fallback, and the merge_all regression (BOTH colliding
comparands' values survive the merge)."""
import host.compare_overlay as CO


# -- unique_comparand_tokens: collision-free + deterministic over the SET --------------------------------------------

def test_collision_two_names_two_distinct_tokens():
    toks = CO.unique_comparand_tokens([(1, "PCC-Panel-1"), (2, "Pump-1")])
    assert len(toks) == 2 and len(set(toks.values())) == 2     # collision-free
    assert toks[1] == "P1"                                     # the FIRST holder keeps the short token
    assert toks[2] == "Pu1"                                    # the collider rebuilt with a WIDER alpha head


def test_no_collision_matches_comparand_token():
    # a non-colliding set stays byte-identical to comparand_token (test_multi_parallel pins ["U01", "U02"] end-to-end)
    toks = CO.unique_comparand_tokens([(1, "UPS-01"), (2, "UPS-02")])
    assert toks == {1: CO.comparand_token("UPS-01"), 2: CO.comparand_token("UPS-02")} == {1: "U01", 2: "U02"}


def test_deterministic_same_input_same_output():
    named = [(1, "PCC-Panel-1"), (2, "Pump-1"), (3, "Transformer 2")]
    assert CO.unique_comparand_tokens(named) == CO.unique_comparand_tokens(list(named))
    assert CO.unique_comparand_tokens(named) == {1: "P1", 2: "Pu1", 3: "T2"}


def test_three_way_collision_three_distinct():
    toks = CO.unique_comparand_tokens([(1, "PCC-Panel-1"), (2, "Pump-1"), (3, "Pipe-1")])
    assert len(set(toks.values())) == 3                        # every comparand keeps its OWN section key
    assert toks[1] == "P1"                                     # input order decides who keeps the bare token


def test_identical_names_fall_to_letter_suffix():
    # 'P-1' has a 1-char head (no widening possible): dup names de-collide via the 'b', 'c', ... suffix
    toks = CO.unique_comparand_tokens([(1, "P-1"), (2, "P-1"), (3, "P-1")])
    assert len(set(toks.values())) == 3
    assert toks[1] == "P1" and toks[2] == "P1b" and toks[3] == "P1c"


# -- regression through merge_all: colliding comparands both SURVIVE the overlay merge -------------------------------

def _card(aid, name, amps):
    return {"render_card_id": 18, "asset": {"id": aid, "name": name},
            "payload": {"strip": {"stats": {"amps": amps}}}}


def test_merge_all_keeps_both_colliding_comparands():
    """The H1 data-loss shape end-to-end: two comparands whose names collide to 'P1' now merge into ONE overlay card
    whose stats.sections carries BOTH tokens with each comparand's OWN value (before the fix: one section, the last
    comparand's value only -- see test_compare_overlay_tokens_characterization's DEFECT pin)."""
    cards = [_card(1, "PCC-Panel-1", 100.0), _card(2, "Pump-1", 7.0)]
    tokens_by_id = CO.unique_comparand_tokens([(1, "PCC-Panel-1"), (2, "Pump-1")])
    merged = CO.merge_all(cards, tokens_by_id)
    assert len(merged) == 1                                    # one merged card per render_card_id
    stats = merged[0]["payload"]["strip"]["stats"]
    sections = stats["sections"]
    assert set(sections.keys()) == {"P1", "Pu1"}               # BOTH comparands present -- no silent overwrite
    assert sections["P1"]["amps"] == 100.0                     # the panel's own value
    assert sections["Pu1"]["amps"] == 7.0                      # the pump's own value
    assert stats["amps"] == 107.0                              # the union sum sees both comparands
