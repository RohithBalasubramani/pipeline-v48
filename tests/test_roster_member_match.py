"""tests/test_roster_member_match.py -- CHARACTERIZATION of the gic-2 / gic-20 collision family across the three
roster/member matchers, now guarding the T2.1-2 hardening (roster.match_hardening). Pure unit tests: DATA-free (no DB,
no LLM, no host) -- the matchers are exercised over synthetic member dicts and by_slug maps.

Three kinds of test live here, all green:
  * flag-OFF CONTRACT tests (`__pass`) assert the DEFAULT behavior that is CORRECT -- the intended contract, run with the
    knob OFF (its byte-identical legacy substring path). They are the regression floor; they must never flip.
  * flag-ON FIX tests (`__hardened`, carry the `hardening_on` fixture) are the FIVE former XFAIL(strict) collision bugs.
    They were written before the fix, asserting the DESIRED post-hardening answer; with roster.match_hardening ON the
    bounded matchers now answer correctly, so the xfail markers are gone and these are ordinary passing assertions.
  * flag-ON CONTRACT tests (`__flag_on`) prove the hardening does NOT regress the genuine matches or the asymmetric
    no-key semantics when the knob is on (exact-slug still wins, a real feeder token still matches, empty/None guards
    unchanged).

Matchers under test (all module-level, imported directly):
  ems_exec/executor/roster_modes_sankey.py :: _match_slug  (bidirectional 'k in s or s in k' substring), _node_role
  ems_exec/executor/roster_modes_series.py :: _member_match (name_contains substring over the name+table 'hay')
  ems_exec/executor/members.py            :: _spec_match   (same name_contains substring shape as _member_match)

KEY DETAIL about the name_contains 'hay' (read from the source, NOT slugified): it is
    (member['name'] + ' ' + member['table']).strip().lower()
so UNDERSCORES SURVIVE. A selector token collides on the RAW underscore form -- 'gic_2' is a substring of 'gic_20' --
while the DASHED 'gic-2' form misses only because of the accidental '_' vs '-' mismatch. Both facts are pinned so the
hardening cannot silently change either without a test flipping.
"""
from __future__ import annotations

import pytest

from ems_exec.executor.roster_modes_sankey import _match_slug, _node_role
from ems_exec.executor.roster_modes_series import _member_match
from ems_exec.executor.members import _spec_match


def _member(name, table=None, type=None, load_group=None):
    """A minimal registry-shaped member dict -- the only keys the matchers read."""
    return {"name": name, "table": table, "type": type, "load_group": load_group}


# Two distinct members whose slugs differ ONLY by the trailing '0' (the gic-2 / gic-20 family).
MEMBER_A = _member("GIC-2", table="gic_2_n1", load_group="GIC-2")     # slug 'gic-2'
MEMBER_B = _member("GIC-20", table="gic_20_n1", load_group="GIC-20")  # slug 'gic-20'


@pytest.fixture
def hardening_on(monkeypatch):
    """Flip roster.match_hardening ON by monkeypatching the config seam match_bounds.enabled() reads -- BOTH cfg and
    flag_on in config.app_config. This exercises the REAL enabled() -> flag_on -> cfg path (the matcher code is
    untouched; only the knob is forced on), so a test carrying this fixture asserts the POST-HARDENING behavior directly.
    The 5 tests below were XFAIL(strict) collision bugs; with the flag on the bounded matchers answer correctly and they
    are now ordinary passing assertions -- no xfail marker survives (T2.1-2)."""
    import config.app_config as _ac
    _orig_cfg, _orig_flag = _ac.cfg, _ac.flag_on
    monkeypatch.setattr(
        _ac, "cfg",
        lambda key, default=None: "on" if key == "roster.match_hardening" else _orig_cfg(key, default))
    monkeypatch.setattr(
        _ac, "flag_on",
        lambda key, default=False, cfg_fn=None:
            True if key == "roster.match_hardening" else _orig_flag(key, default, cfg_fn))
    return True


# =====================================================================================================================
#  _match_slug  (roster_modes_sankey.py)  -- the sankey node->member slug matcher
# =====================================================================================================================
def test_match_slug_exact_slug_wins__pass():
    """CONTRACT: when BOTH slugs are present, an exact slug hit wins over any substring scan. Label 'GIC-20' must
    resolve to MEMBER_B (its exact slug), never to MEMBER_A. Holds today and must keep holding."""
    by_slug = {"gic-2": MEMBER_A, "gic-20": MEMBER_B}
    assert _match_slug("GIC-20", by_slug) is MEMBER_B


def test_match_slug_unrelated_label_returns_none__pass():
    """CONTRACT: a label that neither equals nor substring-overlaps any slug returns None (no fabricated match). This
    also proves None is a REACHABLE outcome, so the 'should be None' collision assertions below are meaningful."""
    assert _match_slug("ups-01", {"gic-2": MEMBER_A}) is None


def test_match_slug_forward_substring_collision__hardened(hardening_on):
    """FIXED (roster.match_hardening T2.1-2): with ONLY 'gic-2' in the map, label 'gic-20' must NOT match anything
    (gic-20 is a different meter). The legacy 'k in s' leg fired -- 'gic-2' is a substring of 'gic-20' -- returning
    MEMBER_A; unique_bounded_match rejects the boundary-broken hit (the '0' after 'gic-2' is a word char) and returns
    None. Flag ON via the fixture."""
    assert _match_slug("gic-20", {"gic-2": MEMBER_A}) is None


def test_match_slug_reverse_substring_collision__hardened(hardening_on):
    """FIXED (T2.1-2), the OTHER direction of the old bidirectional substring: with ONLY 'gic-20' in the map, label
    'gic-2' must NOT match. The legacy 's in k' leg fired -- 'gic-2' is a substring of 'gic-20' -- returning MEMBER_B;
    the bounded matcher returns None (correct no-match). Flag ON."""
    assert _match_slug("gic-2", {"gic-20": MEMBER_B}) is None


# =====================================================================================================================
#  _node_role  (roster_modes_sankey.py)  -- member / trunk / entity classification of a sankey node
# =====================================================================================================================
def test_node_role_member_exact_match__pass():
    """CONTRACT: a node whose label exactly slugs to a roster member is classified 'member' and carries that member.
    Anchors the member path so the trunk-collision fix below cannot regress genuine member matching."""
    role, mr = _node_role({"label": "GIC-08", "id": None}, {"gic-08": MEMBER_A}, frozenset(), set())
    assert role == "member" and mr is MEMBER_A


def test_node_role_trunk_exact_panel_slug__pass():
    """CONTRACT: a node naming the panel itself ('PCC-Panel-1' against panel_slugs {'pcc-panel-1'}) is the trunk. This
    genuine trunk match must survive the containment-collision fix."""
    role, _mr = _node_role({"label": "PCC-Panel-1", "id": None}, {}, {"pcc-panel-1"}, set())
    assert role == "trunk"


def test_node_role_trunk_prefix_containment_collision__hardened(hardening_on):
    """FIXED (T2.1-2): node 'PCC-Panel-10' against panel_slugs {'pcc-panel-1'} is an 'entity' (a foreign labelled node),
    NOT the panel trunk -- Panel-10 is a different panel. The legacy 'p in s' containment leg fired ('pcc-panel-1' is a
    substring of 'pcc-panel-10') and returned 'trunk'; contains_bounded rejects it (the '0' is a word char). Flag ON."""
    role, _mr = _node_role({"label": "PCC-Panel-10", "id": None}, {}, {"pcc-panel-1"}, set())
    assert role == "entity"


# =====================================================================================================================
#  _member_match  (roster_modes_series.py)  -- series-split group membership
# =====================================================================================================================
def test_member_match_type_and_load_group__pass():
    """CONTRACT: the exact-token paths (type_code / load_group, case-insensitive any-of) match. These non-substring
    paths are the reliable ones and must be untouched by the name_contains hardening."""
    assert _member_match(_member("m", type="ups"), {"types": ["UPS"]}) is True
    assert _member_match(_member("m", load_group="gic-08"), {"load_groups": ["GIC-08"]}) is True


def test_member_match_name_contains_genuine_feeder_token__pass():
    """INTENDED USE: name_contains with a real feeder-class token 'ups' matches member 'gic_02_n3_ups' (the token is a
    genuine word in the hay). This is the case name_contains exists for -- it must keep matching after hardening."""
    m = _member("gic_02_n3_ups", table="gic_02_n3")
    assert _member_match(m, {"name_contains": ["ups"]}) is True


def test_member_match_name_contains_underscore_boundary_collision__hardened(hardening_on):
    """FIXED (T2.1-2): selector 'gic_2' must NOT match member 'gic_20_n3_ups' -- gic_2 and gic_20 are different sites.
    The legacy raw-substring test ('gic_2' in 'gic_20_n3_ups ...') was True because the hay keeps underscores and 'gic_2'
    is a prefix of 'gic_20'; contains_bounded rejects it (the '0' after 'gic_2' is a word char). Flag ON."""
    m = _member("gic_20_n3_ups", table="gic_20_n3")
    assert _member_match(m, {"name_contains": ["gic_2"]}) is False


def test_member_match_dash_form_misses_underscore_hay__pass():
    """CHARACTERIZATION of the accidental non-collision: the DASHED token 'gic-2' misses member 'gic_20_n3_ups' today
    only because the hay keeps underscores ('gic-2' is not a substring of 'gic_20...'). False is ALSO the correct
    boundary answer (gic-2 must not match gic-20), so this stays a PASS through the hardening -- pinned so a future
    normalize-the-hay change cannot silently turn it into a collision."""
    m = _member("gic_20_n3_ups", table="gic_20_n3")
    assert _member_match(m, {"name_contains": ["gic-2"]}) is False


def test_member_match_empty_dict_matches_nothing__pass():
    """CONTRACT (asymmetric no-key semantics, part 1): an empty match dict selects NO member -- a series with no
    selector must fold no member (honest-null series), never the whole panel. NOT a bug; it is the contract."""
    assert _member_match(_member("gic_02_n3_ups"), {}) is False


def test_member_match_non_dict_matches_nothing__pass():
    """CONTRACT: a non-dict (None) match also selects nothing on the series side (the guard returns False). Pins the
    other half of _member_match's 'no valid selector -> nothing' rule."""
    assert _member_match(_member("gic_02_n3_ups"), None) is False


# =====================================================================================================================
#  _spec_match  (members.py)  -- bucketed_multi spec group membership (same name_contains shape)
# =====================================================================================================================
def test_spec_match_name_contains_genuine_feeder_token__pass():
    """INTENDED USE: name_contains 'ups' matches member 'gic_02_n3_ups' (mirrors _member_match's genuine case)."""
    m = _member("gic_02_n3_ups", table="gic_02_n3")
    assert _spec_match(m, {"name_contains": ["ups"]}) is True


def test_spec_match_name_contains_underscore_boundary_collision__hardened(hardening_on):
    """FIXED (T2.1-2), same collision shape as _member_match: selector 'gic_2' no longer matches member 'gic_20_n3_ups'
    -- the legacy raw substring matched, contains_bounded rejects the boundary-broken hit. Flag ON."""
    m = _member("gic_20_n3_ups", table="gic_20_n3")
    assert _spec_match(m, {"name_contains": ["gic_2"]}) is False


def test_spec_match_none_matches_everything__pass():
    """CONTRACT (asymmetric no-key semantics, part 2 -- the DELIBERATE asymmetry vs _member_match): a None/absent match
    on the spec side matches EVERY member (the fleet-wide default). NOT a bug; it is the contract. Contrast with
    _member_match({}) which matches NOTHING."""
    assert _spec_match(_member("gic_02_n3_ups"), None) is True


def test_spec_match_empty_dict_matches_everything__pass():
    """CONTRACT: an empty match dict is falsy on the spec side too, so it also matches every member (fleet-wide). This
    is the same 'no selector -> whole fleet' default as None -- and the opposite of _member_match's empty-dict rule."""
    assert _spec_match(_member("gic_02_n3_ups"), {}) is True


# =====================================================================================================================
#  FLAG-ON CONTRACT tests -- the hardening must NOT regress the genuine matches or the asymmetric no-key semantics.
#  These carry the `hardening_on` fixture so they assert the SAME contract the flag-off tests above pin, but with the
#  bounded matchers active. (The flag-off contract tests stay green unconditionally; these prove parity flag-on.)
# =====================================================================================================================
def test_match_slug_exact_slug_wins__flag_on(hardening_on):
    """CONTRACT flag-ON: the exact-slug lookup still fires BEFORE unique_bounded_match, so label 'GIC-20' resolves to
    MEMBER_B (its exact slug), never to MEMBER_A via a bounded scan. The hardening never weakens an exact hit."""
    by_slug = {"gic-2": MEMBER_A, "gic-20": MEMBER_B}
    assert _match_slug("GIC-20", by_slug) is MEMBER_B


def test_match_slug_bounded_containment_still_resolves__flag_on(hardening_on):
    """CONTRACT flag-ON: a GENUINE boundary-clean containment still resolves -- label 'GIC-08-N1' (slug 'gic-08-n1')
    uniquely contains member slug 'gic-08' with a '-' boundary after it, so it matches MEMBER_A. Bounded != no-match."""
    assert _match_slug("GIC-08-N1", {"gic-08": MEMBER_A}) is MEMBER_A


def test_node_role_trunk_exact_panel_slug__flag_on(hardening_on):
    """CONTRACT flag-ON: the genuine trunk match survives -- 'PCC-Panel-1' against panel_slugs {'pcc-panel-1'} is still
    'trunk' (contains_bounded on an exact, edge-bounded slug is True)."""
    role, _mr = _node_role({"label": "PCC-Panel-1", "id": None}, {}, {"pcc-panel-1"}, set())
    assert role == "trunk"


def test_member_match_genuine_ups_token__flag_on(hardening_on):
    """CONTRACT flag-ON: the intended name_contains use still works -- feeder-class token 'ups' matches member
    'gic_02_n3_ups' (bounded by '_' before and the hay edge after). The token name_contains exists for keeps matching."""
    m = _member("gic_02_n3_ups", table="gic_02_n3")
    assert _member_match(m, {"name_contains": ["ups"]}) is True


def test_spec_match_genuine_ups_token__flag_on(hardening_on):
    """CONTRACT flag-ON: same genuine token on the spec side -- 'ups' still matches 'gic_02_n3_ups'."""
    m = _member("gic_02_n3_ups", table="gic_02_n3")
    assert _spec_match(m, {"name_contains": ["ups"]}) is True


def test_member_match_type_and_load_group__flag_on(hardening_on):
    """CONTRACT flag-ON: the exact-token type/load_group paths are untouched by the name_contains hardening."""
    assert _member_match(_member("m", type="ups"), {"types": ["UPS"]}) is True
    assert _member_match(_member("m", load_group="gic-08"), {"load_groups": ["GIC-08"]}) is True


def test_asymmetric_no_key_contract_holds_flag_on(hardening_on):
    """CONTRACT flag-ON (the DELIBERATE asymmetry must survive the hardening): _member_match(m, {}) matches NOTHING
    (series side -> honest-null series) while _spec_match(m, None) and _spec_match(m, {}) match EVERYTHING (spec side ->
    fleet-wide default). The bounded name_contains change touches neither the empty-dict nor the None guard."""
    m = _member("gic_02_n3_ups", table="gic_02_n3")
    assert _member_match(m, {}) is False
    assert _member_match(m, None) is False
    assert _spec_match(m, None) is True
    assert _spec_match(m, {}) is True
