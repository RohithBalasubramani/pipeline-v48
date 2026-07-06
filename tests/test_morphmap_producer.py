"""ITEM 18 — morph-map producer: apply({path: value}) onto the stored skeleton MUST be byte-equivalent to the live
produce→gate→enforce sequence on identical declared intent, reject data/chrome/invented morphs identically, and stay
COMPLETELY unwired from the default emit path (flag emit.morphmap_mode default-off). No DB rows required (synthetic
fixtures); no live LLM."""
import copy
import json

import pytest  # noqa

from layer2.emit.metadata.producer import produce, metadata_reference
from layer2.emit.morphmap.producer import apply as morph_apply
from layer2.gates import gate_exact_metadata, enforce_exact_metadata


# synthetic card: metadata (title/unit/labels/bool) + DATA tier (numeric kpi.value; roster-named numeric series)
RAW = {
    "title": "Feeder Load",
    "unit": "kW",
    "showLegend": False,
    "kpi": {"label": "Peak", "value": 427.5},
    "series": [12.5, 13.0, 14.2],
}
STORED = {                                # the seedless skeleton (data leaves → typed placeholders)
    "title": "Feeder Load",
    "unit": "kW",
    "showLegend": False,
    "kpi": {"label": "Peak", "value": 0},
    "series": [],
}


def _full_emit(ai_meta, morphed):
    """EXACTLY layer2/build._finalize's metadata sequence for the synthetic card."""
    ref = metadata_reference(RAW, stored=STORED)
    full, applied, rejected = produce(RAW, ai_meta, morphed, stored=STORED)
    ok, _ = gate_exact_metadata(full, ref, morphed=applied)
    if not ok:
        full, _rev = enforce_exact_metadata(full, ref, morphed=applied)
    return full


def _b(o):
    return json.dumps(o, sort_keys=True, separators=(",", ":"), default=str)


def test_pure_default_conforms_and_defaults_ship():
    built, rep = morph_apply({}, STORED, default_payload=RAW)
    assert rep["conforms"] is True
    assert rep["applied"] == [] and rep["rejected"] == []
    assert built["title"] == "Feeder Load" and built["unit"] == "kW" and built["kpi"]["label"] == "Peak"
    # identical bytes to the live path's pure-default emission (incl. the gate's DATA-slot handling of `series`)
    assert _b(built) == _b(_full_emit({}, []))


def test_metadata_morph_applies_and_everything_else_is_byte_identical():
    built, rep = morph_apply({"title": "DG Focus — Load"}, STORED, default_payload=RAW)
    assert rep["applied"] == ["title"] and rep["conforms"] is True
    assert built["title"] == "DG Focus — Load"
    ref, _ = morph_apply({}, STORED, default_payload=RAW)
    ref["title"] = "DG Focus — Load"
    assert _b(built) == _b(ref)                      # ONLY the declared leaf moved


def test_data_leaf_morph_rejected_never_ships():
    built, rep = morph_apply({"kpi.value": 55.5}, STORED, default_payload=RAW)
    assert rep["applied"] == []
    assert any("DATA leaf" in r for r in rep["rejected"])
    assert built["kpi"]["value"] == 0                # placeholder stays; data fills live from the frame


def test_subtree_containing_a_data_leaf_is_rejected_whole():
    built, rep = morph_apply({"kpi": {"label": "X", "value": 3}}, STORED, default_payload=RAW)
    assert rep["applied"] == []
    assert any("DATA leaf" in r for r in rep["rejected"])
    assert built["kpi"] == {"label": "Peak", "value": 0}


def test_invented_and_empty_paths_rejected():
    built, rep = morph_apply({"nope.key": "x", "": "y"}, STORED, default_payload=RAW)
    assert rep["applied"] == []
    assert any("not a real metadata leaf" in r for r in rep["rejected"])
    assert any("empty morph path" in r for r in rep["rejected"])
    assert _b(built) == _b(_full_emit({}, []))


def test_chrome_morph_rejected_by_produce_and_by_gate():
    # produce-level chrome token
    built, rep = morph_apply({"title": "() => boom"}, STORED, default_payload=RAW)
    assert built["title"] == "Feeder Load" and any("chrome" in r for r in rep["rejected"])
    # gate-level chrome token (produce's smaller list misses rgba( — the imported gate catches + enforce reverts)
    built2, rep2 = morph_apply({"title": "rgba(0,0,0)"}, STORED, default_payload=RAW)
    assert built2["title"] == "Feeder Load"
    assert rep2["conforms"] is True and "title" in rep2["reverted"]


def test_regimeA_byte_equivalence_with_full_emit_contract():
    """The full contract: AI retypes EVERYTHING, declares `title` in _morphed but ALSO drifts `unit` undeclared.
    Live path applies only the declared morph. morph-map with the DECLARED map must be byte-identical."""
    ai_meta = copy.deepcopy(STORED)
    ai_meta["title"] = "DG Focus — Load"             # declared
    ai_meta["unit"] = "MW"                           # authored but UNDECLARED → live path silently reverts
    full = _full_emit(ai_meta, ["title"])
    assert full["title"] == "DG Focus — Load" and full["unit"] == "kW"
    built, rep = morph_apply({"title": "DG Focus — Load"}, STORED, default_payload=RAW)
    assert _b(built) == _b(full)


def test_regimeB_expressed_intent_ships_under_morphmap():
    """Under morph-map, expressing the `unit` change = declaring it — the intent the full contract lost now ships
    (still through the same gates)."""
    built, rep = morph_apply({"title": "DG Focus — Load", "unit": "MW"}, STORED, default_payload=RAW)
    assert rep["conforms"] is True
    assert built["unit"] == "MW" and built["title"] == "DG Focus — Load"


def test_flag_default_off_and_unwired(monkeypatch):
    import config.app_config as ac
    import layer2.emit.morphmap.mode as mode
    monkeypatch.setattr(ac, "_load", lambda: {})                       # no DB row → code default 'off'
    assert mode.mode() == "off" and mode.enabled() is False
    monkeypatch.setattr(ac, "_load", lambda: {"emit.morphmap_mode": ("on", "text")})
    assert mode.enabled() is True
    # FENCE: the live emit path must NOT reference the morph-map package until post-cert wiring
    import os
    import layer2.emit.emit as emit_mod
    import layer2.build as build_mod
    for m in (emit_mod, build_mod):
        src = open(os.path.abspath(m.__file__), errors="replace").read()
        assert "morphmap" not in src, f"{m.__name__} references morphmap — default path must stay untouched"


def test_prompt_contract_file():
    import os
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "layer2", "emit", "morphmap", "prompt.md")
    txt = open(p).read()
    assert '"morphs"' in txt and "data_instructions" in txt and "answerability" in txt and "data_note" in txt
    assert "exact_metadata" in txt                    # says explicitly there is NO exact_metadata key
    assert "{{" not in txt                            # no unfilled placeholders
