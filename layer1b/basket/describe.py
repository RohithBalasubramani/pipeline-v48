"""layer1b/basket/describe.py — derive (label, kind, unit) from a neuract/compat column name. The neuract schema is
self-describing (active_power_total_kw, voltage_ln_avg, thd_voltage_r_pct), so the dictionary is built from real columns,
not the stale lt_parameter. The ONE place to tune column naming conventions. [neuract migration]

EVENT/FLAG RULE [hardening]: boolean event/status/compliance columns (sag_event_active, thd_compliance_ieee519) are
kind='event' with NO unit — the old prefix rules mislabeled current_imbalance_event_active as an amp-valued raw metric
('A'), inviting the basket AI to pull a 0/1 flag into a current card as if it were a phase current, and Layer 2
inherited the wrong unit. The pattern is the DB row validation.event_name_pattern (config.validation code-default):
narrowed to exclude thd_compliance_i_avg/v_avg, which are CONTINUOUS % averages (real quality metrics), not flags —
only thd_compliance_ieee519 is a genuine 0/1 flag. Name-pattern based, applies to every meter, no card-ids.

LABEL DEDUP [AI_QUALITY_BACKLOG item 21 / D5]: the dictionary label was ALWAYS the trivial title-case derivation of
the self-describing column_name ('voltage_ll_ry' -> 'Voltage Ll Ry'), so every basket prompt line repeated the column
name twice (~1-1.4K chars/call across the R/Y/B variants and the rest). describe now emits the label ONLY when it
differs from title_label(column_name) — today that is never, so the field rides empty and every consumer derives the
display form on demand (they all fall back to the column name: reflect `label or column`, executor gaps
`label or metric or col`, the L2 emit basket lines never read it). title_label() stays exported as the ONE derivation
home. DB knob layer1b.basket.label_dedup (bool, default on) restores the old behavior with a row edit, no code change.
"""
import re

from config.app_config import cfg
from config.validation import EVENT_NAME_PATTERN

_EVENT = re.compile(EVENT_NAME_PATTERN)
_DERIVED = re.compile(r"(_pct$|_deviation_|_spread$|_unbalance|^current_(min|max)$|_loss_)")
_UNITS = (("_kwh", "kWh"), ("_kvah", "kVAh"), ("_kvarh", "kVArh"),
          ("_kw", "kW"), ("_kva", "kVA"), ("_kvar", "kVAr"), ("_pct", "%"), ("_hz", "Hz"),
          ("_deg", "°"))


def unit(col):
    c = col.lower()
    if _EVENT.search(c):
        return ""                   # 0/1 flag — NEVER a physical unit (was 'A' for current_*_event_active)
    for suf, u in _UNITS:
        if c.endswith(suf):
            return u
    if c.startswith("voltage_"):
        return "V"
    if c.startswith("current_"):
        return "A"
    if c.startswith("frequency"):
        return "Hz"
    if c.startswith("thd_"):
        return "%"
    return ""                       # power_factor / dimensionless


def kind(col):
    c = col.lower()
    if _EVENT.search(c):
        return "event"              # boolean flag — excluded from quantity families (not raw, not derived)
    return "derived" if _DERIVED.search(c) else "raw"


def title_label(col):
    """The trivial human label derived from a self-describing column name — the ONE derivation home (display fallback)."""
    return col.replace("_", " ").strip().title()


def describe(col):
    # item 21 label dedup (see docstring): emit the label ONLY when it differs from title_label(col). The dictionary
    # label today IS that trivial derivation — a pure repeat of the column name — so under the knob the field rides ''
    # and consumers derive the display form on demand. A future CURATED label that differs must be emitted verbatim.
    lbl = "" if bool(cfg("layer1b.basket.label_dedup", True)) else title_label(col)
    return [lbl, kind(col), unit(col)]
