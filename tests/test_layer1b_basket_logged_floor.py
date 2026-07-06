"""tests/test_layer1b_basket_logged_floor.py — SEAM 4: the 1b basket ALWAYS carries the meter's real LOGGED columns
(even when the basket AI drops them), a genuinely-empty column stays has_data=false (honest-blank, never fabricated),
and a present-but-empty avg column whose per-phase siblings ARE logged is flagged derivable=avg_from_phase.

Non-live: the DB/schema reads (col_dict, window_nonnull) and the LLM (call_qwen) are all mocked with a deterministic
mfm171-shaped fixture, so no live Qwen call and no live neuract dependency. [SEAM 4: logged floor + avg-from-phase]"""
from unittest.mock import patch

from layer1b.basket import column_basket as cb

TABLE = "gic_15_n3_pcc_01_transformer_01_se"
ASSET = {"table": TABLE, "class": "Transformer", "name": "PCC-01 Transformer-01"}

# a mfm171-shaped column dictionary: [column_name, label, kind, unit]. Includes logged phases + a logged LN avg,
# empty aggregate avgs (current_avg, voltage_ll_avg), and a 0/1 event flag that must NEVER ride into the floor.
_DICT = [
    ["voltage_r_n", "Voltage R N", "raw", "V"],
    ["voltage_y_n", "Voltage Y N", "raw", "V"],
    ["voltage_b_n", "Voltage B N", "raw", "V"],
    ["voltage_ry", "Voltage Ry", "raw", "V"],
    ["voltage_yb", "Voltage Yb", "raw", "V"],
    ["voltage_br", "Voltage Br", "raw", "V"],
    ["voltage_avg", "Voltage Avg", "raw", "V"],          # LN avg — LOGGED here
    ["voltage_ll_avg", "Voltage Ll Avg", "raw", "V"],    # LL avg — EMPTY, phases logged -> derivable
    ["current_r", "Current R", "raw", "A"],
    ["current_y", "Current Y", "raw", "A"],
    ["current_b", "Current B", "raw", "A"],
    ["current_avg", "Current Avg", "raw", "A"],          # EMPTY, phases logged -> derivable
    ["active_power_total_kw", "Active Power Total Kw", "raw", "kW"],
    ["reactive_energy_import_kvarh", "Reactive Energy Import Kvarh", "raw", "kVArh"],  # genuinely EMPTY, no phases
    ["current_imbalance_event_active", "Current Imbalance Event Active", "event", ""],  # 0/1 FLAG — never a floor column
]

# window has_data: everything logged EXCEPT the three empties (current_avg, voltage_ll_avg, reactive_energy_import_kvarh).
_LOGGED = {c[0] for c in _DICT} - {"current_avg", "voltage_ll_avg", "reactive_energy_import_kvarh"}


def _run(ai_feasible, ai_probable=None, prompt="voltage and current health"):
    ai = {"feasible": ai_feasible, "probable": ai_probable or []}
    with patch.object(cb, "col_dict", return_value=[list(c) for c in _DICT]), \
         patch.object(cb, "window_nonnull", return_value=set(_LOGGED)), \
         patch.object(cb, "call_qwen", return_value=ai):
        return cb.build_basket(prompt, ASSET)


def _col(basket, name):
    return next((c for c in basket["columns"] if c["column"] == name), None)


def test_logged_voltage_included_even_when_ai_drops_it():
    """THE BUG: the AI returns only current+power (drops every voltage col). The logged floor must still put the logged
    voltage columns in the basket, with has_data=true — Layer 2 can bind them instead of false-blanking."""
    b = _run(["current_r", "current_y", "current_b", "active_power_total_kw"])
    names = {c["column"] for c in b["columns"]}
    # logged voltage present despite the AI narrowing
    assert "voltage_r_n" in names and "voltage_avg" in names
    assert _col(b, "voltage_r_n")["has_data"] is True
    assert _col(b, "voltage_avg")["has_data"] is True
    # the AI's own picks are still there (union, not replace)
    assert {"current_r", "current_y", "current_b", "active_power_total_kw"} <= names


def test_before_after_floor_vs_ai_only():
    """The floor is the fix: with the floor OFF the basket is the narrow AI set; with it ON (default) it carries every
    logged metric column. Proves the 28->N jump is the floor, not the AI."""
    ai = ["current_r", "active_power_total_kw"]
    # turn the floor OFF via the cfg knob (column_basket imports cfg by name -> patch cb.cfg); all other cfg keys default.
    with patch.object(cb, "cfg", side_effect=lambda k, d: False if k == "layer1b.basket.include_logged_floor" else d):
        off = _run(ai)
    on = _run(ai)                                   # default include_logged_floor=true
    assert off["n_columns"] == 2                     # AI-only
    assert on["n_columns"] > off["n_columns"]        # floor rescued the logged columns
    assert any(c["column"].startswith("voltage") for c in on["columns"])


def test_empty_column_is_honest_blank():
    """A genuinely-empty column (no rows, no logged phases) stays has_data=false so downstream honest-blanks it — never
    fabricated, never flagged derivable."""
    b = _run(["reactive_energy_import_kvarh"])       # AI asks for the empty column explicitly
    c = _col(b, "reactive_energy_import_kvarh")
    assert c is not None and c["has_data"] is False
    assert "derivable" not in c                        # no phase source -> not derivable, stays honest-blank


def test_avg_from_phase_flagged_when_phases_logged():
    """current_avg / voltage_ll_avg are EMPTY but their per-phase siblings ARE logged -> flag derivable=avg_from_phase
    with the logged phase source columns, has_data still false (recovery pointer, not a fabricated value)."""
    b = _run(["current_avg", "voltage_ll_avg"], prompt="average current and average line-line voltage")
    ca = _col(b, "current_avg")
    assert ca["has_data"] is False and ca.get("derivable") == "avg_from_phase"
    assert set(ca["derive_sources"]) == {"current_r", "current_y", "current_b"}
    lla = _col(b, "voltage_ll_avg")
    assert lla["has_data"] is False and lla.get("derivable") == "avg_from_phase"
    assert set(lla["derive_sources"]) == {"voltage_ry", "voltage_yb", "voltage_br"}


def test_event_flag_never_in_logged_floor():
    """A 0/1 event flag (current_imbalance_event_active, kind='event') must NOT ride into the basket via the floor — it
    is not a phase current. It only appears if the AI explicitly picks it (event cards), never as a floor freebie."""
    b = _run(["current_r"])                            # AI does NOT ask for the flag
    assert _col(b, "current_imbalance_event_active") is None


def test_logged_avg_not_flagged_derivable():
    """voltage_avg IS logged here -> has_data=true and NOT flagged derivable (only present-but-empty avgs are)."""
    b = _run(["voltage_avg"])
    c = _col(b, "voltage_avg")
    assert c["has_data"] is True and "derivable" not in c
