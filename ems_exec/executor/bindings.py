"""ems_exec/executor/bindings.py — the CLOSED binding-op evaluator for roster elements + the shared dataset Policy.
ZERO card knowledge: ops are the fixed vocabulary the card_fill_recipe rows / AI emissions speak; every column name
arrives inside the binding; every dataset convention (PF columns, power column, PF floors, flow threshold, status
synonyms) is a DB-driven config knob with a code default — physics/dataset semantics, not card facts.

Binding vocabulary (closed — anything else honest-nulls):
    col         {"b":"col","c":<column>,"q":<quantity>,"r":<round>,"keep_sign":bool} — latest-row column, verified
                (denorm clamp + negative power/energy → abs unless keep_sign).
    delta       {"b":"delta","c":<column>,"r":n} — windowed cumulative-counter delta for THIS member.
    event       {"b":"event","c":<flag column>} — windowed RISING-EDGE count of a boolean flag for THIS member (a new
                event begins each time the flag goes de-asserted→asserted over the window; a genuinely quiet flag → 0,
                honest — never a fabricated bar). None only when the column is absent / the table is empty.
    phase_mean  {"b":"phase_mean","cs":[cols],"r":n} — mean of the listed per-phase columns.
    prefer_abs  {"b":"prefer_abs","cs":[preferred, signed],"r":n} — first non-null of cs[0], else abs(cs[1]).
    attr        {"b":"attr","a":<name|role|table|mfm_id|type|load_group>} — a member registry attribute.
    slug        {"b":"slug","a":<attr>} — the slugified attribute (falls back to mfm_id — stable ids for dark members).
    status      {"b":"status","policy":"pf_floors","vocab":[good,fair,bad]} — PF-floor verdict in the card's OWN vocab;
                PF unknown → energized→vocab[0] / de-energized→'idle' (never a fabricated fault).
    energized   {"b":"energized"} — |power| >= the configured flow threshold (False for a dark member).
    ts_label    {"b":"ts_label","fmt":"HH:MM:SS"} — the member row's REAL timestamp formatted (None when absent).
    const       {"b":"const","v":<literal>} — the literal.
    null        {"b":"null","why":...} — HONEST-NULL (the dataset has no such column; uncolonizable upstream).

[atomic; pure evaluation over one (member, row) pair + Policy; delegates math to _agg / reads to members.member_delta]
"""
from __future__ import annotations

from ems_exec.renderers import _agg
from ems_exec.executor import members as _members


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  Policy — dataset conventions, built ONCE per run from DB-driven config accessors (code-default fallback each)
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
class Policy:
    """The shared dataset/physics knobs every binding op reads — NOT card facts. Each one is an app_config /
    feeder_overview row with the code default preserved (edit the row, no code change)."""

    def __init__(self):
        from config.app_config import cfg
        # FIXED SCHEMA VOCABULARY, not knobs [hardcoding F10 half-knob retired 2026-07-12]: these neuract gic_*
        # column names are also literals in derivation_binding.base_columns rows, _story LIVE_COLS and the
        # schema_slot_map seed — a DB row here moved ONE of ~15 consumers, the most misleading state for an
        # operator. Rows deleted (db/fix_retire_roster_column_knobs.sql); renaming the columns is a schema
        # migration, not a config edit.
        self.pf_cols = ["kpi_true_pf", "power_factor_total"]
        self.power_col = "active_power_total_kw"
        self.status_synonyms = cfg("roster.status_synonyms", {
            "critical": ["critical", "danger"],
            "warning": ["warning", "watch", "warn"],
            "normal": ["normal", "ok", "success", "live"],
        })
        try:
            from config import feeder_overview as _fo
            self.pf_good = _fo.num("feeder_overview.pf_good_min", 0.95)
            self.pf_fair = _fo.num("feeder_overview.pf_fair_min", 0.90)
            self.flow_threshold_kw = _fo.num("feeder_overview.sld_flow_threshold_kw", 1.0)
        except Exception:
            self.pf_good, self.pf_fair, self.flow_threshold_kw = 0.95, 0.90, 1.0

    # ── shared verdicts ───────────────────────────────────────────────────────────────────────────────────────────
    def verify(self, value, quantity=None):
        """Denorm clamp + the negative power/energy abs convention — delegates to the executor's ONE _verify."""
        from ems_exec.executor.verify import _verify
        return _verify(value, quantity=quantity)

    def pf_of(self, row):
        """Unsigned true PF from the configured column pair: prefer the unsigned column, else abs(signed). None when
        both are absent (honest-null)."""
        cols = self.pf_cols or []
        pf = _agg.num(row.get(cols[0])) if len(cols) > 0 else None
        if pf is None and len(cols) > 1:
            signed = _agg.num(row.get(cols[1]))
            pf = abs(signed) if signed is not None else None
        return pf

    def power_of(self, row):
        """The member's verified power reading (the reporting/energized signal), or None."""
        return self.verify(_agg.num(row.get(self.power_col)), quantity="power")

    def energized(self, row):
        """|power| >= the flow threshold; a dark member (no power read) is NOT energized (honest — no fabricated flow)."""
        kw = _agg.num(row.get(self.power_col))
        return False if kw is None else abs(kw) >= self.flow_threshold_kw

    def status(self, row, vocab):
        """PF-floor verdict in the caller's 3-word vocab [good, fair, bad]; PF unknown → energized→vocab[0] / 'idle'.
        NEVER fabricates a fault from missing data."""
        v = list(vocab or ["normal", "warning", "critical"])
        while len(v) < 3:
            v.append(v[-1] if v else "critical")
        pf = self.pf_of(row)
        if pf is not None:
            if pf >= self.pf_good:
                return v[0]
            if pf >= self.pf_fair:
                return v[1]
            return v[2]
        return v[0] if self.energized(row) else "idle"

    def status_matches(self, value, target):
        """Does an element's status `value` mean `target` (synonym fold: danger≡critical, success≡normal, …)?"""
        s = str(value or "").strip().lower()
        t = str(target or "").strip().lower()
        return s == t or s in {str(x).lower() for x in (self.status_synonyms or {}).get(t, [])}


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  helpers
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
def slugify(x):
    """Lower-dashed slug (space / slash / underscore → dash) so gic table names and display names normalize the same
    way for fuzzy matching. None in → None out."""
    return (str(x).strip().lower().replace(" ", "-").replace("/", "-").replace("_", "-")[:48]
            if x is not None else None)


def _round(x, n):
    v = _agg.num(x)
    if v is None:
        return None
    return round(v, n) if n is not None else v


_FMT = (("YYYY", "%Y"), ("MMM", "%b"), ("DD", "%d"), ("HH", "%H"), ("MM", "%M"), ("SS", "%S"))


def format_ts(value, fmt):
    """A REAL timestamp value rendered per the shared `fmt` token table ('DD HH:MM' → '%d %H:%M'). No fmt → the value
    passes through untouched (the raw [{t, value}] point contract). Unparseable → None (honest, never a seed label)."""
    if not fmt:
        return value
    if value is None:
        return None
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None
    f = fmt
    for token, strf in _FMT:
        f = f.replace(token, strf)
    try:
        return dt.strftime(f)
    except Exception:
        return None


def _ts_label(row, ts_col, fmt):
    """The member row's REAL timestamp rendered per `fmt` ('HH:MM:SS' → %H:%M:%S). None when absent/unparseable —
    honest, never a seed clock label."""
    v = row.get(ts_col) if ts_col else None
    if not v:
        return None
    return format_ts(v, fmt or "HH:MM:SS")


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  evaluate — ONE binding over ONE (member, row) pair. Unknown op → None (honest). Never raises.
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
def evaluate(binding, member, row, window, policy, ts_col=None):
    """The real value for one binding — real column read / registry attribute / policy verdict, honestly None."""
    if isinstance(binding, str):                                   # bare-string shorthand = {"b":"col","c":<column>}
        binding = {"b": "col", "c": binding}
    if not isinstance(binding, dict):
        return None
    op = (binding.get("b") or "").strip().lower()
    try:
        if op == "col":
            v = _agg.num(row.get(binding.get("c")))
            if v is None:
                return None
            if not binding.get("keep_sign"):
                v = policy.verify(v, quantity=binding.get("q"))
            return _round(v, binding.get("r"))
        if op == "delta":
            return _members.member_delta(member, window, binding.get("c"),
                                         ndigits=binding.get("r", 1))
        if op == "event":
            return _members.member_event_count(member, window, binding.get("c"))
        if op == "phase_mean":
            return _agg.mean([row.get(c) for c in (binding.get("cs") or [])], ndigits=binding.get("r", 3))
        if op == "prefer_abs":
            cs = binding.get("cs") or []
            v = _agg.num(row.get(cs[0])) if len(cs) > 0 else None
            if v is None and len(cs) > 1:
                s = _agg.num(row.get(cs[1]))
                v = abs(s) if s is not None else None
            return _round(v, binding.get("r", 3))
        if op == "attr":
            return member.get(binding.get("a"))
        if op == "slug":
            v = member.get(binding.get("a") or "name")
            return slugify(v if v is not None else member.get("mfm_id"))
        if op == "status":
            return policy.status(row, binding.get("vocab"))
        if op == "energized":
            return policy.energized(row)
        if op == "ts_label":
            return _ts_label(row, ts_col, binding.get("fmt"))
        if op == "const":
            return binding.get("v")
        if op == "null":
            return None
    except Exception:
        return None
    return None                                                    # unknown op → honest-null (closed vocabulary)


def element(element_spec, member, row, window, policy, ts_col=None):
    """One roster ELEMENT: every key of the recipe's element spec evaluated over this member's real row — per-leaf
    honest-null (a missing column blanks ITS key only, the element still renders)."""
    return {k: evaluate(b, member, row, window, policy, ts_col=ts_col)
            for k, b in (element_spec or {}).items()}


def referenced_columns(roster):
    """Every neuract column any binding in the normalized roster references (c / cs across element / group /
    sample / member_value / agg 'of'-independent) — the per-member read set."""
    cols = set()

    def _scan(b):
        if isinstance(b, str):
            cols.add(b)
        elif isinstance(b, dict):
            if b.get("c"):
                cols.add(b["c"])
            for c in (b.get("cs") or []):
                cols.add(c)

    for slot in (roster or []):
        for key in ("element", "group", "sample", "member_value"):
            for b in (slot.get(key) or {}).values():
                _scan(b)
    return {c for c in cols if isinstance(c, str) and c}
