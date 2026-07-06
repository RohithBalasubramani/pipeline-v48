"""ITEM 22a (outputs/AI_QUALITY_BACKLOG.md — 'Hygiene: cast-integrity test'): every cmd_catalog app_config row must
parse through config.app_config.cfg with its DECLARED data_type.

Catches the INERT-ROW drift class: `display.null_dash` sat dead because its row declared data_type='number' on a text
value — _cast raised, cfg() silently fell back to the code default, and editing the row changed nothing. Nothing
prevents the next mis-typed INSERT except this test.

DB-tolerant, not @live: on a cmd_catalog outage _load() fail-opens to {} and the row-sweep tests SKIP (never red in
`pytest -m 'not live'` on an unreachable DB); the mechanism tests below need no DB at all."""
import pytest

from config import app_config

_SENTINEL = object()
# the data_type vocabulary _cast() actually dispatches on ('text' is the explicit passthrough spelling used by every
# seeded row) — any OTHER spelling silently passes through as text, which is exactly the drift this test polices.
_KNOWN_TYPES = {"number", "int", "bool", "json", "text"}


def _rows():
    return app_config._load()          # process-cached {key: (value, data_type)}; {} on DB outage (fail-open)


def test_every_app_config_row_casts_with_declared_type():
    rows = _rows()
    if not rows:
        pytest.skip("cmd_catalog unreachable (app_config fail-open) — row sweep needs the live DB")
    bad = []
    for key in sorted(rows):
        value, data_type = rows[key]
        if app_config.cfg(key, _SENTINEL) is _SENTINEL:
            bad.append(f"{key!r}: value {value!r} does not parse as declared data_type={data_type!r} — the row is "
                       f"INERT (cfg() silently serves the code default; the display.null_dash dead-row class)")
    assert not bad, "app_config cast-integrity violations:\n" + "\n".join(bad)


def test_every_app_config_data_type_is_known():
    rows = _rows()
    if not rows:
        pytest.skip("cmd_catalog unreachable (app_config fail-open) — row sweep needs the live DB")
    bad = [f"{key!r}: data_type={dt!r}" for key, (_v, dt) in sorted(rows.items()) if dt not in _KNOWN_TYPES]
    assert not bad, ("app_config rows with an UNKNOWN data_type (silently treated as text by _cast):\n"
                     + "\n".join(bad) + f"\nknown: {sorted(_KNOWN_TYPES)}")


# ── mechanism (no DB): the sentinel actually detects the inert-row class ──────────────────────────────────────────
def test_cast_sentinel_detects_mistyped_number():
    # the literal display.null_dash bug: a text value ('—') declared data_type='number' → cfg falls back → row inert
    assert app_config._cast("—", "number", _SENTINEL) is _SENTINEL


def test_cast_sentinel_detects_mistyped_json():
    assert app_config._cast("not-json", "json", _SENTINEL) is _SENTINEL


def test_cast_valid_values_never_hit_sentinel():
    assert app_config._cast("42.5", "number", _SENTINEL) == 42.5
    assert app_config._cast("7", "int", _SENTINEL) == 7
    assert app_config._cast("on", "bool", _SENTINEL) is True
    assert app_config._cast('["a", 1]', "json", _SENTINEL) == ["a", 1]
    assert app_config._cast("—", "text", _SENTINEL) == "—"
