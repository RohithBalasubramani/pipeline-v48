"""tests/test_compare_overlay_tokens_characterization.py — pins TODAY'S behavior of host/compare_overlay.py
comparand_token + the merge_overlay keying BEFORE the Tier-0 H1 fix (deterministic_audit_20260714 H1 / T0-4).

The DEFECT being pinned: comparand_token is a per-name heuristic with no uniqueness guarantee — 'PCC-Panel-1' and
'Pump-1' both yield 'P1'. merge_overlay keys per-comparand payloads by token (per = {tok: ...}), so two same-token
comparands OVERWRITE: one panel's data silently vanishes from the merged overlay card (CONFIRMED silent data loss).
T0-4 adds unique_comparand_tokens() at the tokens_by_id build; comparand_token itself stays as-is (per-name
heuristic; uniqueness is a SET property, enforced where the set is known)."""
import host.compare_overlay as CO


# ── comparand_token: the per-name heuristic (correct pins) ──────────────────────────────────────────────────────────

def test_basic_tokens():
    assert CO.comparand_token("PCC-Panel-1") == "P1"
    assert CO.comparand_token("Transformer 2") == "T2"
    assert CO.comparand_token("DG-3") == "D3"


def test_no_trailing_number_takes_first_word():
    assert CO.comparand_token("Main Incomer") == "Main"


def test_empty_name():
    assert CO.comparand_token("") == "?"
    assert CO.comparand_token(None) == "?"


def test_DEFECT_distinct_assets_same_token():
    # the H1 collision: distinct assets, identical token
    assert CO.comparand_token("PCC-Panel-1") == CO.comparand_token("Pump-1") == "P1"


# ── merge_overlay: the silent-overwrite consequence ─────────────────────────────────────────────────────────────────

def _card(name, aid, amps):
    return {"render_card_id": 18, "asset": {"id": aid, "name": name},
            "payload": {"strip": {"stats": {"amps": amps}}}}


def test_DEFECT_same_token_comparands_lose_data_in_merge():
    """Two comparands that collide to one token: merge_overlay's per={tok: ...} dict keeps only the LAST one's
    stats — the first panel's data is silently gone. Pinned as today's (broken) behavior; T0-4's unique tokens
    make this test's setup impossible via merge_all (each comparand gets its own token)."""
    a, b = _card("PCC-Panel-1", 1, 100.0), _card("Pump-1", 2, 7.0)
    tok = CO.comparand_token("PCC-Panel-1")            # == comparand_token("Pump-1") == "P1"
    merged = CO.merge_overlay([(tok, a), (tok, b)], [tok])
    sections = merged["payload"]["strip"]["stats"]["sections"]
    assert list(sections.keys()) == ["P1"]             # ONE section for TWO comparands
    assert sections["P1"]["amps"] == 7.0               # the Pump OVERWROTE the panel — 100.0 A vanished


def test_distinct_tokens_merge_correctly():
    a, b = _card("PCC-Panel-1", 1, 100.0), _card("Transformer 2", 2, 7.0)
    merged = CO.merge_overlay([("P1", a), ("T2", b)], ["P1", "T2"])
    sections = merged["payload"]["strip"]["stats"]["sections"]
    assert sections["P1"]["amps"] == 100.0 and sections["T2"]["amps"] == 7.0
    assert merged["payload"]["strip"]["stats"]["amps"] == 107.0    # union sum
