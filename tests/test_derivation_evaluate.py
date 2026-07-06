"""tests/test_derivation_evaluate.py — the safe expression interpreter (derivations/evaluate.py).

Covers the three contract legs: (1) whitelisted arithmetic over ctx names (row / start.<col> / end.<col> /
nameplate.<key>), (2) missing/None/non-numeric input → None (honest-degrade, never fabricate), (3) injection attempts
(attributes, subscripts, calls outside the whitelist, dunders, comprehensions, strings) are REJECTED → None, never
executed. Pure unit tests — no DB, no live data."""
import math

from ems_exec.derivations.evaluate import evaluate


CTX = {
    "row": {
        "active_energy_import_kwh": 2500.0,
        "reactive_energy_import_kvarh": 1500.0,
        "active_power_total_kw": -180.7,
        "apparent_power_total_kva": 181.6,
        "power_factor_total": -0.999,
        "voltage_avg": 234.86667,
        "kpi_voltage_deviation_pct": -2.1388874,
        "nameplate:rated_kva": 600.0,
        "text_col": "hello",
    },
    "start_row": {"active_energy_import_kwh": 100.0, "reactive_energy_import_kvarh": 40.0},
    "end_row": {"active_energy_import_kwh": 250.5, "reactive_energy_import_kvarh": 90.0},
    "nameplate": {"rated_kva": 600.0},
}


# ── (1) arithmetic + name resolution ─────────────────────────────────────────────────────────────────────────────────
def test_literals_and_arithmetic():
    assert evaluate("1 + 2 * 3", {}) == 7.0
    assert evaluate("(1 + 2) * 3", {}) == 9.0
    assert evaluate("2 ** 3 / 4", {}) == 2.0
    assert evaluate("-5 + 1", {}) == -4.0


def test_bare_name_reads_row():
    assert evaluate("active_energy_import_kwh / 1000", CTX) == 2.5
    assert evaluate("round(active_energy_import_kwh / 1000, 2)", CTX) == 2.5


def test_whitelisted_functions():
    assert evaluate("sqrt(9)", {}) == 3.0
    assert evaluate("abs(active_power_total_kw)", CTX) == 180.7
    assert evaluate("min(1, abs(active_power_total_kw) / abs(apparent_power_total_kva))", CTX) == (
        min(1, abs(-180.7) / abs(181.6)))
    assert evaluate("max(3, 5, 1)", {}) == 5.0
    assert evaluate("round(2.678, 1)", {}) == 2.7


def test_start_end_window_names():
    assert evaluate("end.active_energy_import_kwh - start.active_energy_import_kwh", CTX) == 150.5
    assert evaluate("round(max(end.active_energy_import_kwh - start.active_energy_import_kwh, 0), 1)", CTX) == 150.5


def test_nameplate_names_both_forms():
    assert evaluate("nameplate.rated_kva", CTX) == 600.0
    # pseudo-column fallback: the executor injects nameplate values on the row as 'nameplate:<key>'
    ctx2 = {"row": dict(CTX["row"])}
    assert evaluate("nameplate.rated_kva", ctx2) == 600.0


def test_quadrature_identity():
    v = evaluate("sqrt(3 ** 2 + 4 ** 2)", {})
    assert v == 5.0


def test_matches_python_formula():
    # the migrated truePf expression mirrors round(min(1, |P|/|S|), 3)
    expr = "round(min(1, abs(active_power_total_kw) / abs(apparent_power_total_kva)), 3)"
    assert evaluate(expr, CTX) == round(min(1.0, abs(-180.7) / abs(181.6)), 3)


# ── (2) missing input / bad arithmetic → None (honest-degrade) ──────────────────────────────────────────────────────
def test_missing_row_column_degrades():
    assert evaluate("no_such_column + 1", CTX) is None


def test_none_valued_input_degrades():
    assert evaluate("dead_col * 2", {"row": {"dead_col": None}}) is None


def test_non_numeric_input_degrades():
    assert evaluate("text_col + 1", CTX) is None


def test_missing_window_endpoint_degrades():
    assert evaluate("end.active_energy_import_kwh - start.active_energy_import_kwh", {"row": {}}) is None


def test_missing_nameplate_degrades():
    assert evaluate("active_power_total_kw / nameplate.rated_kva", {"row": {"active_power_total_kw": 10.0}}) is None


def test_division_by_zero_degrades():
    assert evaluate("1 / 0", {}) is None
    assert evaluate("voltage_avg / max(1 + kpi_voltage_deviation_pct / 100, 0)",
                    {"row": {"voltage_avg": 230.0, "kpi_voltage_deviation_pct": -150.0}}) is None  # denom clamps → ÷0


def test_sqrt_negative_degrades():
    assert evaluate("sqrt(0 - 4)", {}) is None


def test_overflow_and_nonfinite_degrade():
    assert evaluate("10 ** 10 ** 10", {}) is None            # overflow → None, never raises
    assert evaluate("nanish", {"row": {"nanish": float("nan")}}) is None
    assert evaluate("infish", {"row": {"infish": float("inf")}}) is None


def test_empty_and_unparseable_degrade():
    assert evaluate("", CTX) is None
    assert evaluate(None, CTX) is None
    assert evaluate("1 +", CTX) is None
    assert evaluate("round(", CTX) is None


# ── (3) injection attempts are REJECTED (None, not executed) ────────────────────────────────────────────────────────
def test_rejects_dunder_attribute_access():
    assert evaluate("(1).__class__", CTX) is None
    assert evaluate("abs.__globals__", CTX) is None
    assert evaluate("start.__class__", CTX) is None           # dotted root is a NAME READ, never object attributes


def test_rejects_non_whitelisted_calls():
    assert evaluate("__import__('os').system('true')", CTX) is None
    assert evaluate("eval('1+1')", CTX) is None
    assert evaluate("exec('x=1')", CTX) is None
    assert evaluate("open('/etc/passwd')", CTX) is None
    assert evaluate("getattr(1, 'real')", CTX) is None
    assert evaluate("pow(2, 3)", CTX) is None                 # even harmless builtins outside the whitelist


def test_rejects_call_with_keywords_or_attribute_func():
    assert evaluate("round(1.234, ndigits=1)", CTX) is None   # keywords not in the grammar
    assert evaluate("math.sqrt(4)", CTX) is None              # attribute call → rejected


def test_rejects_subscripts_and_containers():
    assert evaluate("row['voltage_avg']", CTX) is None
    assert evaluate("[1, 2, 3][0]", CTX) is None
    assert evaluate("(1, 2)", CTX) is None
    assert evaluate("{1: 2}", CTX) is None


def test_rejects_strings_bools_comparisons_and_logic():
    assert evaluate("'abc'", CTX) is None
    assert evaluate("True", CTX) is None
    assert evaluate("1 if voltage_avg else 2", CTX) is None
    assert evaluate("1 < 2", CTX) is None
    assert evaluate("1 and 2", CTX) is None
    assert evaluate("not 1", CTX) is None
    assert evaluate("1 | 2", CTX) is None                     # bitwise excluded


def test_rejects_lambda_comprehension_walrus():
    assert evaluate("(lambda: 1)()", CTX) is None
    assert evaluate("[x for x in (1, 2)]", CTX) is None
    assert evaluate("(x := 5)", CTX) is None
    assert evaluate("f'{1}'", CTX) is None


def test_rejects_oversized_expression():
    big = "+".join(["1"] * 300)
    assert evaluate(big, {}) is None


def test_result_is_float_or_none_only():
    for expr in ("1 + 1", "sqrt(2)", "round(1.5)"):
        v = evaluate(expr, {})
        assert isinstance(v, float) and math.isfinite(v)


# ── registry dispatch (DB-free via monkeypatch): expression row authoritative, python fall-through, honest None ─────
def test_registry_expression_row_wins(monkeypatch):
    from ems_exec.derivations import registry
    monkeypatch.setattr(registry, "_expression_for", lambda k: "round(min(1, abs(active_power_total_kw) "
                                                               "/ abs(apparent_power_total_kva)), 3)")
    assert registry.run("truePf", CTX) == round(min(1.0, abs(-180.7) / abs(181.6)), 3)


def test_registry_falls_through_to_python_fn(monkeypatch):
    from ems_exec.derivations import registry
    monkeypatch.setattr(registry, "_expression_for", lambda k: None)   # no expression row → retained python fn
    assert registry.run("windowEnergyKwh", CTX) == 150.5


def test_registry_collapsed_fn_without_expression_degrades(monkeypatch):
    from ems_exec.derivations import registry
    monkeypatch.setattr(registry, "_expression_for", lambda k: None)   # deleted python body + no row → honest None
    assert registry.run("truePf", CTX) is None
    assert registry.run("progressActivePct", CTX) is None
    assert registry.run("displacementPf", CTX) is None
