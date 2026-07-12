"""tests/test_prompt_corpus.py — the DB-driven prompt corpus (validation/corpus/): store fail-open, slot grounding,
mutation families, expect-widening, determinism, budgets. OFFLINE by construction: data.db_client.q is monkeypatched
in every test that could reach it — no live cmd_catalog needed."""
import random

import pytest

from sweep.corpus import fill, generate as gen
from sweep.corpus import store as store_mod
from sweep.corpus.mutate import expand_case, mutations
from sweep.corpus.mutators import REGISTRY
from sweep.corpus.templates import defaults


def _mk_assets():
    rows, i = [], 0
    for cls, prefix, n in (("UPS", "UPS", 5), ("DG", "DG", 3), ("Transformer", "Transformer", 2),
                           ("Chiller", "Chiller", 5)):
        for k in range(1, n + 1):
            i += 1
            rows.append({"id": i, "name": f"GIC-0{k}-N{k}-{prefix}-0{k} MFM", "table": f"t{i}", "cls": cls})
    return rows


def _fake_universe():
    assets = _mk_assets()
    by_class: dict = {}
    for a in assets:
        by_class.setdefault(a["cls"], []).append(a)
    return {"assets": assets, "by_class": by_class, "unique_names": assets,
            "homonym_tokens": ["UPS-1", "DG-2"],
            "panel_aliases": [("pcc-1a", "PCC-Panel-1"), ("pcc-1b", "PCC-Panel-1"), ("pcc-2", "PCC-Panel-2")],
            "pages": [], "cards": [], "card_handling": {}}


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    """No test here may touch a live DB; store cache cleared around every test (conftest clears cfg's)."""
    import data.db_client as dbc
    monkeypatch.setattr(dbc, "q", lambda db, sql: (_ for _ in ()).throw(RuntimeError("offline test")))
    store_mod.reload()
    yield
    store_mod.reload()


def test_store_fails_open_to_code_defaults():
    s = store_mod.store()
    assert s["source"] == "code-default"
    assert len(s["templates"]) >= 40 and len(s["categories"]) >= 15
    assert {"metric", "window", "conv_prefix", "conv_suffix"} <= set(s["vocab"])


def test_store_reads_db_rows(monkeypatch):
    import data.db_client as dbc

    def fake_q(db, sql):
        if "prompt_category" in sql:
            return [["single_asset", "cards", "50"]]
        if "prompt_template" in sql:
            return [["single_asset.t1", "single_asset", "<metric> for <asset>", "", "2"]]
        return [["metric", "energy and power", ""], ["window", "today", ""]]

    monkeypatch.setattr(dbc, "q", fake_q)
    store_mod.reload()
    s = store_mod.store()
    assert s["source"] == "db"
    assert s["categories"]["single_asset"]["budget"] == 50
    assert s["templates"][0]["expect"] is None            # '' round-trips to None (inherit category expect)


def test_budgets_promise_tens_of_thousands():
    total = sum(c["budget"] for c in defaults()["categories"].values())
    assert total >= 20000, "default budgets are the corpus-size promise"


def test_fill_grounds_class_appropriate(monkeypatch):
    d = defaults()
    tmpl = {"tkey": "single_asset.metric_for_asset", "category": "single_asset",
            "template": "<metric> for <asset>", "expect": None, "weight": 3}
    cases = fill.ground(tmpl, "cards", _fake_universe(), d["vocab"], 48, 500)
    assert cases and all("<" not in c["prompt"] for c in cases)
    for c in cases:
        assert c["meta"]["asset"] in c["prompt"]
        if c["meta"]["metric"] == "fuel efficiency":
            assert c["meta"]["cls"] == "DG"               # class-restricted metric never leaks to other classes
    assert any(c["meta"]["cls"] == "DG" for c in cases)


def test_fill_compare_distinct_same_class():
    d = defaults()
    tmpl = {"tkey": "compare_2.compare_metric", "category": "compare_2",
            "template": "compare <asset1> and <asset2> <metric>", "expect": None, "weight": 1}
    cases = fill.ground(tmpl, "compare:2", _fake_universe(), d["vocab"], 48, 40)
    assert cases
    for c in cases:
        a, b = c["meta"]["assets"]
        assert a != b and a in c["prompt"] and b in c["prompt"]
        assert "+" not in c["meta"]["cls"]                # same-class lane

    mixed = {"tkey": "compare_mixed.compare_and", "category": "compare_mixed",
             "template": "compare <asset1> and <asset2> <metric>", "expect": None, "weight": 1}
    mcases = fill.ground(mixed, "compare:2|picker", _fake_universe(), d["vocab"], 48, 20)
    assert mcases and all("+" in c["meta"]["cls"] for c in mcases)


def test_fill_unknown_slot_is_loud():
    tmpl = {"tkey": "x.bad", "category": "single_asset", "template": "<metrc> for <asset>",
            "expect": None, "weight": 1}
    with pytest.raises(ValueError, match="metrc"):
        fill.ground(tmpl, "cards", _fake_universe(), defaults()["vocab"], 48, 5)


def test_short_token_prefers_last_unit():
    assert fill._short_token("GIC-21-N4-UPS-08") == "UPS-8"
    assert fill._short_token("DG-1 MFM") == "DG-1"


def test_mutator_families_deterministic():
    vocab = defaults()["vocab"]
    ctx = {"asset": "GIC-01-N1-UPS-01 MFM", "cls": "UPS", "metric": "power factor",
           "aliases": ["pcc-1b"], "vocab": vocab}
    text = "power factor for GIC-01-N1-UPS-01 MFM"
    for name, mod in REGISTRY.items():
        v1 = mod.variants(text, ctx, random.Random(7))
        v2 = mod.variants(text, ctx, random.Random(7))
        assert v1 == v2, f"{name} not deterministic"
        for v in v1:
            assert v["text"] != text and v["text"].encode("ascii", "strict")
            assert set(v) == {"name", "text", "weakens_pin"}


def test_expand_widens_only_pin_weakening():
    base = {"id": "abc123", "category": "single_asset", "prompt": "power factor for GIC-01-N1-UPS-01 MFM",
            "expect": "cards", "meta": {"asset": "GIC-01-N1-UPS-01 MFM", "cls": "UPS"}}
    out = expand_case(base, defaults()["vocab"], seed=48, k=50)
    assert out
    widened = [c for c in out if c["expect"] == "cards|picker"]
    strict = [c for c in out if c["expect"] == "cards"]
    assert widened and strict
    assert all(c["meta"]["mutation"].split(":")[0] in ("spelling", "partial", "aliasing", "abbrev")
               for c in widened)
    assert all(c["meta"]["base_id"] == "abc123" for c in out)
    assert len({c["prompt"] for c in out}) == len(out)    # no duplicate variant texts


def test_expand_no_name_restricts_to_safe_families():
    base = {"id": "k1", "category": "knowledge", "prompt": "what is reactive power",
            "expect": "knowledge", "meta": {}}
    out = expand_case(base, defaults()["vocab"], seed=48, k=50)
    assert out and all(c["meta"]["mutation"].split(":")[0] in ("casing", "conversational") for c in out)
    assert all(c["expect"] == "knowledge" for c in out)


def test_mutations_backcompat_probe_set():
    out = mutations("GIC-01 UPS-01 MFM", random.Random(48))
    names = {n for n, _ in out}
    assert {"lowercase", "uppercase", "strip_punct", "squash_space"} <= names


def test_generate_deterministic_and_budgeted(monkeypatch):
    d = defaults()
    for c in d["categories"].values():
        c["budget"] = 40                                  # tiny budgets keep the test fast
    monkeypatch.setattr(gen, "store", lambda: d)
    monkeypatch.setattr(gen, "universe", _fake_universe)
    one, two = gen.generate(), gen.generate()
    assert one == two, "generation must be byte-deterministic"
    assert len(one) > 200
    by_cat: dict = {}
    for c in one:
        by_cat[c["category"]] = by_cat.get(c["category"], 0) + 1
        assert set(c) == {"id", "category", "prompt", "expect", "meta"}
    assert all(n <= 40 for n in by_cat.values())
    assert len({c["id"] for c in one}) == len(one)        # ids unique corpus-wide
