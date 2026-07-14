"""tests/test_sections_token_registry.py — registry-VALIDATED token() (T0-5, deterministic_audit_20260714 L2-07).

token() no longer synthesizes '<n><S>' unchecked: the candidate spellings (as-written + zero-stripped) are checked
against the REAL section values in equipment.mfm (_section_map). Exactly ONE registry hit -> that token; zero hits
(no such section) or an ambiguous pair (both '01A' and '1A' real) -> honest None. Equipment door dark (q raises ->
map {}) -> the legacy synthesized token (fail-open on outage, unchanged). Plus the renderer seam: a SECTION-asked
panel_aggregate render whose token resolved None must take the honest-blank branch, NEVER silently widen to the
full-panel roster.

Offline: data.db_client.q is monkeypatched (sections._section_map imports it at call time) and sections._CACHE is
cleared around every test — the map is process-cached after ONE full read, so a stale real-DB map would otherwise
shadow the pinned fixture (and the pinned fixture would poison later real-DB tests)."""
import pytest

import data.equipment.sections as SE


@pytest.fixture(autouse=True)
def _clean_cache():
    SE._CACHE.clear()
    yield
    SE._CACHE.clear()


def _pin_map(monkeypatch, rows):
    """Pin the equipment.mfm registry: q('cmd_catalog', sql) yields (table_name, section) rows."""
    import data.db_client as DB
    monkeypatch.setattr(DB, "q", lambda db, sql: list(rows))
    SE._CACHE.clear()                                   # drop any previously cached real map


def test_real_token_passes(monkeypatch):
    _pin_map(monkeypatch, [("t1", "1A"), ("t2", "1B"), ("t3", "2A")])
    assert SE.token("PCC-Panel-1", "A") == "1A"


def test_zero_stripped_candidate_hits(monkeypatch):
    # 'PCC-Panel-01' -> candidates {'01A', '1A'}; only '1A' is real -> the single hit wins (collapse CONFIRMED
    # by the registry, not assumed).
    _pin_map(monkeypatch, [("t1", "1A"), ("t2", "1B"), ("t3", "2A")])
    assert SE.token("PCC-Panel-01", "A") == "1A"


def test_not_a_real_section_is_none(monkeypatch):
    # panel 99 has NO section in the registry -> honest None (never a token that silently filters the member
    # roll-up to zero).
    _pin_map(monkeypatch, [("t1", "1A"), ("t2", "1B"), ("t3", "2A")])
    assert SE.token("PCC-Panel-99", "A") is None


def test_ambiguous_zero_variant_is_none(monkeypatch):
    # BOTH '01A' and '1A' are real registry tokens -> 'PCC-Panel-01' cannot be attributed to one section -> None.
    _pin_map(monkeypatch, [("t1", "1A"), ("t2", "01A"), ("t3", "1B")])
    assert SE.token("PCC-Panel-01", "A") is None


def test_door_dark_falls_open_to_legacy(monkeypatch):
    # equipment door dark (DB raises -> _section_map {}) -> the LEGACY synthesized token; an outage keeps the
    # fail-open behavior byte-identical to pre-T0-5 (never a crash, never a new None on a flap).
    import data.db_client as DB

    def _boom(db, sql):
        raise RuntimeError("equipment door dark")

    monkeypatch.setattr(DB, "q", _boom)
    SE._CACHE.clear()
    assert SE.token("PCC-Panel-1", "A") == "1A"


# -- the renderer seam: section asked + token None -> honest-blank branch, NEVER the full-panel roster ---------------

def test_renderer_section_token_none_takes_honest_blank_branch(monkeypatch):
    """A panel_aggregate render with a SECTION stamped whose token resolves None must NOT silently widen to the
    full panel: the members resolve is never called (with or without a section filter) and the card ships the same
    honest-blank coverage badge an orphan panel gets."""
    from ems_exec.renderers import panel_aggregate as PA

    _pin_map(monkeypatch, [("t1", "1A"), ("t2", "1B")])   # panel 99 section A is NOT a real token -> None

    calls = []

    def _spy_resolve(mfm_id, section_token=None):
        calls.append((mfm_id, section_token))
        return [{"mfm_id": 1, "name": "m1", "table": "t1", "role": "outgoing"}], \
            {"reporting": 1, "expected": 1, "verdict": "render"}

    monkeypatch.setattr(PA._members, "resolve", _spy_resolve)

    asset = {"mfm_id": 999, "name": "PCC-Panel-99", "table": "pcc_panel_99", "section": "A"}
    card = {"exact_metadata": {"kpis": {"total_kw": None}}, "data_instructions": {"fields": []}}
    out = PA.render(asset, card, {"asset_table": "pcc_panel_99", "mfm_id": 999,
                                  "window": ("2026-07-01T00:00:00", "2026-07-02T00:00:00")})

    assert calls == [], "section asked + token None must NOT resolve the roster (silent full-panel widen)"
    assert isinstance(out, dict)
    assert out["widgets"]["_coverage"]["verdict"] == "honest_blank"
    assert out["widgets"]["_coverage"] == {"reporting": 0, "expected": 0, "verdict": "honest_blank"}


def test_renderer_no_section_path_still_resolves_full_panel(monkeypatch):
    """The NO-section path is untouched: resolve is called once with the panel's mfm_id and no section filter."""
    from ems_exec.renderers import panel_aggregate as PA

    _pin_map(monkeypatch, [("t1", "1A"), ("t2", "1B")])

    calls = []

    def _spy_resolve(mfm_id, section_token=None):
        calls.append((mfm_id, section_token))
        return [], {"reporting": 0, "expected": 0, "verdict": "honest_blank"}

    monkeypatch.setattr(PA._members, "resolve", _spy_resolve)

    asset = {"mfm_id": 320, "name": "PCC-Panel-4", "table": "pcc_panel_4_feedbacks"}
    card = {"exact_metadata": {"kpis": {"total_kw": None}}, "data_instructions": {"fields": []}}
    out = PA.render(asset, card, {"asset_table": "pcc_panel_4_feedbacks", "mfm_id": 320,
                                  "window": ("2026-07-01T00:00:00", "2026-07-02T00:00:00")})

    assert calls == [(320, None)]
    assert isinstance(out, dict)


def test_renderer_real_section_token_still_filters(monkeypatch):
    """A REAL section token flows through to resolve unchanged (the section view keeps working)."""
    from ems_exec.renderers import panel_aggregate as PA

    _pin_map(monkeypatch, [("t1", "1A"), ("t2", "1B")])

    calls = []

    def _spy_resolve(mfm_id, section_token=None):
        calls.append((mfm_id, section_token))
        return [], {"reporting": 0, "expected": 0, "verdict": "honest_blank"}

    monkeypatch.setattr(PA._members, "resolve", _spy_resolve)

    asset = {"mfm_id": 317, "name": "PCC-Panel-1", "table": "pcc_panel_1", "section": "B"}
    card = {"exact_metadata": {"kpis": {"total_kw": None}}, "data_instructions": {"fields": []}}
    PA.render(asset, card, {"asset_table": "pcc_panel_1", "mfm_id": 317,
                            "window": ("2026-07-01T00:00:00", "2026-07-02T00:00:00")})

    assert calls == [(317, "1B")]
