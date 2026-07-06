"""F7 [leaf-reason-contradicts-DB] — the not-logged reason must reflect the REAL logged column set. Pure unit tests.

The reason channel used to say 'active_power_total_kw not logged by this meter' (structurally_null) while that column is
100% non-null live (dg_2/dg_3). The bug: _gap_of trusted the possibly-incomplete latest_row cache — a bucketed/event
column is not preloaded there, so `latest_row.get(col) is None` mislabeled a LIVE column as unlogged. The fix routes the
decision through neuract.column_logged (a direct 'any non-null?' read): a PRESENT + LOGGED column that blanked reads
denorm_garbage ('value failed the validity gates'), NEVER structurally_null; only a genuinely 100%-NULL column reads
'not logged by this meter'. These stub column_logged so no live DB is needed."""
from __future__ import annotations

import ems_exec.data.neuract as nx
from ems_exec.executor import fill as F


class _StubLogged:
    """Patch neuract.present_columns + column_logged for the test: `logged` is the set of present+non-null columns;
    `present_only` are present-but-100%-NULL columns."""

    def __init__(self, logged, present_only=()):
        self.logged = set(logged)
        self.present = set(logged) | set(present_only)

    def __enter__(self):
        self._pc, self._cl = nx.present_columns, nx.column_logged
        nx.present_columns = lambda t: frozenset(self.present)
        nx.column_logged = lambda t, c: c in self.logged
        return self

    def __exit__(self, *a):
        nx.present_columns, nx.column_logged = self._pc, self._cl


def test_present_and_logged_column_that_blanks_is_never_not_logged():
    # active_power_total_kw is present + logged (has non-null rows) but this leaf blanked → no_reading (honest), NOT
    # structurally_null ('not logged') and NOT denorm_garbage ('below valid range' on a real-data column). The F7
    # contradiction is impossible now.
    with _StubLogged(logged={"active_power_total_kw"}):
        cause, params = F._gap_of(
            {"kind": "bucketed", "column": "active_power_total_kw", "slot": "series", "label": "Active Power"},
            "dg_2_mfm", frozenset({"active_power_total_kw"}), latest_row={}, asset_name="DG 2")
    assert cause == "no_reading"
    assert cause != "structurally_null"
    assert cause != "denorm_garbage"


def test_genuinely_null_present_column_reads_not_logged():
    # a present column with ZERO non-null rows IS honestly 'not logged by this meter'.
    with _StubLogged(logged=set(), present_only={"kpi_true_pf"}):
        cause, params = F._gap_of(
            {"kind": "raw", "column": "kpi_true_pf", "slot": "pf", "label": "PF"},
            "dg_2_mfm", frozenset({"kpi_true_pf"}), latest_row={}, asset_name="DG 2")
    assert cause == "structurally_null"


def test_absent_column_reads_not_measured():
    # a column absent from the schema is 'not measured' (column_absent), distinct from 'not logged'.
    with _StubLogged(logged={"other"}):
        cause, params = F._gap_of(
            {"kind": "raw", "column": "nonexistent_col", "slot": "x", "label": "X"},
            "dg_2_mfm", frozenset({"other"}), latest_row={}, asset_name="DG 2")
    assert cause == "column_absent"


def test_derived_with_all_logged_base_cols_is_not_structurally_null():
    # a derivation whose base columns are ALL logged but produced no value failed its inputs — never claims the base
    # columns are unlogged.
    from config import derivation_binding as _deriv
    orig = _deriv.binding
    _deriv.binding = lambda fn: {"base_columns": ["active_power_total_kw"], "fidelity": "exact"}
    try:
        with _StubLogged(logged={"active_power_total_kw"}):
            cause, params = F._gap_of(
                {"kind": "derived", "fn": "some_fn", "slot": "d", "label": "D"},
                "dg_2_mfm", frozenset({"active_power_total_kw"}), latest_row={}, asset_name="DG 2")
        assert cause == "no_reading"
        assert cause != "structurally_null"
    finally:
        _deriv.binding = orig


def test_derived_with_unlogged_base_col_is_structurally_null():
    from config import derivation_binding as _deriv
    orig = _deriv.binding
    _deriv.binding = lambda fn: {"base_columns": ["dead_col"], "fidelity": "exact"}
    try:
        with _StubLogged(logged=set(), present_only={"dead_col"}):
            cause, params = F._gap_of(
                {"kind": "derived", "fn": "some_fn", "slot": "d", "label": "D"},
                "dg_2_mfm", frozenset({"dead_col"}), latest_row={}, asset_name="DG 2")
        assert cause == "structurally_null"
    finally:
        _deriv.binding = orig
