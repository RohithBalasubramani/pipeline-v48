"""data/neuract_live/twin.py — DEAD-TWIN → LIVE-TWIN redirect for member / incomer meter resolution.

A single physical asset can carry TWO registry meters: a live Secure-Elite300 (`_se`) meter with a real time-series, and
a dead schematic/placeholder (`_sch`) stub (0 columns, never_wired, table_exists=false). The panel topology edges
(lt_mfm_incoming / lt_mfm_outgoing) frequently point at the DEAD stub's id — so the panel-aggregate roll-up reads an
empty table and the whole supply side blanks (Energy Input card, Energy Flow sankey source/efficiency, SLD incomers, the
"no readings available" narrative — ALL one root cause). This redirects a dead meter to its DATA-BEARING twin: the
sibling meter of the SAME physical asset whose registry row is table_exists AND not never_wired.

The twin key is GIC-SCOPED and precise: it strips only the `-Nxx-` meter-position segment and a `[model]` suffix,
KEEPING the GIC prefix + the full equipment descriptor. So `GIC-15-N10-PCC-01 (Transformer-01)` and
`GIC-15-N3-PCC-01 (Transformer-01) [Secure Elite300]` both key to `gic-15-pcc-01 (transformer-01)` and match — while a
GENERIC descriptor like `Spare` never cross-matches across different GIC groups (`GIC-30-N7-Spare` ≠ `GIC-01-N1-Spare`).
Registry-flag driven, no hardcoded ids. Redirects ONLY when exactly ONE live twin exists (ambiguous → honest no-op).

Verified live coverage (GIC-15 HT meters): the 4 PCC transformers, the Spare, the 11 KV Incomer, and the TIE feeder —
7 dead `_sch` stubs each redirect to their live `_se` twin. Flag topology.data_bearing_twin (default off)."""
import re

from data.registry import lt_mfm as _reg

_KEY_NPOS = re.compile(r"^(GIC-\d+)-N\d+-", re.I)
_KEY_MODEL = re.compile(r"\s*\[[^\]]*\]\s*$")


def _twin_key(name):
    """The physical-asset identity key: GIC prefix + equipment descriptor, with the -Nxx- meter position and a [model]
    suffix removed. None for an empty name."""
    s = (name or "").strip()
    s = _KEY_NPOS.sub(r"\1-", s)
    s = _KEY_MODEL.sub("", s)
    s = s.strip().lower()
    return s or None


def _dead(row):
    return bool(row.get("never_wired")) or not row.get("table_exists")


def _live(row):
    return bool(row.get("table_exists")) and not row.get("never_wired") and bool(row.get("table"))


def live_twin_table(mfm_id):
    """The neuract table of the DATA-BEARING twin for `mfm_id`, or None. Returns a table ONLY when `mfm_id` is itself a
    DEAD twin AND EXACTLY ONE live sibling shares its GIC-scoped twin key. Registry-flag driven; never fabricates,
    never raises."""
    try:
        rows = _reg.registry_rows()
    except Exception:
        return None
    me = next((r for r in rows if r.get("id") == _as_int(mfm_id)), None)
    if not me or not _dead(me):
        return None                                    # unknown / already live → no redirect
    key = _twin_key(me.get("name"))
    if not key:
        return None
    live = [r for r in rows if r.get("id") != me.get("id") and _live(r) and _twin_key(r.get("name")) == key]
    return live[0]["table"] if len(live) == 1 else None   # unambiguous single live twin only


def _as_int(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return None
