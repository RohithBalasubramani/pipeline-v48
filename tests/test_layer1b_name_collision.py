"""Layer 1b name-collision discipline + ghost-skip + candidate recall — NON-LIVE (no LLM, deterministic over the local
cmd_catalog registry_* mirror). Covers F5 (homonym confident-pin), F6 (broken candidate recall), P03 (ghost table).

The tokens under test are stable registry facts (queried 2026-07-04):
  DG-3      → id 4  'DG-3 MFM' (dg_3_mfm)            AND id 302 'GIC-28-N3-DG-03 [Jackson]' (empty gic_28 twin)
  UPS-04    → ids 23/191/299 (real UPS-04s)          — NOT the Laminator-4.1 (id 156)
  UPS-01    → ids 11/188/192/194/296                 — id 11 'GIC-01-N3-UPS-01' is the one the AI omitted (F6)
  UPS-10    → id 78 'GIC-07-N5-UPS - 10'             AND id 236 'GIC-21-N6-UPS-10 Incomer-4'
  Transformer-03 → id 167 (_sch GHOST) + id 173 (_se, data) + id 100176 (pqm) — the ghost must never appear
"""
from layer1b.resolve.asset_candidates import asset_candidates
from layer1b.resolve.name_collision import unit_tokens, colliding_rows, is_collision, uniquely_named

_CANDS = asset_candidates()


def _ids(rows):
    return {c[0] for c in rows}


# ── unit_tokens: lexical class+unit parse (prompt-side and name-side) ─────────────────────────────────────────────
def test_unit_tokens_variants():
    assert unit_tokens("Real-time power of DG-03 Jackson") == {("dg", 3)}
    assert unit_tokens("Load profile of UPS-04") == {("ups", 4)}
    assert unit_tokens("GIC-07-N5-UPS - 10 CL:600 KVA") == {("ups", 10)}          # spaced form on a registry name
    # a bare/number-less class implies no token (the class prior handles that, not the collision gate)
    assert unit_tokens("battery backup autonomy") == set()


def test_unit_tokens_laminator_is_not_ups04():
    # the false-positive the AI confidently pinned: 'UPS Supply Laminator-4.1' carries NO ('ups',4) token — 'UPS'
    # is not immediately followed by the number, so it never enters the UPS-04 collision set (id 156 excluded).
    assert ("ups", 4) not in unit_tokens("GIC-14-N2-UPS Supply Laminator-4.1")
    assert "156" not in {c[0] for c in colliding_rows("Load profile of UPS-04", _CANDS)}


# ── F5: homonym collision → refuse confident pin ─────────────────────────────────────────────────────────────────
def test_F5_dg03_is_collision():
    # DG-3 legacy meter (id 4) and DG-03 [Jackson] (id 302) are DISTINCT physical devices sharing the 'DG-3' token
    assert is_collision("Real-time power of DG-03 Jackson", _CANDS) is True
    rows = colliding_rows("Real-time power of DG-03 Jackson", _CANDS)
    assert {"4", "302"} <= _ids(rows)


def test_F5_ups04_is_collision_and_excludes_laminator():
    assert is_collision("Load profile of UPS-04", _CANDS) is True
    rows = colliding_rows("Load profile of UPS-04", _CANDS)
    got = _ids(rows)
    assert {"23", "191", "299"} <= got                 # the real UPS-04s are all recalled
    assert "156" not in got                            # the Laminator-4.1 false-positive is NOT offered


# ── F6: candidate recall must include the correctly-named asset the AI omitted ───────────────────────────────────
def test_F6_ups01_recall_includes_named_asset():
    rows = colliding_rows("UPS-01 load percentage right now", _CANDS)
    got = _ids(rows)
    assert "11" in got                                 # GIC-01-N3-UPS-01 — the dense one the AI dropped
    assert is_collision("UPS-01 load percentage right now", _CANDS) is True


def test_F6_ups01_recall_excludes_wrong_unit():
    rows = colliding_rows("UPS-01 load percentage right now", _CANDS)
    # UPS-07 (id 233) is a different unit number — must never leak into the UPS-01 candidate set
    assert "233" not in _ids(rows)


# ── P03: ghost (table_exists=False) rows are never candidates / never a collision member ─────────────────────────
def test_P03_transformer03_skips_ghost():
    rows = colliding_rows("Show voltage levels for Transformer-03", _CANDS)
    got = _ids(rows)
    assert "167" not in got                            # gic_15_n12_..._sch ghost (table_exists=False) dropped
    assert "173" in got                                # the real _se data-bearing row survives


def test_P03_ghost_flag_present_in_registry():
    by_id = {c[0]: c for c in _CANDS}
    assert len(by_id["167"]) > 9 and by_id["167"][9] is False   # ghost flagged
    assert by_id["173"][9] is True                              # real row flagged renderable


# ── non-collision / non-asset prompts fall straight through (no false gate) ──────────────────────────────────────
# ── full-name / GIC-prefix prompts still pin (collision gate must not fire on an already-disambiguated name) ──────
def test_full_gic_name_pins_not_collision():
    # 'GIC-01-N3-UPS-01' names one colliding row in full → NOT ambiguous, pin id 11 (preserves the reconcile path)
    rows = colliding_rows("real time monitoring for GIC-01-N3-UPS-01", _CANDS)
    u = uniquely_named("real time monitoring for GIC-01-N3-UPS-01", rows)
    assert u is not None and u[0] == "11"
    assert is_collision("real time monitoring for GIC-01-N3-UPS-01", _CANDS) is False


def test_full_jackson_name_pins_the_jackson_row():
    # the explicit bracketed name pins the Jackson genset (id 302), never the legacy DG-3 meter (id 4)
    p = "power of GIC-28-N3-DG-03 [Jackson]"
    u = uniquely_named(p, colliding_rows(p, _CANDS))
    assert u is not None and u[0] == "302"
    assert is_collision(p, _CANDS) is False


def test_partial_dg03_jackson_stays_ambiguous():
    # 'DG-03 Jackson' (partial, no GIC prefix / full name) is the F5 case → picker, never a lone pin
    assert uniquely_named("Real-time power of DG-03 Jackson",
                          colliding_rows("Real-time power of DG-03 Jackson", _CANDS)) is None
    assert is_collision("Real-time power of DG-03 Jackson", _CANDS) is True


def test_no_token_prompt_is_not_a_collision():
    assert is_collision("show me the total plant energy today", _CANDS) is False
    assert colliding_rows("show me the total plant energy today", _CANDS) == []


def test_single_match_token_is_not_a_collision():
    # AHU-5 exists as exactly one renderable device (id 36) — a lone match must NOT trigger the picker
    rows = colliding_rows("temperature of AHU-5", _CANDS)
    assert _ids(rows) == {"36"}
    assert is_collision("temperature of AHU-5", _CANDS) is False
