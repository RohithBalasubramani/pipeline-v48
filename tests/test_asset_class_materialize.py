"""tests/test_asset_class_materialize.py -- T1-8: the name-needle class tier is a DEAD last resort.

layer1b.resolve.asset_candidates._class_of resolves a row's class in three tiers:
  1. asset_type.code   (authoritative registry fact)
  2. lt_mfm_type.code  (trusted registry fact)
  3. _name_class(table) name-needle vocabulary  -- the LAST-RESORT fallback

Tiers 1/2 are the registry facts; when either resolves, the returned class is byte-identical to before and NO telemetry
is emitted. Reaching tier 3 means both registry facts missed for this row, i.e. the canonical class facts are
missing/stale -- so _class_of now records a throttled obs.failures.record('asset_candidates','name_class_fallback',
detail='<table>-><class>') note WHEN the fallback actually fires, so the future registry class-column backfill can be
targeted. The recorded telemetry is additive: the class VALUE _class_of returns is unchanged.

Offline / hermetic: the class maps are forced via a monkeypatch of the module's OWN _class_code_maps binding, and
obs.failures.record is monkeypatched to a capture list (_class_of does `from obs.failures import record` at call time,
so patching the source attribute is picked up). No live DB, no LLM. The module-level throttle set is cleared per test so
ordering never changes an outcome."""
import obs.failures as _failures
import layer1b.resolve.asset_candidates as ac


def _capture(monkeypatch):
    """Force a clean throttle + a capture list for obs.failures.record; return the list of (args, kwargs)."""
    ac._NAME_CLASS_NOTED.clear()
    calls = []
    monkeypatch.setattr(_failures, "record", lambda *a, **k: calls.append((a, k)) or {"ok": True})
    return calls


def _force_maps(monkeypatch, a_map, m_map):
    """Pin the (asset_type_code->class, mfm_type_code->class) maps _class_of reads through, hermetically."""
    monkeypatch.setattr(ac, "_class_code_maps", lambda: (a_map, m_map))


# -- tier 1: asset_type.code resolves => that class, NO telemetry ----------------------------------------------------
def test_asset_type_code_resolves_no_telemetry(monkeypatch):
    calls = _capture(monkeypatch)
    _force_maps(monkeypatch, {"dg": "DG"}, {})
    r = {"asset_type_code": "dg", "mfm_type_code": None, "table": "gic_30_ahu_1"}  # table would name-class to AHU

    assert ac._class_of(r) == "DG"                       # authoritative fact wins, byte-identical
    assert calls == []                                   # tier 1 never touches the fallback -> no note


# -- tier 2: only mfm_type.code resolves => that class, NO telemetry -------------------------------------------------
def test_mfm_type_code_resolves_no_telemetry(monkeypatch):
    calls = _capture(monkeypatch)
    _force_maps(monkeypatch, {}, {"apfc": "APFCR"})
    r = {"asset_type_code": None, "mfm_type_code": "apfc", "table": "gic_30_apfc_1"}  # 'apfc' needle would also hit

    assert ac._class_of(r) == "APFCR"                    # trusted fact wins over the name needle
    assert calls == []                                   # tier 2 never touches the fallback -> no note


# -- tier 3: NEITHER fact resolves but the name needle hits => name class + EXACTLY one telemetry note ----------------
def test_name_class_fallback_records_once(monkeypatch):
    calls = _capture(monkeypatch)
    _force_maps(monkeypatch, {}, {})                     # both registry facts miss -> forced onto the last-resort tier
    r = {"asset_type_code": None, "mfm_type_code": None, "table": "gic_30_ahu_1"}

    assert ac._class_of(r) == "AHU"                       # name-needle value, unchanged behavior
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args[:2] == ("asset_candidates", "name_class_fallback")
    assert kwargs.get("detail") == "gic_30_ahu_1->AHU"


# -- throttle: two _class_of calls for the SAME table record only ONCE ----------------------------------------------
def test_name_class_fallback_throttled_per_table(monkeypatch):
    calls = _capture(monkeypatch)
    _force_maps(monkeypatch, {}, {})
    r = {"asset_type_code": None, "mfm_type_code": None, "table": "gic_30_chiller_2"}

    assert ac._class_of(r) == "Chiller"
    assert ac._class_of(dict(r)) == "Chiller"            # same table, fresh dict -> value still returned
    assert len(calls) == 1                               # ...but the note fires only once per process

    # a DIFFERENT table still records (the throttle is per-table, not a global one-shot)
    assert ac._class_of({"asset_type_code": None, "mfm_type_code": None, "table": "gic_30_pump_9"}) == "Pump"
    assert len(calls) == 2
    assert calls[1][1].get("detail") == "gic_30_pump_9->Pump"
