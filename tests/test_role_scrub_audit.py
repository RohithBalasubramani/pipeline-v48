"""tests/test_role_scrub_audit.py -- OFFLINE unit tests for scripts/audit_role_scrub_coverage.py (T1-13).

No DB, no LLM. We load the audit module directly by path (it is NOT a package, and importing it has no side effects
because every DB/LLM import is lazy). The survivor walk is exercised with the REAL
grounding.role_scrub.scrub_active_string_leaves, with grounding.role_scrub.vocab monkeypatched to None so the scrub
resolves to its CODE-DEFAULT vocabularies with zero cmd_catalog access (honest-degrade path)."""
import importlib.util
import os

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_MODPATH = os.path.join(os.path.dirname(_HERE), "scripts", "audit_role_scrub_coverage.py")


def _load_audit_module():
    spec = importlib.util.spec_from_file_location("audit_role_scrub_coverage_undertest", _MODPATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


AUD = _load_audit_module()


@pytest.fixture
def code_default_scrub(monkeypatch):
    """The real role scrub, forced onto its code-default vocab (vocab() -> None) so the test never touches a DB."""
    import grounding.role_scrub as rs
    monkeypatch.setattr(rs, "vocab", lambda *a, **k: None)
    return rs.scrub_active_string_leaves


# -- survivor collection --------------------------------------------------------------------------------

def _fixture_tree():
    return {
        # active-state object: BOTH strings are blanked by the scrub (status parent + label key; tone suffix).
        "status": {"label": "SCRUBBED_LABEL", "tone": "warn"},
        # dictionary subtree ('vocab' substring): kept byte-identical, must NOT be collected.
        "statusVocab": {"opt": "DICT_KEPT_VALUE"},
        # BLIND SPOT: 'verdict' under the unrecognised parent 'customWidget' falls through every vocab rule -> survives.
        # 'count' is numeric (skipped); 'unit' is chrome that also survives (a legit survivor the LLM would reject).
        "customWidget": {"verdict": "BLINDSPOT_FABRICATION", "count": "123", "unit": "kW"},
    }


def test_blindspot_leaf_is_collected(code_default_scrub):
    survivors = AUD.collect_survivors("story-1", _fixture_tree(), code_default_scrub)
    values = {s["value"] for s in survivors}
    # the fabricated string under an unrecognised active key is surfaced ...
    assert "BLINDSPOT_FABRICATION" in values
    # ... and it is reported with the exact role slot (parent + key) a role_scrub.* list would test against.
    blindspot = next(s for s in survivors if s["value"] == "BLINDSPOT_FABRICATION")
    assert blindspot["key"] == "verdict"
    assert blindspot["parent_key"] == "customwidget"
    assert blindspot["parent_chain"] == ["customwidget"]
    assert blindspot["path"] == "customWidget.verdict"
    assert blindspot["story_id"] == "story-1"


def test_scrubbed_and_dictionary_leaves_not_collected(code_default_scrub):
    survivors = AUD.collect_survivors("story-1", _fixture_tree(), code_default_scrub)
    values = {s["value"] for s in survivors}
    # a legitimately-scrubbed active-state leaf (status.label / status.tone) never survives the parallel walk
    assert "SCRUBBED_LABEL" not in values
    assert "warn" not in values
    # a dictionary-subtree leaf (statusVocab.*) is skipped exactly as the scrub keeps it
    assert "DICT_KEPT_VALUE" not in values
    assert not any("statusvocab" in s["parent_chain"] for s in survivors)


def test_numeric_string_not_collected(code_default_scrub):
    survivors = AUD.collect_survivors("story-1", _fixture_tree(), code_default_scrub)
    assert "123" not in {s["value"] for s in survivors}


def test_collector_does_not_mutate_input(code_default_scrub):
    tree = _fixture_tree()
    AUD.collect_survivors("story-1", tree, code_default_scrub)
    # the scrub runs on a deep copy -- the caller's tree keeps its (fabricated) originals intact
    assert tree["status"]["label"] == "SCRUBBED_LABEL"


def test_fake_scrub_injection_collects_only_unblanked():
    """collect_survivors is pure over its injected scrub: a fake that blanks nothing -> every non-numeric string leaf
    surfaces; the dictionary skip still holds without any role_scrub import."""
    def _noop_scrub(tree, ph):
        return tree
    tree = {"a": {"x": "keepme"}, "myVocab": {"opt": "dict_kept"}}
    survivors = AUD.collect_survivors("s", tree, _noop_scrub, dict_keys={"legend"})
    values = {s["value"] for s in survivors}
    assert "keepme" in values
    assert "dict_kept" not in values          # 'myvocab' matched by the 'vocab' substring rule


# -- dedup --------------------------------------------------------------------------------------------

def test_dedup_by_parent_key_and_value_and_cap():
    survivors = [
        {"parent_key": "customwidget", "key": "verdict", "value": "Elevated"},
        {"parent_key": "customwidget", "key": "verdict", "value": "Elevated"},   # dup
        {"parent_key": "customwidget", "key": "verdict", "value": "Normal"},     # distinct value
        {"parent_key": "panel", "key": "verdict", "value": "Elevated"},          # distinct parent
    ]
    unique = AUD.dedup_survivors(survivors)
    assert len(unique) == 3
    assert AUD.dedup_survivors(survivors, limit=2) == unique[:2]


# -- post-validation ---------------------------------------------------------------------------------

def _survivors_for_validation():
    return [
        {"story_id": "s", "path": "customWidget.verdict", "parent_chain": ["customwidget"],
         "parent_key": "customwidget", "key": "verdict", "value": "Elevated"},
    ]


_SEEDED = {"role_scrub.active_value_keys", "role_scrub.active_state_parents", "role_scrub.global_active_keys"}
_DICT_KEYS = {"statusvocab", "legend", "palette"}


def test_post_validate_keeps_valid_key_and_parent_proposals():
    survivors = _survivors_for_validation()
    proposals = [
        {"index": 0, "live_assertion": True, "rule_row": "role_scrub.active_value_keys", "token": "verdict"},
        {"index": 0, "live_assertion": True, "rule_row": "role_scrub.active_state_parents", "token": "customWidget"},
    ]
    kept = AUD.post_validate(proposals, survivors, _SEEDED, dict_keys=_DICT_KEYS)
    got = {(k["rule_row"], k["token"]) for k in kept}
    assert got == {
        ("role_scrub.active_value_keys", "verdict"),
        ("role_scrub.active_state_parents", "customwidget"),   # parent tokens are accepted + lowercased
    }


def test_post_validate_drops_unknown_rule_row():
    survivors = _survivors_for_validation()
    proposals = [{"live_assertion": True, "rule_row": "role_scrub.made_up_row", "token": "verdict"}]
    assert AUD.post_validate(proposals, survivors, _SEEDED, dict_keys=_DICT_KEYS) == []


def test_post_validate_drops_invented_token():
    survivors = _survivors_for_validation()
    proposals = [{"live_assertion": True, "rule_row": "role_scrub.active_value_keys", "token": "ghost_token"}]
    assert AUD.post_validate(proposals, survivors, _SEEDED, dict_keys=_DICT_KEYS) == []


def test_post_validate_drops_dictionary_subtree_collision():
    survivors = _survivors_for_validation() + [
        {"story_id": "s", "path": "x.statusVocab", "parent_chain": ["x"], "parent_key": "x",
         "key": "statusvocab", "value": "whatever"}]
    proposals = [{"live_assertion": True, "rule_row": "role_scrub.active_value_keys", "token": "statusVocab"}]
    assert AUD.post_validate(proposals, survivors, _SEEDED, dict_keys=_DICT_KEYS) == []


def test_post_validate_drops_non_live_assertion():
    survivors = _survivors_for_validation()
    proposals = [{"live_assertion": False, "rule_row": "role_scrub.active_value_keys", "token": "verdict"}]
    assert AUD.post_validate(proposals, survivors, _SEEDED, dict_keys=_DICT_KEYS) == []


# -- SQL emission --------------------------------------------------------------------------------------

def test_build_sql_is_fully_commented_and_merges():
    kept = [{"live_assertion": True, "rule_row": "role_scrub.active_value_keys", "token": "verdict"}]
    current = {"role_scrub.active_value_keys": ["label", "tone"]}
    sql = AUD.build_sql(kept, current, "unit-tag")
    # every non-blank line is a SQL comment -> nothing can be executed by accident
    for line in sql.splitlines():
        assert line == "" or line.startswith("--"), line
    assert "REVIEW before applying; re-run build_stripped_payloads.py after" in sql
    assert "vocab.role_scrub.active_value_keys" in sql
    # the merged list carries BOTH the current tokens and the new one
    assert '"label"' in sql and '"tone"' in sql and '"verdict"' in sql
    assert "unit-tag" in sql


def test_build_sql_empty_when_no_additions():
    sql = AUD.build_sql([], {}, "empty-tag")
    assert "(no validated additions this run)" in sql
    for line in sql.splitlines():
        assert line == "" or line.startswith("--")
