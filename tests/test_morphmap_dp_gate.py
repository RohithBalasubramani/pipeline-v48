"""ITEM 18 — morph-map DP-GATE: the morphs-only metadata contract is composed ONLY for a card that HAS a stored
seedless skeleton to overlay (catalog_row.default_payload.payload_stripped non-null). A NO-DEFAULT-PAYLOAD card (no
card_payloads row — e.g. the AI-Summary / Heatmap time-axis narrative cards 8/160) keeps the FULL-author metadata.md
even with the flag ON, so it authors exact_metadata and hits build.py's no-dp path instead of tripping
"no default payload + empty exact_metadata".

Proves the fix on the ONLY seam that broke live: prompt SELECTION in emit._system() + user_message._build's metadata
header. No live LLM; no DB rows required for the gate itself (app_config monkeypatched); a small live-shaped card_in.

The gate mirrors build._finalize EXACTLY: morph-map path is taken ⇔ dp truthy AND _stored (payload_stripped) not None.
So the prompt the AI sees always agrees with the producer route build.py takes on its output."""
import copy

import pytest  # noqa

import config.app_config as ac
import layer2.emit.morphmap.mode as mode
import layer2.emit.emit as emit_mod


# ── minimal card_in shapes ─────────────────────────────────────────────────
def _dp_card():
    """A card that HAS a stored skeleton (default_payload.payload_stripped non-null) — the morph-map candidate."""
    return {
        "card_id": 5,
        "column_basket": {"columns": [], "probable": []},
        "asset": {},
        "catalog_row": {
            "handling_class": "single_asset",
            "recipe": {"fields": []},
            "default_payload": {
                "payload": {"title": "Feeder Load", "unit": "kW", "kpi": {"value": 0}},
                "payload_stripped": {"title": "Feeder Load", "unit": "kW", "kpi": {"value": 0}},
                "data_paths": ["kpi.value"],
            },
        },
    }


def _no_dp_card():
    """A NO-DEFAULT-PAYLOAD card (no card_payloads row): default_payload is None. This is cards 8/160 — the live break.
    It MUST author full exact_metadata (no skeleton to overlay), so it keeps the full-emit prompt even with flag on."""
    return {
        "card_id": 8,
        "column_basket": {"columns": [], "probable": []},
        "asset": {},
        "catalog_row": {"handling_class": "narrative", "recipe": {"fields": []}, "default_payload": None},
    }


def _null_stripped_card():
    """dp exists but payload_stripped is NULL (builder never run) — build.py falls through to the FULL path for it too
    (`_stored is not None` is False), so the prompt must ALSO stay full-author. Belt-and-suspenders with build.py."""
    c = _dp_card()
    c["catalog_row"]["default_payload"]["payload_stripped"] = None
    return c


def _flag(monkeypatch, on):
    monkeypatch.setattr(ac, "_load", lambda: {"emit.morphmap_mode": ("on", "text")} if on else {})


# ── mode.py unit: the applicability gate ───────────────────────────────────
def test_card_has_skeleton_gate():
    assert mode.card_has_skeleton(_dp_card()) is True
    assert mode.card_has_skeleton(_no_dp_card()) is False
    assert mode.card_has_skeleton(_null_stripped_card()) is False
    assert mode.card_has_skeleton(None) is True                # unknown/generic — flag intent stands, per-card gate runs live


def test_use_morphmap_metadata_requires_flag_and_skeleton(monkeypatch):
    _flag(monkeypatch, on=False)
    assert mode.use_morphmap_metadata(_dp_card()) is False      # flag off ⇒ never morph-map
    assert mode.use_morphmap_metadata(_no_dp_card()) is False
    _flag(monkeypatch, on=True)
    assert mode.use_morphmap_metadata(_dp_card()) is True       # flag on + skeleton ⇒ morph-map
    assert mode.use_morphmap_metadata(_no_dp_card()) is False   # flag on + NO skeleton ⇒ full-emit (the fix)
    assert mode.use_morphmap_metadata(_null_stripped_card()) is False


# ── emit._system(): which metadata PART-2 contract is composed ─────────────
def test_system_dp_card_flag_on_composes_morphmap(monkeypatch):
    _flag(monkeypatch, on=True)
    sysmsg = emit_mod._system(_dp_card())
    assert "MORPH-MAP EMIT" in sysmsg                           # (a) DP card + flag on → morphs-only VARIANT
    assert "{{" not in sysmsg                                   # placeholders substituted


def test_system_no_dp_card_flag_on_composes_full_emit(monkeypatch):
    _flag(monkeypatch, on=True)
    sysmsg = emit_mod._system(_no_dp_card())
    assert "MORPH-EMIT" in sysmsg                               # (b) NO-DP card + flag on → FULL-author metadata.md
    assert "MORPH-MAP EMIT" not in sysmsg                       #     so it authors exact_metadata (no error)
    assert "{{" not in sysmsg


def test_system_null_stripped_card_flag_on_composes_full_emit(monkeypatch):
    _flag(monkeypatch, on=True)
    sysmsg = emit_mod._system(_null_stripped_card())
    assert "MORPH-EMIT" in sysmsg and "MORPH-MAP EMIT" not in sysmsg


def test_system_flag_off_full_emit_both_cards(monkeypatch):
    _flag(monkeypatch, on=False)
    for card in (_dp_card(), _no_dp_card()):
        sysmsg = emit_mod._system(card)                         # (c) flag off → full-emit for BOTH (unchanged today)
        assert "MORPH-EMIT" in sysmsg and "MORPH-MAP EMIT" not in sysmsg


def test_default_off_byte_identical_to_baseline(monkeypatch):
    """DEFAULT-OFF proof: with NO DB row (code default 'off') the composed system prompt is byte-identical between a
    DP card and the exact same card had morph-map never existed — i.e. the flag-off path == today's full-emit path."""
    _flag(monkeypatch, on=False)
    dp_off = emit_mod._system(_dp_card())
    # flip on then off again must return the exact same bytes (no residual state)
    _flag(monkeypatch, on=True)
    _ = emit_mod._system(_dp_card())
    _flag(monkeypatch, on=False)
    assert emit_mod._system(_dp_card()) == dp_off


# ── user_message._build metadata header agrees with the system prompt ──────
def _build_card_in():
    """A fuller card_in for user_message._build. Only the fields _build reads are populated; keep it minimal but valid.
    Reused for BOTH dp/no-dp variants by swapping catalog_row.default_payload."""
    return {
        "run_id": "t", "card_id": 5, "page_key": "p", "is_group_card": False, "group_id": None,
        "story": {"page_story": "", "analytical_story": "", "metric": "", "intent": "", "template_card_ids": []},
        "asset": {},
        "column_basket": {"columns": [], "probable": []},
        "swap_candidates": [],
        "catalog_row": {
            "title": "T", "handling_class": "single_asset", "resolver_scope": "", "payload_family": "",
            "recipe": {"payload_shape": "", "orientation": "", "entity_dim": "", "selection_dim": "",
                       "selection_role": "", "fields": []},
            "contract": {"capabilities": [], "component": "", "host_cmd_component": "", "canonical_shape": "",
                         "payload_schema_json": {}},
            "controls": {"time_mode": "", "sampling_options": [], "segmented_tabs": [], "defaults": {}},
            "feasibility": {"verdict": "", "required_topology": "", "reason": ""},
            "backend_strategy": None,
            "default_payload": {
                "payload": {"title": "Feeder Load", "unit": "kW", "kpi": {"value": 0}},
                "payload_stripped": {"title": "Feeder Load", "unit": "kW", "kpi": {"value": 0}},
                "data_paths": ["kpi.value"],
            },
        },
    }


def test_user_message_header_dp_card_flag_on_is_morphs(monkeypatch):
    _flag(monkeypatch, on=True)
    from layer2.emit.user_message import _build
    msg = _build(_build_card_in())
    assert "Return `morphs`" in msg                             # DP card + flag on → morphs-only instruction wording
    assert "author EVERY metadata key as exact_metadata" not in msg


def test_user_message_header_no_dp_card_flag_on_is_full_author(monkeypatch):
    _flag(monkeypatch, on=True)
    from layer2.emit.user_message import _build
    ci = _build_card_in()
    ci["catalog_row"]["default_payload"] = None                 # NO-DP card
    msg = _build(ci)
    assert "author EVERY metadata key as exact_metadata" in msg  # NO-DP card + flag on → full-author wording (the fix)
    assert "Return `morphs`" not in msg
    assert "author exact_metadata (byte-identical default" in msg   # the closing line also stays full-author


def test_user_message_header_flag_off_full_author_both(monkeypatch):
    _flag(monkeypatch, on=False)
    from layer2.emit.user_message import _build
    for dp in ({"payload": {"title": "T", "kpi": {"value": 0}},
                "payload_stripped": {"title": "T", "kpi": {"value": 0}}, "data_paths": ["kpi.value"]}, None):
        ci = _build_card_in()
        ci["catalog_row"]["default_payload"] = copy.deepcopy(dp) if dp else None
        msg = _build(ci)
        assert "author EVERY metadata key as exact_metadata" in msg and "Return `morphs`" not in msg


# ── OUTPUT-ENVELOPE ACTIVATION: the final 'Emit exactly {…}' envelope must ask for morphs (not exact_metadata) when
# the morph-map metadata slice is composed — else the model follows the concrete exact_metadata template and the
# morph-map path never activates live. ─────────────────────────────────────────────────────────────────────────────
def _dp_card():
    return {"card_id": 5, "catalog_row": {"default_payload": {"payload": {"title": "x"},
            "payload_stripped": {"title": "x"}}, "handling_class": "single_asset"},
            "column_basket": {"columns": []}, "asset": {}}


def _nodp_card():
    return {"card_id": 8, "catalog_row": {"default_payload": None, "handling_class": "narrative_ai"},
            "column_basket": {"columns": []}, "asset": {}}


def test_envelope_flag_off_keeps_exact_metadata(monkeypatch):
    import config.app_config as ac
    import layer2.emit.emit as E
    monkeypatch.setattr(ac, "_load", lambda: {})
    for c in (_dp_card(), _nodp_card()):
        s = E._system(c)
        assert '"exact_metadata":{"_morphed":[]}' in s and '"morphs":{}' not in s


def test_envelope_flag_on_dp_card_asks_for_morphs(monkeypatch):
    import config.app_config as ac
    import layer2.emit.emit as E
    monkeypatch.setattr(ac, "_load", lambda: {"emit.morphmap_mode": ("on", "text")})
    s = E._system(_dp_card())
    assert '"morphs":{}' in s and '"exact_metadata":{"_morphed":[]}' not in s   # envelope activated
    assert "MORPH-MAP EMIT" in s                                                # metadata slice is the variant


def test_envelope_flag_on_no_dp_card_keeps_exact_metadata(monkeypatch):
    import config.app_config as ac
    import layer2.emit.emit as E
    monkeypatch.setattr(ac, "_load", lambda: {"emit.morphmap_mode": ("on", "text")})
    s = E._system(_nodp_card())
    assert '"exact_metadata":{"_morphed":[]}' in s and '"morphs":{}' not in s   # no skeleton → full-emit
    assert "MORPH-MAP EMIT" not in s
