"""grounding/role_scrub.py — ROLE-BASED string-leaf scrub for the build-time skeleton (one concern).

WHY (the seedless gap): grounding.default_assemble strips DATA leaves by TYPE (leaf_classify: numbers / numeric-string
KPIs / series) and scrubs narrative/clock/provenance STRINGS by KEY/VALUE. That leaves a third class untouched — a STRING
whose SLOT ROLE is an ACTIVE, DATA-DERIVED ASSERTION (a value knowable ONLY from live/queried data), e.g. the worst-panel
pick `strip.stats.worstCurrent.table='MFM_033'`, a live verdict `status.label='Elevated'`, an event instance
`anomalies[].title='Welding Overlap'`. `classify` treats the KEY as chrome so the fabricated VALUE replays as if live.

This module blanks those strings — and ONLY those — by their SLOT ROLE, never by the string itself:
  (A) DERIVED-PICK objects  (parent key `worst*` / `selectedPanel`) → blank EVERY string attr of the object; the whole
      object IS 'which panel scored worst' + its derived facts {id,panel,table,status,cause,causeKey,driver,driverKey}.
  (B) ROSTER lists          (`panels[]` / `periods[].panels[]`) → blank the DERIVED per-panel facts + the DB pointer
      {status,cause,causeKey,driver,driverKey,table} but KEEP the roster display identity {id,panel} (a dropdown label,
      not a verdict).
  (C) ACTIVE-STATE objects  (parent key `status`/`statusBadge`/`badge`/`freshness`/`ieeeBadge`/`state`/`service`) → blank
      the asserted condition {label,statusKey,statusLabel,tone,dsTone,status,key} + sibling active pointers
      insightKey / *State / availability / severityLabel.
  (D) EVENT / ANOMALY instances (`anomalies[]`/`events[]`/`event`) → blank {title,label,type,severity,status} (the
      'what happened' claim + its time-offset label); KEEP lane/series chrome {axis,unit,chart,series,seriesLabel,color}.
  (F) any hardcoded meter/table id whose VALUE matches the fabricated-pointer pattern (^MFM[_-]?\\d+$), any slot.
  (G) an asserted compliance verdict {ieeeState / availability / ieeeBadge.label} = a live result.

KEPT byte-identical (a LOOKUP-DICTIONARY / enum option-set the component needs to render ANY state) whenever ANY ancestor
key is a dictionary-subtree key (*Vocab / statusVocab / insightVocab / causeVocab / driverVocab / complianceWords /
eventTypeKeys / driverCodeMap / eventModeOrder / statusLegend / bandThresholds / legend / palette). The dictionary KEEP
OVERRIDES every blank rule — so `status.label='Normal'` blanks but `statusVocab.normal='Normal'` and
`bandThresholds.stops.kw[].status='high'` stay. Distinguish an ACTIVE-VALUE slot from a LOOKUP-DICTIONARY slot by the
PARENT-KEY ROLE, never by the enum string alone.

DB-first: every key/parent/pattern list is a cmd_catalog.app_config `role_scrub.*` row read via config.vocab (db/
seed_role_scrub_vocab.sql). No card_id, no specific string, is hardcoded — the code holds only the generic ROLE walk
(which config lists cannot express: it needs the ancestor chain to tell `status.label` from `statusVocab.normal`).
On a missing row / DB outage the lists return empty → the scrub narrows to nothing (honest degrade, never a fabricated
guess). Build-time only: invoked by grounding.default_assemble._strip_and_scrub (persisted into payload_stripped).
"""
from __future__ import annotations

import re

from config.vocab import vocab


# ── DB-config vocab lists (role_scrub.* rows; empty on miss → honest no-op) ────────────────────────
def _set(name):
    return {str(x).strip().lower() for x in (vocab(name) or ()) if str(x).strip()}


def _derived_pick_parents():
    # parent keys whose WHOLE object is a data-derived pick (blank every string attr). 'worst' matches any worst* key
    # (worstCurrent/worstVoltage/worstIThd/worstVThd/worst) by PREFIX below; selectedpanel is an exact active pick.
    return _set("role_scrub.derived_pick_parents") or {"worst", "selectedpanel"}


def _active_state_parents():
    return _set("role_scrub.active_state_parents") or {
        "status", "statusbadge", "badge", "freshness", "ieeebadge", "state", "service"}


def _active_value_keys():
    # the verdict / derived-fact attribute keys blanked inside a derived-pick / active-state / roster object.
    return _set("role_scrub.active_value_keys") or {
        "label", "statuslabel", "statuskey", "tone", "dstone", "status", "key",
        "driver", "driverkey", "cause", "causekey", "insightkey", "ieeestate",
        "availability", "severity", "severitylabel", "severityaction", "table",
        "id", "panel", "deltatone"}


def _roster_parents():
    return _set("role_scrub.roster_parents") or {"panels", "periods"}


def _roster_identity_keys():
    # roster display identity KEPT (the dropdown label dictionary, not a verdict): only inside a roster list.
    return _set("role_scrub.roster_identity_keys") or {"id", "panel"}


def _roster_blank_keys():
    # DERIVED per-panel facts + DB pointer blanked inside a roster element (identity id/panel kept).
    return _set("role_scrub.roster_blank_keys") or {
        "status", "cause", "causekey", "driver", "driverkey", "table"}


def _event_parents():
    return _set("role_scrub.event_parents") or {"anomalies", "events", "event", "anomaly"}


def _event_value_keys():
    return _set("role_scrub.event_value_keys") or {"title", "label", "type", "severity", "status"}


def _dictionary_subtree_keys():
    # KEEP-HARD: if ANY ancestor key is one of these, the string is a lookup-dictionary / enum option-set / roster of
    # design bands / presentation chrome container — keep byte-identical. Substring 'vocab' covers every *Vocab. This
    # OVERRIDES all blank rules (incl. the global active-key / tone rules).
    return _set("role_scrub.dictionary_subtree_keys") or {
        "statusvocab", "insightvocab", "causevocab", "drivervocab", "notevocab", "vocab",
        "compliancewords", "eventtypekeys", "drivercodemap", "eventmodeorder", "eventcolumn",
        "statuslegend", "bandthresholds", "legend", "palette", "presentation"}


def _global_active_keys():
    # ACTIVE-POINTER keys that assert the live condition by their OWN NAME, regardless of parent (blanked anywhere
    # except inside a dictionary subtree). A same-named STATIC caption is spared by living under a dictionary subtree.
    # 'mode' = an operating-MODE verdict (UPS points[].mode='normal', event summary.mode='sag') — knowable only from
    # live data; a mode OPTION-SET (modeVocab / eventModeOrder) is a dictionary subtree and stays. [card-59 seed]
    return _set("role_scrub.global_active_keys") or {
        "ieeestate", "filterstate", "availability", "capacitorbank", "severityaction",
        "severitylabel", "insightkey", "statuslabel", "statuskey", "mode"}


def _tone_suffix():
    raw = vocab("role_scrub.tone_key_suffix")
    return (raw if isinstance(raw, str) and raw.strip() else "tone").strip().lower()


def _reference_line_parents():
    return _set("role_scrub.reference_line_parents") or {"referencelines", "watchlines"}


def _metric_value_parents():
    # KPI/stat/tile containers whose element `value`/`displayValue` IS the measured datum. A NUMERIC value was already
    # zeroed by leaf_classify (runs first); a surviving STRING there is a data-derived TEXT descriptor (e.g. a stat
    # 'Primary Event'='Motor start sag', a status word) — a fabricated seed, blank it. label/unit/note stay (not value).
    return _set("role_scrub.metric_value_parents") or {
        "stats", "stat", "metrics", "metric", "kpis", "kpi", "kpicells", "kpicell",
        "cells", "tiles", "scorecells", "summarystats", "quickstats"}


def _metric_value_keys():
    return _set("role_scrub.metric_value_keys") or {"value", "displayvalue"}


def _is_numeric(s):
    try:
        float(str(s).replace(",", "").replace("%", "").strip()); return True
    except (TypeError, ValueError):
        return False


_MFM_DEFAULT = r"^\s*MFM[_-]?\d+\s*$"


def _mfm_pattern():
    raw = vocab("role_scrub.mfm_pointer_pattern")
    pat = raw if isinstance(raw, str) and raw.strip() else _MFM_DEFAULT
    try:
        return re.compile(pat, re.IGNORECASE)
    except re.error:
        return re.compile(_MFM_DEFAULT, re.IGNORECASE)


# ── the role walk ──────────────────────────────────────────────────────────────────────────────────


def _parent_is_derived_pick(ancestors, pick_parents):
    """True when the nearest object-parent (last ancestor) is a derived-pick: exact match OR a 'worst*' prefix key."""
    if not ancestors:
        return False
    p = ancestors[-1]
    if p in pick_parents:
        return True
    return p.startswith("worst")


def _in_roster(ancestors, roster_parents):
    """True when SOME ancestor is a roster list parent (panels / periods) — the element is a roster row."""
    return any(a in roster_parents for a in ancestors)


def scrub_active_string_leaves(tree, ph):
    """Mutate `tree` in place: blank (→ `ph`) every STRING leaf whose SLOT ROLE is an active / derived-pick / event
    assertion, keeping lookup-dictionary / enum / roster-identity chrome. `ancestors` is the lowercased key chain of the
    CONTAINING objects (list indices contribute no key). Returns the same tree. Never raises on shape (defensive walk)."""
    pick_parents = _derived_pick_parents()
    state_parents = _active_state_parents()
    active_keys = _active_value_keys()
    roster_parents = _roster_parents()
    roster_id = _roster_identity_keys()
    roster_blank = _roster_blank_keys()
    event_parents = _event_parents()
    event_keys = _event_value_keys()
    dict_keys = _dictionary_subtree_keys()
    global_keys = _global_active_keys()
    tone_suffix = _tone_suffix()
    ref_line_parents = _reference_line_parents()
    metric_parents = _metric_value_parents()
    metric_value_keys = _metric_value_keys()
    mfm = _mfm_pattern()

    def blank_here(key, value, ancestors):
        """Decide whether the string `value` at `key` (lowercased) under `ancestors` is an active data-derived
        assertion to blank. Dictionary-subtree KEEP already handled by the caller (walk skips into dict subtrees)."""
        # (F) fabricated meter/table pointer — any slot, by VALUE.
        if mfm.match(value):
            return True
        # (C/G global) ACTIVE-POINTER key — a live-derived assertion by its own name, anywhere (ieeeState / availability
        # / severityAction / per-metric statusLabel). A static same-named caption is already spared by the dict-subtree
        # KEEP in the caller (complianceStrip.severityLabel).
        if key in global_keys:
            return True
        # (C/E global) a *tone verdict anywhere — EXCEPT a static reference/watch line style (referenceLines[].tone).
        if key.endswith(tone_suffix) and not any(a in ref_line_parents for a in ancestors):
            return True
        # (D) event / anomaly instance attribute.
        if any(a in event_parents for a in ancestors) and key in event_keys:
            return True
        # (H) KPI/stat value-slot holding a NON-NUMERIC string = a data-derived text descriptor (the numeric case was
        # already zeroed by leaf_classify before this scrub). Immediate parent is the metric container.
        if ancestors and ancestors[-1] in metric_parents and key in metric_value_keys and not _is_numeric(value):
            return True
        # (A) derived-pick object (worst* / selectedPanel): blank EVERY active/identity attr of the object.
        if _parent_is_derived_pick(ancestors, pick_parents) and key in active_keys:
            return True
        # (B) roster element (panels[] / periods[].panels[]): blank DERIVED facts + DB pointer, KEEP {id,panel}.
        if _in_roster(ancestors, roster_parents):
            if key in roster_id:
                return False
            if key in roster_blank:
                return True
            return False
        # (C)/(G) active-state object (status/statusBadge/badge/freshness/ieeeBadge/state/service): blank the verdict
        # attrs. Also sibling active pointers directly under such a parent (insightKey/ieeeState/availability).
        if ancestors and ancestors[-1] in state_parents and key in active_keys:
            return True
        return False

    def walk(o, ancestors):
        # `ancestors` = the lowercased key chain of the CONTAINING objects (a list index adds NO key). The leaf key is
        # tested separately so blank_here can check key membership against the parent role.
        if isinstance(o, dict):
            for k, v in list(o.items()):
                kl = str(k).lower()
                # dictionary-subtree KEEP: never descend-to-blank inside a *Vocab / enum / legend / bandThresholds /
                # palette subtree — the whole subtree is lookup chrome (this OVERRIDES every blank rule).
                if "vocab" in kl or kl in dict_keys:
                    continue
                if isinstance(v, str):
                    if v.strip() and blank_here(kl, v.strip(), ancestors):
                        o[k] = ph
                else:
                    walk(v, ancestors + [kl])
        elif isinstance(o, list):
            for v in o:
                if not isinstance(v, str):
                    walk(v, ancestors)

    try:
        walk(tree, [])
    except Exception:
        pass
    return tree
