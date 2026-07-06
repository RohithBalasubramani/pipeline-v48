"""grounding/default_assemble.py — build a card's subcard-inclusive DEFAULT payload STATUS: the byte-identical
harvested default with (a) its subcards nested at their slots, (b) the correct variant chosen by slot identity, (c) a
component-sibling fallback when the card itself has no default, (d) ALL data-leaf values stripped to typed
placeholders, and (e) fabricated narrative literals scrubbed. ZERO AI — this is a deterministic transform over the
harvested `card_payloads` rows + `card_component_usage` (both editable DB tables).

WHY: Layer 3 must be shown the card's default SHAPE (which slots exist, which are metadata chrome vs data) WITHOUT any
fabricated demo number/text — otherwise the AI (and, worse, the resting render) leaks Storybook literals as if live
(card 41's "loss 43.0 kW", card 8's "DG load remains near 80%"). And a card with no harvested default must not fall to
the raw contract EXAMPLE payload — it should reuse a SIBLING card's default for the SAME primary component.

Covers:
  · [META-06] subcard structural defaults dropped → nest each subcard's default at its key_roles slot (subcard-inclusive).
  · [META-07] multiple non-subcard payloads → pick the default by SLOT IDENTITY (variant/story match), not alphabetically.
  · [META-01/05] no default → COMPONENT-LEVEL sibling fallback (a card that DOES have a default for the same primary
    component); if none, honest 'no default'.
  · [VC-02] Storybook demo values leaked as live → strip every data leaf to a typed placeholder + scrub fabricated
    narrative text so the default carries NO fabricated metric.

Every policy (typed-placeholder values, the narrative-slot scrub list) is an editable row read via `config.*`. No
hardcoded field names / magic values in logic.
"""
from __future__ import annotations

import copy
import re

from config import quality_policy as qp
from config import reason_templates as rt
from data.db_client import q
from grounding.event_skeleton_scrub import empty_event_instance_lists
from grounding.measured_annotation_scrub import scrub_measured_annotation_strings
from grounding.role_scrub import scrub_active_string_leaves
from layer2.catalog.card_payload import default_for
from validate.leaf_classify import classify
from validate.payload_lookup import card_payloads_for


# ── typed placeholders (editable policy) ──────────────────────────────────────────────────────────
# A data leaf is stripped to a TYPED zero so the CMD_V2 component still mounts with the right prop type (a number prop
# stays a number, an array prop stays an array) — never a fabricated demo value. The zero VALUES are editable rows.
_SENTINEL = object()


def _placeholder(kind, scalar=_SENTINEL):
    if kind == "scalar":
        # numeric 0.0 keeps the prop numeric so a CMD_V2 component's unguarded .toFixed()/.toLocaleString() never
        # crashes; overridable via placeholder.scalar OR the explicit `scalar` arg (honest-blank callers pass None so
        # the host's display-dash renders '—' instead of a fabricated 0.0). An explicit scalar (incl. None) wins.
        if scalar is not _SENTINEL:
            return scalar
        v = qp.txt("placeholder.scalar", "0")
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0
    # array / series → an empty list keeps the prop iterable without any fabricated points.
    return []


# ── narrative-slot scrub list (editable policy) ───────────────────────────────────────────────────
# Metadata STRING leaves whose last path segment is one of these are AI-authored narrative that embed a fabricated
# metric ("Active power loss is 43.0 kW …"). They are scrubbed to a neutral placeholder so the resting default carries
# no fabricated text. The list is a comma-separated editable policy row (quality_policy 'narrative_slots').
def _narrative_slots():
    raw = qp.txt("narrative_slots",
                 "insight,text,summary,note,caption,subtitle,likelysource,nextpriority,"
                 "trendlabel,message,headline,description,detail,commentary")
    return {s.strip().lower() for s in raw.split(",") if s.strip()}


def _narrative_placeholder():
    # empty string keeps the prop a string; the reason channel carries the honest 'awaiting live data' note separately.
    return qp.txt("placeholder.narrative", "")


# ── clock-string scrub (editable policy) ──────────────────────────────────────────────────────────
# A metadata STRING that carries a clock time ('13:14:10', 'at 13:17:30') is a harvested Storybook TIMESTAMP — shown
# unstripped it renders a FABRICATED live time axis (scrubber/footer/peak-at labels at the wrong wall clock). This is a
# VALUE-typed check (like the numeric-string KPI rule), not a keyword list; the switch is an editable policy row.
# TEMPORAL seed strings — a harvested Storybook time-axis label is DATA (a stale wall-clock/date), not chrome, and
# leaks a wrong date into the render (trend x-tick 'Apr 15', selectedLabel '21 (Today)', footer HH:MM). Match a CONCRETE
# date/clock only — a bare picker word ('Today','This Week','Last 7 Days' as a rangeOptions label) has no digit/month
# and stays chrome. VALUE-typed (like the numeric-string KPI rule), DB-overridable via scrub.temporal_pattern.
_TEMPORAL_DEFAULT = (
    r"(?<![\d.])\d{1,2}:\d{2}(?::\d{2})?(?![\d.])"                             # HH:MM(:SS) clock
    r"|(?i:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*\d{1,2}"  # 'Apr 15'
    r"|\d{1,2}\s*(?i:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*"     # '15 Apr'
    r"|\d{4}[-/]\d{2}[-/]\d{2}"                                                # ISO date
    r"|\d{1,2}\s*\((?i:today|yesterday|tomorrow)\)"                            # '21 (Today)'
    r"|\d{1,2}\s*(?i:am|pm)\b")                                                # '9 AM'
_CLOCK_STR = re.compile(qp.txt("scrub.temporal_pattern", _TEMPORAL_DEFAULT) or _TEMPORAL_DEFAULT)


def _clock_scrub_on():
    return (qp.txt("scrub.clock_strings", "on") or "on").strip().lower() != "off"


# ── date-axis orphan-day scrub (editable policy) ──────────────────────────────────────────────────
# A trend x-axis is harvested as ['Apr 15','16','17','18','19','20','21 (Today)'] — a stale CALENDAR window. The
# calendar-anchor labels ('Apr 15','21 (Today)') match _CLOCK_STR and get scrubbed, but the middle BARE day-numbers
# ('16'..'20') don't (a bare integer isn't a concrete date on its own) so the stale window LEAKS. When an ARRAY is a
# temporal axis (some sibling label IS a concrete date/clock), its bare-integer members are day-of-month positions of
# the SAME axis → temporal seeds too. This is a per-ARRAY value-typed inference (not a key list, not per-card): scrub the
# bare-day siblings only inside an array already proven temporal. A bare integer that is NOT in a temporal axis (a plain
# category count, a gauge tick) is never touched. Pattern is DB-overridable via scrub.bare_day_pattern.
_BARE_DAY = re.compile(qp.txt("scrub.bare_day_pattern", r"^\s*\d{1,2}\s*$") or r"^\s*\d{1,2}\s*$")


def _axis_label_strings(lst):
    """The label strings of a list — the elements themselves (string list) or each object's `label` (object list)."""
    out = []
    for x in lst:
        if isinstance(x, str):
            out.append(x)
        elif isinstance(x, dict) and isinstance(x.get("label"), str):
            out.append(x["label"])
    return out


def _is_temporal_axis(lst):
    """True when this list is a TIME/DATE axis: at least one of its label strings carries a concrete date/clock
    (_CLOCK_STR). Then bare-integer siblings are day-of-month positions of the SAME axis (orphaned seeds)."""
    return any(_CLOCK_STR.search(s) for s in _axis_label_strings(lst))


# ── provenance-marker scrub (editable policy) ─────────────────────────────────────────────────────
# A harvested Storybook payload can carry a PROVENANCE marker string ('source':'mock') — a lie about the data origin
# that, shipped verbatim, tells the FE/user the numbers came from a mock feed (card 47). It is a metadata STRING (not a
# data leaf, not narrative prose), so neither the data-leaf strip nor the narrative scrub touches it. This VALUE-typed
# scrub neutralises any string whose value is one of the mock-provenance tokens → the neutral placeholder, so no
# 'mock'/'demo'/'seed' provenance survives into a live payload. The token list is an editable policy row.
def _provenance_tokens():
    raw = qp.txt("scrub.provenance_tokens", "mock,fake,demo,seed,sample,stub,placeholder,dummy,fixture")
    return {s.strip().lower() for s in str(raw or "").split(",") if s.strip()}


def _esc(s):
    return str(s).replace("'", "''")


def _last_seg(path):
    """The trailing key of a classify path ('data.insight' → 'insight', 'snapshot.h5.valuePct' → 'valuePct')."""
    if not path:
        return ""
    seg = path.rsplit(".", 1)[-1]
    return seg.split("[", 1)[0].lower()          # drop any list index


# classify-style dotted/indexed path addressing: the ONE shared home (ems_exec/executor/paths.py).
# _set_at ≡ paths._set_path (silent no-op on a vanished path); _get_at ≡ paths._leaf_at (None on a miss).
from ems_exec.executor.paths import _set_path as _set_at, _leaf_at as _get_at

_NUM_STR = re.compile(r"^\s*[+-]?\d")


def _strip_series(out, path, scalar=_SENTINEL):
    """Strip a SERIES leaf. A series-of-OBJECTS (phases / sankey links / heatmap feeders / sources) is stripped
    PER-ELEMENT — each element recursively has EVERY data leaf zeroed (numbers, numeric-string KPI values, nested
    arrays) while its text chrome (label/color/unit/id) is kept byte-identical — so no seed number leaks yet the executor
    can refill phases[i].value etc. A list of plain numbers (or empty) carries no chrome → typed empty []."""
    cur = _get_at(out, path)
    if isinstance(cur, list) and cur and all(isinstance(x, dict) for x in cur):
        # date-axis orphan-day scrub BEFORE the per-element recurse: a series-of-objects (trend points/totals) is
        # stripped element-by-element, so a lone element can't see its sibling 'Apr 15'/'21 (Today)' anchors. Detect the
        # temporal axis on the WHOLE array first and blank each object's bare-day `label`, then recurse. [orphan-day]
        if _clock_scrub_on() and _is_temporal_axis(cur):
            ph = _narrative_placeholder()
            for el in cur:
                if isinstance(el.get("label"), str) and (_CLOCK_STR.search(el["label"]) or _BARE_DAY.match(el["label"])):
                    el["label"] = ph
        for i, el in enumerate(cur):
            cur[i] = _strip_and_scrub(el, scalar=scalar)  # recurse: zero every data leaf in the element, keep chrome
    else:
        _set_at(out, path, _placeholder("series"))


def _strip_and_scrub(payload, scalar=_SENTINEL):
    """Return a DEEP COPY of `payload` with every DATA leaf stripped to a typed placeholder and every narrative-slot
    metadata string scrubbed. The metadata chrome (colors, labels, units, structural booleans) is left byte-identical.
    `scalar` overrides the scalar-leaf placeholder (honest-blank callers pass None → the host dashes it to '—')."""
    out = copy.deepcopy(payload)
    split = classify(payload)
    # 1) strip data leaves (the fabricated demo numbers/arrays/series) to typed placeholders. [VC-02]
    #    A series-of-objects keeps its array + chrome (only the element VALUE is zeroed) so per-element leaves refill.
    for d in split["data_leaves"]:
        if d["kind"] == "series":
            _strip_series(out, d["path"], scalar=scalar)
        else:
            _set_at(out, d["path"], _placeholder(d["kind"], scalar=scalar))
    # 2) scrub narrative-slot metadata strings (fabricated metric text) + clock-time strings (fabricated live
    #    timestamps — the seed scrubber/footer/history labels). [VC-02, META-01]
    narrative = _narrative_slots()
    ph = _narrative_placeholder()
    _walk_scrub(out, "", narrative, ph, clock=_clock_scrub_on(), provenance=_provenance_tokens())
    # 3) ROLE-BASED string scrub: blank STRING leaves whose SLOT ROLE is an active / derived-pick / event data
    #    assertion (worst*/selectedPanel picks, status/badge verdicts, anomaly-event titles, fabricated MFM_xx
    #    pointers) that the TYPE strip (step 1) and the key/value scrub (step 2) both miss — keeping every
    #    lookup-dictionary / enum / roster-identity chrome byte-identical. Role-based, config-driven, zero card_id.
    scrub_active_string_leaves(out, ph)
    # 4) SEED EVENT SKELETONS → []: an event/anomaly INSTANCE list whose elements survived steps 1–3 as blanked
    #    skeletons still renders N ghost event markers 'as if real' — the element COUNT is data; the honest rest state
    #    of an occurrence list is EMPTY. Role-based (role_scrub.event_parents), dictionaries kept. [class (d)]
    empty_event_instance_lists(out)
    # 5) STRING-EMBEDDED MEASUREMENTS → ph: an annotation string carrying a number+unit/percent ('Readiness: 70%',
    #    'peak 77%', 'at 17', 'Max - 420V') beside a numeric data sibling is the seed measurement in text form —
    #    scrubbed by config pattern + data-role; pure chrome captions without measurements stay. [class (b)]
    scrub_measured_annotation_strings(out, ph)
    return out


def strip_to_placeholders(payload, scalar=_SENTINEL):
    """BUILD-TIME ONLY — the canonical STRIP-AT-SOURCE. Invoked SOLELY by scripts/build_stripped_payloads.py to
    persist card_payloads.payload_stripped (155/155 built). Runtime readers use the STORED skeleton DIRECTLY (the
    producer/user_message read payload_stripped; a NULL fails loudly). The graft path calls blank_data_leaves for its
    OWN raw-default containers. Do NOT re-introduce a runtime caller — the stored column is the single source of truth.

    `payload` (a card's harvested card_payloads default) → metadata-only: every DATA leaf reset to its TYPED
    placeholder (scalar→0, array/series→[] via leaf_classify + editable config) and fabricated narrative/clock/date
    scrubbed. So the stored skeleton carries NO seed number at all — the FE mapper fills only what the live frame
    provides, un-framed cells stay the typed placeholder (0 / []), and the CMD_V2 component never crashes on a null it
    expected to .map()/.toLocaleString(). [strip-at-source, single source of truth]

    `scalar` overrides the scalar-leaf placeholder: the default (0) keeps props numeric for the LIVE-fill path (what
    the builder persists). The honest-blank display of an un-filled leaf is handled downstream by host/display_dash
    (the executor nulls a leaf during fill; display_dash dashes the null) — NOT by re-stripping a skeleton."""
    if not isinstance(payload, (dict, list)):
        return payload
    try:
        return _strip_and_scrub(payload, scalar=scalar)
    except Exception:
        return payload


def blank_data_leaves(subtree):
    """RUNTIME graft transform — the MINIMAL data-leaf blank the executor's container graft needs. A grafted container
    comes from the card's RAW default (dp['payload'], seed-bearing), so its own data leaves must be zeroed to typed
    placeholders before it is grafted (the DECLARED slot is overwritten by the live fill immediately; any UNdeclared
    sibling leaf must never carry a Storybook seed). This is the DATA-LEAF portion of the strip via ONE leaf_classify
    pass (scalar→0.0 to keep the prop numeric for the overwrite, array→[], series→per-element blanked) — NO narrative/
    clock/provenance scrub (a data CONTAINER carries no narrative prose). Returns a DEEP COPY; never raises. This is the
    graft's honest-blank, distinct from the full build-time strip_to_placeholders."""
    if not isinstance(subtree, (dict, list)):
        return subtree
    try:
        out = copy.deepcopy(subtree)
        for d in classify(subtree).get("data_leaves") or []:
            if d["kind"] == "series":
                _strip_series(out, d["path"])
            else:
                _set_at(out, d["path"], _placeholder(d["kind"]))
        return out
    except Exception:
        return None if isinstance(subtree, (dict, list)) else copy.deepcopy(subtree)


def null_scalar_data_leaves(subtree):
    """RUNTIME honest-blank transform — null ONLY the SCALAR data-leaf placeholders of an ALREADY-SEEDLESS stored
    skeleton (card_payloads.payload_stripped) from 0.0 → None, so host/display_dash renders '—' on a data-less asset
    (asset_no_data / asset_pending) instead of a fabricated '0.0 V' (the card-11/74 zero family). Array/series leaves and
    ALL chrome stay byte-identical — the input is already seedless, so only the scalar 0-placeholders need nulling for the
    dash; a series already carries blanked elements and an iterable []-array must stay iterable. Returns a DEEP COPY;
    never raises. Distinct from blank_data_leaves (graft: scalar→0.0, keeps props numeric for the immediate live
    overwrite) and the build-time strip_to_placeholders (full raw strip + narrative scrub)."""
    if not isinstance(subtree, (dict, list)):
        return subtree
    try:
        out = copy.deepcopy(subtree)
        for d in classify(subtree).get("data_leaves") or []:
            if d["kind"] == "scalar":
                _set_at(out, d["path"], _placeholder("scalar", scalar=None))
        return out
    except Exception:
        return None


def _walk_scrub(o, path, narrative, ph, clock=False, provenance=None, axis_temporal=False):
    provenance = provenance or set()
    if isinstance(o, dict):
        for k, v in list(o.items()):
            child = f"{path}.{k}" if path else k
            # inside a proven temporal axis, an object's `label` that is a BARE day-number is an orphaned date-axis
            # seed (siblings 'Apr 15'/'21 (Today)' already scrubbed) → neutralise it too. [date-axis orphan-day]
            if (axis_temporal and clock and k.lower() == "label" and isinstance(v, str)
                    and _BARE_DAY.match(v)):
                o[k] = ph
            elif isinstance(v, str) and (k.lower() in narrative or (clock and _CLOCK_STR.search(v))
                                         or v.strip().lower() in provenance):
                o[k] = ph                                    # narrative / clock / provenance-marker → honest neutral
            else:
                _walk_scrub(v, child, narrative, ph, clock=clock, provenance=provenance)
    elif isinstance(o, list):
        axis_t = clock and _is_temporal_axis(o)              # this list is a date/time axis → bare-day siblings are seeds
        for i, v in enumerate(o):
            if isinstance(v, str) and ((clock and _CLOCK_STR.search(v)) or v.strip().lower() in provenance
                                       or (axis_t and _BARE_DAY.match(v))):
                o[i] = ph                                    # seed clock label / provenance marker / orphan day → honest ''
            else:
                _walk_scrub(v, f"{path}[{i}]", narrative, ph, clock=clock, provenance=provenance,
                            axis_temporal=axis_t)


# ── slot-identity variant selection [META-07] ─────────────────────────────────────────────────────
def _pick_default_row(card_id, page_key, variant_hint=None, story_hint=None):
    """Choose the card's default (non-subcard) payload row by SLOT IDENTITY, not alphabetically. When the card has >1
    non-subcard row, prefer an exact story_id match, then a variant match; else fall back to the row default_for picks
    (rows[0]) so behaviour never regresses. Returns the row dict (with `page_key` = the page the row lives on) or None.
    HOME-PAGE FALLBACK [swap-target re-emit]: a swapped-IN / off-page swap candidate has NO row under the slot's
    page_key by construction (card_id → exactly one page in card_payloads) — fall back to the card's own home-page
    row so has_default/assemble see the card's REAL default instead of degrading to a sibling or 'no default'."""
    rows = card_payloads_for(card_id, page_key, include_subcards=False)
    for r in rows:
        r.setdefault("page_key", page_key)
    if not rows:
        from validate.payload_lookup import card_payloads_home
        rows = card_payloads_home(card_id, include_subcards=False)     # rows carry their own page_key
    if not rows:
        return None
    if story_hint:
        for r in rows:
            if r["story_id"] == story_hint:
                return r
    if variant_hint:
        for r in rows:
            if (r.get("variant") or "") == variant_hint:
                return r
    return rows[0]


# ── component-sibling fallback [META-01/05] ───────────────────────────────────────────────────────
def _primary_component(card_id):
    """The card's PRIMARY CMD_V2 component name (card_component_usage.is_primary). Drives the sibling-default reuse for
    a card that has no default of its own (e.g. card 8 AiSummary → reuse card 19/25's AiSummary default)."""
    rows = q("cmd_catalog",
             "SELECT component_name FROM card_component_usage "
             f"WHERE card_id={int(card_id)} AND is_primary='t' LIMIT 1")
    return rows[0][0] if rows and rows[0] and rows[0][0] else None


def _sibling_default(card_id):
    """A default payload from a SIBLING card that shares this card's primary component AND has a harvested default.
    Returns (payload, sibling_card_id, page_key, story_id) or None. This lets cards 6/8/160 reuse the
    LiveScrubberBar/AiSummary defaults harvested for 19/25 instead of the raw contract example. [META-01/05]"""
    comp = _primary_component(card_id)
    if not comp:
        return None
    rows = q("cmd_catalog",
             "SELECT DISTINCT u.card_id FROM card_component_usage u "
             f"WHERE u.component_name='{_esc(comp)}' AND u.is_primary='t' "
             f"AND u.card_id <> {int(card_id)} "
             "AND EXISTS (SELECT 1 FROM card_payloads p "
             "            WHERE p.card_id=u.card_id AND p.is_subcard=false) "
             "ORDER BY u.card_id")
    for r in rows:
        sib = int(r[0])
        # sibling may live on a different page_key — pull its default row directly (any page_key).
        srows = q("cmd_catalog",
                  "SELECT page_key, story_id FROM card_payloads "
                  f"WHERE card_id={sib} AND is_subcard=false ORDER BY story_id LIMIT 1")
        if not srows or not srows[0]:
            continue
        page_key, story_id = srows[0][0], srows[0][1]
        full = card_payloads_for(sib, page_key, include_subcards=False)
        if full:
            return full[0]["payload"], sib, page_key, story_id
    return None


# ── subcard-inclusive assembly [META-06] ──────────────────────────────────────────────────────────
def _nest_subcards(parent_payload, card_id, page_key):
    """Nest each subcard's (stripped) default under the parent at its slot. A subcard's `key_roles` names its target
    slot key; we nest the subcard payload's single content object at that key when the parent exposes it. Missing slots
    are left as-is (the parent's own default already carries them). Returns (assembled, subcard_count)."""
    rows = card_payloads_for(card_id, page_key, include_subcards=True)
    subs = [r for r in rows if r.get("is_subcard")]
    if not subs:
        return parent_payload, 0
    assembled = copy.deepcopy(parent_payload)
    nested = 0
    for s in subs:
        sp = s.get("payload") or {}
        # a subcard payload is typically {<slot>: {...}, "variant": "..."}; nest the non-variant content object(s).
        for k, v in sp.items():
            if k == "variant":
                continue
            if k in assembled and isinstance(assembled.get(k), list) and isinstance(v, (dict, list)):
                assembled[k].append(_strip_and_scrub({k: v})[k]); nested += 1
            elif k not in assembled:
                assembled[k] = _strip_and_scrub({k: v})[k]; nested += 1
    return assembled, nested


def assemble(card_id, page_key, *, variant_hint=None, story_hint=None):
    """Build the card's default-payload STATUS fact-sheet (subcard-inclusive, variant-correct, sibling-fallback,
    values stripped, literals scrubbed). NO AI, NO fetched number.

    Returns:
        {
          has_default: bool,               # True → a byte-identical default exists (own or sibling)
          source: 'own' | 'sibling' | None,# where the default came from
          story_id, variant,               # the chosen slot identity
          sibling_card_id,                 # set when source='sibling'
          payload,                          # the stripped + scrubbed + subcard-assembled default (or None)
          subcard_count,                    # how many subcard defaults were nested [META-06]
          data_leaf_count,                  # how many data leaves were stripped to placeholders
          reason,                           # honest reason when has_default=False, else None
        }
    """
    out = {
        "has_default": False, "source": None, "story_id": None, "variant": None,
        "sibling_card_id": None, "payload": None, "subcard_count": 0,
        "data_leaf_count": 0, "reason": None,
    }

    row = _pick_default_row(card_id, page_key, variant_hint=variant_hint, story_hint=story_hint)
    if row is not None:
        parent = row["payload"]
        # nest subcards from the page the row actually lives on (== page_key except on the home-page fallback)
        assembled, nsub = _nest_subcards(parent, card_id, row.get("page_key") or page_key)
        # STORED skeleton preference [stored stripped payloads]: when the card's OWN row carries the pre-built
        # payload_stripped (scripts/build_stripped_payloads.py) AND no subcard was nested (assembled IS the row
        # payload), use the stored column verbatim — the inspectable DB row, not a per-run transform. NULL / a
        # subcard-assembled tree → the identical on-the-fly strip, so an un-built row never breaks.
        stored = row.get("payload_stripped")
        if stored is not None and nsub == 0:
            stripped = copy.deepcopy(stored)
        else:
            stripped = _strip_and_scrub(assembled)
        out.update(has_default=True, source="own", story_id=row["story_id"],
                   variant=row.get("variant"), payload=stripped, subcard_count=nsub,
                   data_leaf_count=len(classify(parent)["data_leaves"]))
        return out

    # [META-01/05] no own default → component-sibling fallback.
    sib = _sibling_default(card_id)
    if sib is not None:
        payload, sib_id, sib_page, sib_story = sib
        stripped = _strip_and_scrub(payload)
        out.update(has_default=True, source="sibling", story_id=sib_story, variant=None,
                   sibling_card_id=sib_id, payload=stripped,
                   data_leaf_count=len(classify(payload)["data_leaves"]),
                   reason=rt.reason("literal_scrubbed"))
        return out

    # no own default AND no sibling → honest 'no default' (caller honest-blanks the card).
    out["reason"] = rt.reason("no_default_payload", card_id=card_id)
    return out


def has_default(card_id, page_key):
    """Convenience boolean: does this card have a recoverable (own OR sibling) default? Used by the swap-pool filter."""
    return assemble(card_id, page_key)["has_default"]
