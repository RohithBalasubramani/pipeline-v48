"""ems_exec/executor/fab_guards.py — DETERMINISTIC POST-FILL FABRICATION GUARDS (slot-name-INDEPENDENT class killers).

ONE post-fill pass that scans the FINISHED payload and blanks whole FABRICATION CLASSES regardless of the slot the AI
mislabeled — because the adversarial audit keeps finding the SAME class on a DIFFERENT slot each fire, so per-slot fixes
never generalize. Each guard is a CLASS killer, not a card fix; every blank carries a per-leaf reason on the SAME gaps
channel (gaps.py GAPS_KEY) the host pops. Runs as the LAST fabrication-guard pass in fill() — AFTER every honest-fill
pass (series + roster + yscale + display + freshness all done) so it sees the fully-assembled payload and never fights
an earlier honest fill; the three measurable RESCUES that follow (scalar_mean/scalar_tile/load_factor) only ADD
DB-verified values onto now-blank leaves (never fabricate), so no fabrication class survives this pass.

  CLASS 1 — EPOCH-MILLIS TIME-LEAK [card 46 maxLine/minLine/expectedMax/expectedMin ← [1783362600000,…]; card 59/43
            timestamps-as-data]. A leaf that is NOT a designated time axis (its key is NOT in the time-axis token set)
            but whose numeric value (scalar OR EVERY element of a numeric array) is an EPOCH-MILLIS magnitude
            (>= ~1e12, plausibly ms) is a timestamp that leaked into a value/scale leaf → BLANK it. Permanently kills the
            kind=time-over-application class no matter which slot the AI mislabels. A genuine reading (kW/V/A/%/count —
            all far below 1e12) is never touched.

  CLASS 2 — NULL-COLUMN-AS-READING [card 47 vThd.valuePct=0.0 while thd_compliance_v_avg is 0/61793 non-null]. A WRITTEN
            data leaf whose bound column is 100% NULL over the whole table (neuract.column_logged == False) must not
            ship 0.0/a placeholder as a reading — BLANK it (honest 'not measured — column all-null'). Only when the
            column is GENUINELY all-null; a real 0.0 measurement (its column IS logged) stays.

  CLASS 3 — NO-SOURCE VALUE [card 04 iThdPk=265.0 etc. — a peak-THD leaf filled from a non-THD source / with no source
            column]. A WRITTEN numeric leaf whose field has NO resolved source — no present column, no derivation fn,
            no nameplate rating, and no roster-source (the field/roster element is declared null) — must stay BLANK,
            never a stray value. A const/text literal the AI authored (label chrome) is NOT a no-source reading and is
            left alone; only numeric MEASUREMENT leaves are policed.

  CLASS 4 — UNSTRIPPED SEED-LEAK [card 73 backupHistory.series[*].legendValue = [52,71,85,43] byte-identical to the
            card-53 DEFAULT payload legendValue]. A leaf whose FINAL value is BYTE-IDENTICAL to the card's HARVESTED
            DEFAULT payload value at the SAME path AND was NOT written by any fill (its path is not in the written-path
            set / was never filled real) is an UNSTRIPPED SEED that survived into the served payload — BLANK it. Slot-
            name-INDEPENDENT (it never reasons about the key), OVER-REACH-SAFE: a FILLED-real leaf is protected by the
            written-path set (even if it coincidentally equals the seed scalar), and only ARRAY / STRING / compound
            seeds and NON-TRIVIAL scalars are policed (a bare 0 / None / '' / a single-digit is never blanked — those
            are legit values a real fill or an honest blank produces). CHROME WALL [metadata-stripping root cause,
            run r_627ae7b326]: a CHROME/STRUCTURAL leaf is SUPPOSED to equal the card's template default — CLASS 4
            polices only DATA leaves. Exempt: (a) a STRING leaf whose key (or its container's key) is in the
            chrome-string vocab (title/label/name/unit/prefix/suffix/legend/axis-label/tab/id/key/kind/color —
            fab_guards.chrome_string_keys, last-word matched so metricId/axisKey/xAxisLabel/railLabels qualify);
            (b) an axis/scale ARRAY (yLabels/yTicks/ticks/labels — the same vocab on a scalar list); (c) the existing
            structural-chrome + selector-key exemptions. The wall NEVER covers a leaf inside a LIST ELEMENT (a
            per-record narrative title/why/severity stays policed) and never a numeric reading — the card-73
            legendValue [52,71,85,43] numeric seed still blanks.

Every threshold is a DB knob (config.app_config, section 'fab_guards') with a code default — no magic literals baked
here. Never raises; a guard that cannot decide leaves the leaf untouched (never an over-reach blank). [atomic]
"""
from __future__ import annotations

from ems_exec.data import neuract as _nx
from config import nameplate_slot_map as _slot_map
from ems_exec.executor.paths import _toks, _leaf_at, _set_path, _leaf_path_for
from ems_exec.executor.series_fill import (_is_time_field, _element_value_key, _element_time_key)
from ems_exec.executor.gaps import GAPS_KEY


# ── DB knobs (code defaults) ──────────────────────────────────────────────────────────────────────────────────────────
def _epoch_floor():
    """The magnitude at/above which a bare number is treated as an epoch-MILLIS timestamp. 1e12 ms ≈ year 2001; every
    real EMS reading (kW/kWh/V/A/%/count/pf) sits many orders below it. DB knob fab_guards.epoch_ms_floor."""
    try:
        from config.app_config import cfg
        return float(cfg("fab_guards.epoch_ms_floor", 1_000_000_000_000))   # 1e12
    except Exception:
        return 1_000_000_000_000.0


def _guard_on(name):
    """Per-class valve (default on) — fab_guards.<name> == 'off' disables ONE class without a code change."""
    try:
        from config.app_config import cfg
        return str(cfg(f"fab_guards.{name}", "on")).strip().lower() != "off"
    except Exception:
        return True


# ── time-axis token set (CLASS 1 exemption) ─────────────────────────────────────────────────────────────────────────
# A leaf whose key is a designated TIME axis is ALLOWED to hold epoch ms. Union of the DB time_axis_keys vocab and the
# closed token set the contract names (…ticks/…labels/…indexes/…timestamps/axisStart/axisEnd/ts/time + a per-element
# point label/time key). Matched case-insensitively by suffix so mislabels on value/scale keys (maxLine/expectedMax/
# valuePct) never qualify. BOTH token sets are DB-driven (fab_guards.time_axis_suffixes / .time_axis_exact) with the
# code-default mirrors below — no hardcoded key list steers the CLASS-1 exemption.
_TIME_SUFFIXES_DEFAULT = ("ticks", "labels", "indexes", "timestamps", "timestamp",
                          "axisstart", "axisend", "axisstartms", "axisendms", "startms", "endms")
_TIME_EXACT_DEFAULT = ("ts", "time", "label")


def _time_axis_suffixes():
    """The key SUFFIXES that mark a leaf as a designated TIME axis (…ticks/…labels/…indexes/…timestamps/…startMs): a
    leaf whose key ENDS WITH one of these is allowed to hold epoch ms (CLASS-1 exemption). DB knob
    fab_guards.time_axis_suffixes (JSON list, lowercased) with the code-default mirror. Returned as a TUPLE for
    str.endswith()."""
    try:
        from config.app_config import cfg
        rows = cfg("fab_guards.time_axis_suffixes", None)
        if rows:
            return tuple(str(s).strip().lower() for s in rows)
    except Exception:
        pass
    return _TIME_SUFFIXES_DEFAULT


def _time_axis_exact():
    """The EXACT (whole-key) time-axis tokens (ts/time/label): a leaf whose key IS one of these is a time axis. DB knob
    fab_guards.time_axis_exact (JSON list, lowercased) with the code-default mirror."""
    try:
        from config.app_config import cfg
        rows = cfg("fab_guards.time_axis_exact", None)
        if rows:
            return {str(s).strip().lower() for s in rows}
    except Exception:
        pass
    return set(_TIME_EXACT_DEFAULT)


def _is_time_axis_key(key):
    k = (key or "").lower()
    if k in _time_axis_exact() or k.endswith(_time_axis_suffixes()):
        return True
    try:
        from config.vocab import vocab
        keys = {str(x).lower() for x in (vocab("time_axis_keys") or [])}
    except Exception:
        keys = set()
    return k in keys


def _reason(cause, metric):
    """The editable cmd_catalog.reason_template sentence for a machine cause; code-default to the cause key on outage."""
    try:
        from config.reason_templates import reason as _r
        return _r(cause, metric=metric)
    except Exception:
        return cause


def _add_gap(gaps, slot, cause, metric, column=None):
    gaps.append({"slot": slot, "cause": cause, "metric": str(metric),
                 "column": column, "fn": None, "reason": _reason(cause, metric)})


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  CLASS 1 — EPOCH-MILLIS TIME-LEAK — scan the WHOLE payload; blank a non-time leaf holding an epoch-ms magnitude.
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
def _is_epoch_scalar(v, floor):
    return _is_num(v) and v >= floor


def _is_epoch_array(v, floor):
    """Every numeric element is an epoch-ms magnitude (a non-empty, all-numeric, all-epoch array). None elements are
    ignored (an honest-blank point among timestamps), but at least one real epoch value must be present."""
    if not isinstance(v, list) or not v:
        return False
    nums = [x for x in v if x is not None]
    if not nums or any(not _is_num(x) for x in nums):
        return False
    return all(x >= floor for x in nums)


def _apply_class1(out, gaps):
    """CLASS 1 — recurse the FINISHED payload; wherever a NON-time-axis leaf (scalar OR all-numeric array) carries
    epoch-ms magnitudes, blank it. A time-axis key (…ticks/…indexes/…timestamps/ts/…) is exempt; series-of-OBJECTS are
    recursed per element so a mislabeled per-point value key (points[i].value ← ms) is caught while the point's own
    time key (points[i].time) is exempt. Two-pass: collect the paths (a stable recursion over `out`), then set each
    None/[] type-safely (a scalar → None; an all-epoch array → [] so the FE never .map()s a null)."""
    floor = _epoch_floor()
    to_null = []          # (path, is_array)

    def _walk(node, path, key):
        if isinstance(node, dict):
            for k, v in node.items():
                _walk(v, f"{path}.{k}" if path else str(k), k)
            return
        if isinstance(node, list):
            if not _is_time_axis_key(key) and _is_epoch_array(node, floor) \
                    and all(_is_num(x) or x is None for x in node):
                to_null.append((path, True))
                return
            for i, el in enumerate(node):
                _walk(el, f"{path}[{i}]", key)
            return
        if not _is_time_axis_key(key) and _is_epoch_scalar(node, floor):
            to_null.append((path, False))

    _walk(out, "", "")
    for path, is_arr in to_null:
        key = _toks(path)[-1] if _toks(path) else path
        _set_path(out, path, [] if is_arr else None)
        _add_gap(gaps, path, "epoch_ms_leak", key)
    return {p for p, _ in to_null}


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  CLASS 2 / CLASS 3 — per-WRITTEN-leaf source audit (needs the declared fields + the meter's present/logged columns).
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
_ROWS_CACHE: dict = {}


def _table_has_rows(asset_table):
    """Is the table demonstrably REACHABLE with at least one row? The CLASS-2 conclusiveness gate: a genuine all-null
    column is only distinguishable from a DB outage when the table itself HAS data (neuract.latest_ts is not None). DB
    down / empty / missing table → None → False → CLASS 2 stays its hand (never blanks a real reading it can't disprove).
    Cached per table per process (latest_ts is itself cached upstream). Never raises."""
    if not asset_table:
        return False
    hit = _ROWS_CACHE.get(asset_table)
    if hit is not None:
        return hit
    try:
        ok = _nx.latest_ts(asset_table) is not None
    except Exception:
        ok = False
    _ROWS_CACHE[asset_table] = ok
    return ok


def _field_leaf_path(out, field):
    """The dotted leaf path a field resolved to (the SAME resolution fill() used: data.<slot> or <slot>, then metric,
    then target_column). None when the skeleton has no such leaf."""
    slot = field.get("slot") or field.get("target_column") or field.get("metric")
    return (_leaf_path_for(out, slot)
            or _leaf_path_for(out, field.get("metric"))
            or _leaf_path_for(out, field.get("target_column")))


def _field_has_source(field, present_cols):
    """Does this field carry a RESOLVED data source (ANY of the executor's fill paths)? A superset of every legit fill:

      • kind='time'                       — fills from the card's own bucket axis (a real derived time source);
      • a PRESENT column (raw/bucketed/event) — the meter carries it;
      • a derivation fn/metric that binds   — kind='derived', OR a column-less field whose fn/metric resolves a
        cmd_catalog.derivation_binding row (metric='loadPct' → kpiKwLoadPctOfRated — the column-less series family);
      • a nameplate rating slot             — a const/text slot the slot-map maps to a real rating.

    False = NONE of those resolved: the field is declared null (its roster/binding has no source) and any numeric value
    surviving on its leaf is a no-source stray (CLASS 3). A const/text LITERAL is handled by the caller (chrome)."""
    kind = (field.get("kind") or "raw").lower()
    if kind == "time":
        return True                                             # fills from the card's bucket axis (real source)
    if kind == "derived" and (field.get("fn") or field.get("metric")):
        return True
    col = field.get("column")
    if col and col in present_cols:
        return True
    # a COLUMN-LESS series/scalar field whose fn/metric resolves a derivation_binding row IS sourced (the column-less
    # family — the same resolution indexed_families/wildcards use). Reuse that ONE resolver, never re-implement it.
    try:
        from ems_exec.executor.indexed_families import _binding_for_field
        if _binding_for_field(field):
            return True
    except Exception:
        pass
    # a const/text nameplate slot resolves from the real rating — a real source
    rk = _slot_map.rating_key_for(field.get("slot")) or _slot_map.rating_key_for(field.get("metric"))
    if rk:
        return True
    return False


def _apply_class2_class3(out, fields, present_cols, asset_table, gaps, skip_paths):
    """For every field the executor filled, audit its leaf's SOURCE:

      CLASS 2 — the field binds a PRESENT column that is 100% NULL on the table (neuract.column_logged == False): a
                written numeric leaf is 0.0/placeholder posing as a reading → blank it ('not measured — column
                all-null'). Present-and-logged columns (a real 0.0) are exempt.

      CLASS 3 — the field has NO resolved source (no present column, no fn, no nameplate) yet a NUMERIC value survives
                on its leaf → blank it ('no source — value has no measuring column'). const/text literals (chrome) and
                already-blank leaves are exempt; a genuine literal string label is never policed.

    Only WRITTEN numeric MEASUREMENT leaves are touched (scalar, or a numeric array / series-of-objects value key).
    `skip_paths` = the CLASS-1-blanked paths (already handled, don't double-report). Never raises."""
    for field in fields:
        kind = (field.get("kind") or "raw").lower()
        if kind in ("const", "text"):
            # a const/text nameplate slot with a rating source is real; a bare literal is AI-authored chrome, not a
            # measurement — CLASS 3 does NOT police literal strings (labels/axis chrome). Skip entirely.
            # EXCEPT: a const/text that CLAIMS source='live' yet has NO column and NO rating source is a LITERAL DRESSED
            # AS A LIVE READING (card 78 tapPosition kpis 'AUTO' / status.tone 'Nominal', column:None) — a fabricated
            # live-state, not chrome. Blank that string leaf; a genuine static label (source != 'live') stays untouched.
            if _guard_on("no_source") and str(field.get("source") or "").lower() == "live":
                _rk = _slot_map.rating_key_for(field.get("slot")) or _slot_map.rating_key_for(field.get("metric"))
                _c0 = field.get("column")
                if not _rk and not (_c0 and _c0 in present_cols):
                    _p = _field_leaf_path(out, field)
                    _cur = _leaf_at(out, _p) if _p else None
                    if _p and _p not in skip_paths and isinstance(_cur, str) and _cur.strip() not in ("", "—"):
                        _set_path(out, _p, None)
                        _add_gap(gaps, _p, "no_source_value", field.get("label") or field.get("slot") or "value", column=None)
            continue
        path = _field_leaf_path(out, field)
        if not path or path in skip_paths:
            continue
        cur = _leaf_at(out, path)
        col = field.get("column")
        has_col = bool(col and col in present_cols)

        # CLASS 2 — bound column present but 100% NULL over the whole table → any written value is not a reading.
        # CONCLUSIVENESS GATE (never over-reach on a DB outage): column_logged() returns False BOTH for a genuinely
        # all-null column AND for an unreachable/errored read — so we only trust the all-null verdict when the table is
        # demonstrably REACHABLE and has rows (_table_has_rows via latest_ts). DB down / empty table → inconclusive →
        # leave the real reading alone (the honest fill stands; a guard never blanks what it cannot prove fabricated).
        if _guard_on("null_column") and has_col and _table_has_rows(asset_table) \
                and not _nx.column_logged(asset_table, col):
            if _blank_numeric_leaf(out, path, cur):
                metric = field.get("label") or field.get("metric") or col
                _add_gap(gaps, path, "null_column_reading", metric, column=col)
            continue

        # CLASS 3 — no resolved source at all, yet a numeric value survived → stray, blank it.
        if _guard_on("no_source") and not _field_has_source(field, present_cols):
            if _blank_numeric_leaf(out, path, cur):
                metric = field.get("label") or field.get("metric") or field.get("slot") or "value"
                _add_gap(gaps, path, "no_source_value", metric, column=col)


def _blank_numeric_leaf(out, path, cur):
    """Blank the leaf at `path` IF it currently carries a NUMERIC value (scalar, a numeric array, or a series-of-objects
    whose value key holds numbers). Returns True when something was blanked. A leaf already blank (None/'—'/[]/all-None)
    is left as-is (no double work); a non-numeric string/dict leaf is never touched (not a measurement)."""
    if _is_num(cur):
        _set_path(out, path, None)
        return True
    if isinstance(cur, list) and cur:
        # numeric array → [] ; series-of-objects → blank each element's value key
        if all(_is_num(x) or x is None for x in cur) and any(_is_num(x) for x in cur):
            _set_path(out, path, [])
            return True
        if all(isinstance(e, dict) for e in cur):
            vk = _element_value_key(cur[0])
            blanked = False
            if vk:
                for el in cur:
                    if _is_num(el.get(vk)):
                        el[vk] = None
                        blanked = True
            return blanked
    return False


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  CLASS 4 — UNSTRIPPED SEED-LEAK — a leaf byte-identical to the DEFAULT payload at the same path, never filled → blank.
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
def _written_toks(written_paths):
    """The written-path set as tokens-tuples (both address forms fill() records: 'data.foo.bar' and 'foo.bar'). A leaf
    at any of these paths — or UNDER any of them (a grown-array element path) — was filled real and is seed-exempt."""
    out = set()
    for p in (written_paths or ()):
        toks = tuple(_toks(p))
        if toks:
            out.add(toks)
    return out


def _is_written(toks, written):
    """True when the leaf `toks` was filled real: an exact written path, OR a leaf UNDER a written prefix (a grown-array
    container path covers its element leaves), OR a written path under THIS leaf (a filled child means the container is
    not an inert seed)."""
    if toks in written:
        return True
    for w in written:
        if len(w) <= len(toks) and tuple(toks[:len(w)]) == w:
            return True                                         # this leaf is at/under a written path
        if len(toks) < len(w) and tuple(w[:len(toks)]) == toks:
            return True                                         # a written path lies under this leaf (filled child)
    return False


def _trivial_int_magnitude():
    """|v| strictly below this integer magnitude makes an INTEGER-valued scalar too trivial to police as a seed (0..9
    by default — a value a real fill or an honest blank legitimately produces, so equal-to-default there is
    coincidental). DB knob fab_guards.trivial_int_magnitude (int) with code default 10."""
    try:
        from config.app_config import cfg
        return float(cfg("fab_guards.trivial_int_magnitude", 10))
    except Exception:
        return 10.0


def _trivial_string_maxlen():
    """A stripped STRING of this length or shorter is too trivial to police as a seed (a 1-char string by default); a
    string LONGER than this is a seed shape worth policing. The SAME boundary drives _trivial_scalar (<=) and
    _seed_worth_policing (>). DB knob fab_guards.trivial_string_maxlen (int) with code default 1."""
    try:
        from config.app_config import cfg
        return int(cfg("fab_guards.trivial_string_maxlen", 1))
    except Exception:
        return 1


def _trivial_scalar(v):
    """A scalar too trivial to police as a seed-leak: None / bool / '' / a single-digit magnitude (0..9) / a 1-char
    string. Blanking such a value would over-reach — a real fill or an honest blank legitimately produces it, so an
    equal-to-default here is coincidental, not a surviving seed. Non-trivial scalars (multi-digit / decimal / longer
    strings) ARE policed. The 0..9 magnitude and 1-char thresholds are DB knobs (fab_guards.trivial_int_magnitude /
    .trivial_string_maxlen) with code-default mirrors."""
    if v is None or isinstance(v, bool):
        return True
    if isinstance(v, str):
        return len(v.strip()) <= _trivial_string_maxlen()
    if isinstance(v, (int, float)):
        return abs(v) < _trivial_int_magnitude() and float(v) == int(v)   # 0..9 integer magnitude — trivial
    return False


def _structural_chrome_keys():
    """The leaf KEYS whose value is DESIGN-SYSTEM STRUCTURAL CHROME — a series/point IDENTITY, POSITION, or STYLE leaf
    that is byte-identical to its default BY DESIGN (the harvested skeleton), never a rendered reading. A leaf under
    one of these keys is EXEMPT from the seed-leak comparison so CLASS 4 never blanks a legend colour / series key /
    dashed flag / tick separator just because it equals the default (the card-73 over-reach: series[i].key='index',
    .color='#444443', .dashed=false all equal their defaults — blanking them breaks the component's series mapping).
    DB-driven vocab fab_guards.structural_chrome_keys (JSON list, lowercased) with a code-default mirror.

    DELIBERATELY OMITS the VALUE-RENDERING and NARRATIVE keys (legendValue / warn / trip / value / val / why / title /
    severity / caption / note / source / delta / deltaTone) — those DO surface as on-screen numbers or narrative, so a
    stale-seed one IS the fabrication CLASS 4 must catch (card-73 legendValue; the card-61/62 event narratives; the
    card-79 stats value). This set is STRICTLY the identity/position/style keys the design ships verbatim, PLUS the
    series/point DISPLAY-NAME keys (label/name — the harvested series title 'Autonomy index' that the byte-identity gate
    also keeps verbatim; a SERIES display name is chrome, never a reading — event narrative rides `title`/`why`, which
    stay policed): key/color/dashed/dash/stroke/fill/order/separator/from/to/radius/opacity/z/zindex/width/span/index/
    decimals/align/variant/icon/id/label/name/axis/orientation/domain.

    `axis`/`orientation`/`domain` are the SCALE-BINDING identity of a config-object series/axis (which y-scale a line
    binds to, its side, its range) — pure positional chrome that equals its default BY DESIGN, never a rendered reading;
    listed so a dual-axis config series (cards 61/62) keeps its axis binding when it byte-matches the default. (The
    per-element value/threshold-LINE keys warn/trip stay OMITTED here — in a REAL data series they surface as readings;
    a config-object series exempts them wholesale via `_is_config_object_series`, not by key.)"""
    default = {"key", "color", "colour", "dashed", "dash", "stroke", "fill", "order", "separator",
               "from", "to", "radius", "opacity", "z", "zindex", "width", "span", "index",
               "decimals", "align", "variant", "icon", "id", "label", "name",
               "axis", "orientation", "domain"}
    try:
        from config.app_config import cfg
        rows = cfg("fab_guards.structural_chrome_keys", None)
        if rows:
            return {str(k).strip().lower() for k in rows}
    except Exception:
        pass
    return default


def _chrome_selector_keys():
    """The leaf KEYS whose value is PRESENTATION-CONFIG the component INDEXES / SWITCHES / SCALES on — an active-VIEW
    selector, an enum DIRECTION/glyph, an event/strip filter SELECTOR, a gauge SCALE/limit, a tone/badge/ieee enum.
    Unlike the structural-chrome identity keys above, these do NOT surface as a reading but the CMD_V2 component uses
    them UNGUARDED as a switch discriminant or a scale denominator: a null/0 here does not just look wrong — it CRASHES
    SSR (RT_DIR_PRESETS[null].color, rangeForPreset(preset=null)→undefined.start) or EMPTIES the card (views[view=null]
    = nothing; a zero-max gauge can't draw a bar). So a leaf under one of these keys must keep its DEFAULT-payload value:
    it is NEVER blanked by the seed-leak class (exempt like structural chrome) AND is RESTORED from the default when an
    upstream pass (the Layer-2 byte-identity gate, an honest-blank, or CLASS 4) stripped it to null/0/'' — see
    restore_chrome() below. This generalizes FIXB's chrome-preservation from series-identity chrome to the enum/selector/
    scale family. DB-driven vocab fab_guards.chrome_selector_keys (JSON list, lowercased) with a code-default mirror.

    Covers (case-insensitive, by leaf key): the active-view selector (view); enum direction/glyph (dir/glyph/glyphcolor);
    event/strip filter selectors (preset/resample); gauge scale/limit (scalemaxpct/limitpct/scalemax/defaultlimit); and
    tone/badge/ieee enums (tone/dstone/ieeestate). NOT a measurement key — every one is presentation config, so restoring
    it can never fabricate a reading (a genuine DATA leaf that honest-blanks still blanks; its key is not in this set)."""
    default = {"view", "dir", "glyph", "glyphcolor", "preset", "resample",
               "scalemaxpct", "limitpct", "scalemax", "defaultlimit",
               "tone", "dstone", "ieeestate"}
    try:
        from config.app_config import cfg
        rows = cfg("fab_guards.chrome_selector_keys", None)
        if rows:
            return {str(k).strip().lower() for k in rows}
    except Exception:
        pass
    return default


def _is_structural_chrome(toks):
    """True when the leaf's OWN key is a structural-chrome key (identity/position/style) OR a chrome SELECTOR/enum/scale
    key (view/preset/dir/scaleMaxPct/tone/…) — exempt from seed policing (a leaf byte-identical to the default here is
    presentation config by design, never a surviving data seed; blanking it crashes/empties the CMD_V2 component)."""
    if not toks:
        return False
    k = str(toks[-1]).lower()
    return k in _structural_chrome_keys() or k in _chrome_selector_keys()


# ── CLASS-4 CHROME WALL [metadata-stripping root cause, run r_627ae7b326] ────────────────────────────────────────────
def _chrome_string_keys():
    """The leaf KEYS whose STRING value (or whose axis/scale scalar-ARRAY value) is CARD CHROME — a title / unit /
    display label / prefix / legend text / axis label / renderer directive that is byte-identical to the harvested
    default BY DESIGN. The metadata-only emit never re-authors these (the producer copies them verbatim from
    card_payloads), so equal-to-default here is CORRECT, never a surviving data seed — blanking them ships nameless,
    unitless cards and an emptied yLabels sends the CMD_V2 LinePath y-domain degenerate. Matched by the key's LAST
    camel/snake WORD (metricId→id, axisKey→key, xAxisLabel→label, railLabels→labels, unitSuffix→suffix, yTicks→ticks)
    so the whole key family is covered without enumerating every compound. DELIBERATELY OMITS every value/narrative
    word (value/val/why/severity/caption/note/delta — legendValue's last word is 'value', so the card-73 numeric seed
    stays policed). DB-driven vocab fab_guards.chrome_string_keys (JSON list, lowercased) + this code-default mirror."""
    default = {"title", "label", "labels", "name", "unit", "units", "prefix", "suffix",
               "legend", "legends", "axislabel", "xaxislabel", "yaxislabel",
               "tab", "id", "key", "kind", "color", "colour", "ticks"}
    try:
        from config.app_config import cfg
        rows = cfg("fab_guards.chrome_string_keys", None)
        if rows:
            return {str(k).strip().lower() for k in rows}
    except Exception:
        pass
    return default


def _key_words(key):
    """Split a leaf key into lowercase words on camelCase / snake / kebab boundaries: 'xAxisLabel' → ['x','axis',
    'label'], 'metricId' → ['metric','id'], 'railLabels' → ['rail','labels']. Never raises."""
    try:
        s = _re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(key or ""))
        return [w.lower() for w in _re.split(r"[^A-Za-z0-9]+", s) if w]
    except Exception:
        return []


def _is_chrome_key(key):
    """True when `key` is a chrome-string key: an exact (lowercased) vocab match OR its LAST word is in the vocab
    (compound keys — metricId / axisKey / xAxisLabel / reactivePowerTrendLabel — inherit their family's chrome-ness)."""
    vocab = _chrome_string_keys()
    kl = str(key or "").lower()
    if kl in vocab:
        return True
    words = _key_words(key)
    return bool(words) and words[-1] in vocab


def _is_chrome_leaf(node, toks, in_element):
    """The CLASS-4 chrome wall: is this leaf CHROME (supposed to equal the template default) rather than a DATA seed?

      (a) a STRING leaf whose OWN key is chrome (title/unit/…Label/…Key/…Id), or whose immediate CONTAINER key is
          chrome (railLabels.dkwDt — every string inside a *Labels/*Legend container is display text);
      (b) an axis/scale ARRAY — a scalar list (strings or numbers, no dict/list elements) under a chrome key
          (yLabels / yTicks / ticks / labels / timeLabels);
      (c) never inside a LIST ELEMENT (`in_element`) — a per-record narrative leaf (events[i].title / .why /
          .severity) is DATA that surfaces on-screen, so a stale seed there stays policed; series-identity chrome
          inside elements is already exempt via the structural-chrome exact keys (label/name/key/color).

    Only ever SKIPS a blank (never writes), so the worst mis-classification keeps a presentation string — it can
    never fabricate a reading. Numeric SCALARS are never chrome here (a numeric seed always stays policed)."""
    if in_element or not toks:
        return False
    if isinstance(node, str):
        if _is_chrome_key(toks[-1]):
            return True
        return len(toks) >= 2 and _is_chrome_key(toks[-2])
    if isinstance(node, list) and not any(isinstance(e, (dict, list)) for e in node):
        return _is_chrome_key(toks[-1])
    return False


def _is_config_object_series(node):
    """True when `node` is a CONFIG-OBJECT series/axis array — a non-empty list of dict elements where NO element carries
    a data VALUE key or a data TIME key (its dicts are pure line/axis DEFINITIONS: {key, axis, name, trip, warn, color} or
    {id, domain, orientation, …} — cards 61/62). This is the SAME element-shape discriminator fill() uses to RESTORE such
    an array from the default byte-identical: a config-object series equals its default BY DESIGN, so CLASS 4 must exempt
    the WHOLE subtree (axis binding, threshold LINES warn/trip, scale range) — not blank leaves the fill deliberately kept.
    A REAL data series (its elements carry `values`/`value`/`time` — card 73) is NOT a config-object series, so its
    rendered legendValue seed is still policed. REUSES series_fill._element_value_key/_element_time_key (the DB vocab),
    never re-implements the shape test. Never raises."""
    if not isinstance(node, list) or not node:
        return False
    if not all(isinstance(e, dict) for e in node):
        return False
    try:
        for el in node:
            if _element_value_key(el) is not None or _element_time_key(el) is not None:
                return False                                    # a data-bearing element → a real series, not config chrome
    except Exception:
        return False
    return True


def _seed_worth_policing(v):
    """True when the value is a SEED shape worth policing for a leak: an ARRAY (non-empty), a STRING (len>1), or a
    NON-TRIVIAL scalar. A dict is recursed (never blanked whole). Prefers array/string/compound seeds + non-trivial
    scalars (the DEFECT-73 legendValue array), never a bare 0/None/''. The STRUCTURAL-chrome carve-out is applied by
    the caller via `_is_structural_chrome(toks)` so a series key/colour/dashed leaf is never blanked even here."""
    if isinstance(v, list):
        return len(v) > 0
    if isinstance(v, str):
        return len(v.strip()) > _trivial_string_maxlen()
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return not _trivial_scalar(v)
    return False


def _is_numeric_data_seed(v):
    """A NUMERIC seed shape worth policing even in the METADATA branch: a NON-TRIVIAL numeric SCALAR (a rendered legend
    reading like legendValue=52) or a non-empty ALL-NUMERIC array ([52,71,85,43]). A number that surfaces on-screen is a
    reading, never real metadata — so when the strip KEEPS it byte-identical (raw==stripped, a strip MISS) it must still
    be policed. Excludes a trivial scalar (a value a real fill / honest blank could reproduce) via `_trivial_scalar`."""
    if _is_num(v):
        return not _trivial_scalar(v)
    if isinstance(v, list) and v:
        nums = [x for x in v if x is not None]
        return bool(nums) and all(_is_num(x) for x in nums)
    return False


def _is_chrome_leaf_key(toks):
    """True when the leaf's OWN key OR its immediate CONTAINER key is ANY chrome key (structural-chrome ∪ chrome-selector
    ∪ chrome-string vocab). Used to EXEMPT a numeric metadata leaf (decimals / order / scaleMaxPct / index) from the
    numeric-seed carve-out while still policing a numeric DATA reading under a NON-chrome key (legendValue — last word
    'value', deliberately omitted from every vocab). Pure vocab lookup, no shape heuristic. Never raises."""
    if not toks:
        return False
    try:
        if _is_structural_chrome(toks):                         # own key ∈ structural-chrome ∪ chrome-selector
            return True
        if _is_chrome_key(str(toks[-1])):                       # own key ∈ chrome-string family
            return True
        if len(toks) >= 2 and _is_chrome_key(str(toks[-2])):    # immediate container key ∈ chrome-string family
            return True
    except Exception:
        return False
    return False


_DATA_VALUE_KEYS_DEFAULT = {"value", "val"}


def _data_value_keys():
    """The RENDERED-VALUE word vocab: a leaf whose key's LAST camel/snake WORD is one of these (value/val →
    legendValue / summaryVal) is an on-screen READING, deliberately OMITTED from every chrome vocab. Used to NARROW the
    metadata-branch numeric carve-out: a numeric leaf the strip KEPT verbatim (raw==stripped) is a strip-missed seed
    ONLY when its key is a data-value word — so legendValue is policed while presentation CONFIG the strip legitimately
    keeps (curveSag / rowHeight / dimOpacity / bandThresholds.divisors.kw / minWidth) is NEVER touched. DB knob
    fab_guards.data_value_keys (JSON list, lowercased) with the code-default mirror. Class-level field-kind vocab, not a
    per-card/per-slot hardcode."""
    try:
        from config.app_config import cfg
        rows = cfg("fab_guards.data_value_keys", None)
        if rows:
            return {str(k).strip().lower() for k in rows}
    except Exception:
        pass
    return set(_DATA_VALUE_KEYS_DEFAULT)


def _is_data_value_key(key):
    """True when `key`'s LAST camel/snake word is a rendered-value word (value/val): legendValue→value, summaryVal→val.
    Mirrors _is_chrome_key's last-word match so a compound reading key inherits its family. Never raises."""
    vocab = _data_value_keys()
    kl = str(key or "").lower()
    if kl in vocab:
        return True
    words = _key_words(key)
    return bool(words) and words[-1] in vocab


def _blank_seed(cur):
    """The honest-blank TYPE for a leaked seed leaf: an array → [] (the FE never .map()s a null); everything else → None."""
    return [] if isinstance(cur, list) else None


import re as _re

# a DATA MAGNITUDE embedded in a chrome label: a number at a WORD BOUNDARY followed by a KNOWN PHYSICAL UNIT — '131A',
# '600 kVA', '3228 kW', '13.5%'. The word-boundary lookbehind (?<![\w#.]) excludes a hex COLOUR ('#86a86b'), a series
# KEY, and any digit embedded in an identifier; the explicit unit vocab excludes a bare year/index. Only a genuine
# rating/limit/range value baked into a label text (card 69 'Rated: 131A') matches. DB-driven unit vocab, code default.
_MAG_UNITS_DEFAULT = ("kVArh", "MVArh", "kVAh", "MVAh", "kWh", "MWh", "kVAr", "MVAr", "kVA", "MVA",
                      "kW", "MW", "kV", "kA", "VAr", "VA", "Wh", "Hz", "A", "V", "W", "%")


def _mag_units():
    try:
        from config.app_config import cfg
        rows = cfg("fab_guards.magnitude_units", None)
        if isinstance(rows, (list, tuple)) and rows:
            return tuple(str(u) for u in rows)
    except Exception:
        pass
    return _MAG_UNITS_DEFAULT


def _mag_re():
    units = "|".join(sorted((_re.escape(u) for u in _mag_units()), key=len, reverse=True))
    return _re.compile(r"(?<![\w#.])\d[\d,]*(?:\.\d+)?\s*(?:" + units + r")\b")


_MAGNITUDE_RE = _mag_re()


def _embeds_data_magnitude(v):
    """True when a STRING chrome label embeds a numeric data magnitude+unit (a rating/limit/range value baked into the
    label text). Such a label is NOT pure chrome — when it equals a stale default seed it must be neutralized, not
    blanket-exempted. Never raises."""
    try:
        return isinstance(v, str) and bool(_MAGNITUDE_RE.search(v))
    except Exception:
        return False


def _strip_stale_magnitude(s):
    """Neutralize the stale data magnitude in a chrome label seed: 'Rated: 131A' → 'Rated: —' (keeps the label chrome,
    drops the fabricated number). Returns None if nothing is left but the number itself."""
    try:
        out = _MAGNITUDE_RE.sub("—", s).strip()
        return out or None
    except Exception:
        return None


# a sentinel meaning "no RAW-default value is available at this leaf" — either the whole raw default (shape_ref) was
# not threaded through (older callers pass None) OR the raw default's structure diverges from the stripped skeleton at
# this path. Such a leaf can't be classified by the raw-vs-stripped predicate and falls back to the legacy wall.
_NO_RAW = object()


def _apply_class4_seed_leak(out, default_payload, written, gaps, raw_default=None):
    """CLASS 4 — walk `out`, the STRIPPED default (`default_payload`, = card_payloads.payload_stripped) and the RAW
    harvested default (`raw_default`, = shape_ref = card_payloads.payload) in parallel; blank a leaf that is an
    UNSTRIPPED **DATA** seed (a fabricated reading that survived byte-identical to the harvested seed and was never
    filled real).

    THE AUTHORITATIVE WALL is the strip-builder's OWN data/metadata classification, ALREADY PERSISTED in the DB as the
    RAW-vs-STRIPPED diff (payload vs payload_stripped — the strip zeroes DATA leaves to typed placeholders and keeps
    METADATA leaves VERBATIM). Per leaf:
      • raw == stripped  → METADATA (the strip left it untouched — a title / order array / label / colour / unit /
        preset value / axis binding). It is SUPPOSED to equal the template default (the L2 byte-identity gate copies it
        verbatim) → it is NEVER a seed candidate, WHATEVER its key. This one predicate REPLACES the key-vocab chrome
        checks for correctness (those can only under-cover — the compound `stackOrder`/`columnOrder`/`titleConnector`/…
        keys the whack-a-mole vocab kept missing are ALL metadata here and survive automatically). [root cause fix]
      • raw != stripped  → DATA (the strip turned the raw seed into a placeholder). Its seed test is byte-identity to
        the RAW default (`node == raw`): a data leaf equal to the harvested seed and never filled real is an unstripped
        seed → blank it. This PRESERVES CLASS 4's real charter (card-73 legendValue: a data leaf equal to its raw seed
        still blanks); an honest-blank placeholder (`node == stripped != raw`) or a real fill is left alone.

    Fallback (raw_default is None, or a raw leaf is absent at this path — older callers / structural divergence): use
    the LEGACY chrome-vocab wall + stripped comparison, preferring to UNDER-blank (blanking chrome is the harm removed).

    Over-reach-safe throughout: only non-trivial array/string/compound seeds (`_seed_worth_policing`), only UNWRITTEN
    leaves; a CONFIG-OBJECT series/axis subtree (cards 61/62) is exempt wholesale; a dict is recursed. Never raises."""
    if not isinstance(default_payload, dict):
        return set()
    have_raw = isinstance(raw_default, dict)
    blanked = set()

    def _do_blank(node, path, toks, strip_mag):
        _set_path(out, path, _strip_stale_magnitude(node) if strip_mag else _blank_seed(node))
        blanked.add(toks)
        _add_gap(gaps, path, "unstripped_seed", toks[-1] if toks else path)

    def _walk(node, dflt, raw, path, toks, in_el=False):
        if isinstance(node, dict):
            if not isinstance(dflt, dict):
                return
            raw_is_dict = isinstance(raw, dict)
            for k, v in list(node.items()):
                if isinstance(k, str) and k.startswith("_"):
                    continue                                   # reserved telemetry — never policed
                if k not in dflt:
                    continue                                   # no default at this path — nothing to compare
                rv = raw[k] if (raw_is_dict and k in raw) else _NO_RAW
                _walk(v, dflt[k], rv, f"{path}.{k}" if path else str(k), toks + (str(k),), in_el)
            return
        if isinstance(node, list):
            # a CONFIG-OBJECT series/axis array (elements are pure line/axis DEFINITIONS — no value/time key: cards 61/62)
            # equals its default BY DESIGN and is restored-from-default by fill(); CLASS 4 EXEMPTS the whole subtree so it
            # never blanks an axis binding / threshold LINE (warn/trip) / scale range that legitimately mirrors the default.
            if _is_config_object_series(node):
                return
            # a list of OBJECTS is a container — recurse per element so a seed leaf DEEPER in the object is caught while a
            # sibling real leaf is left alone (card 73: series[i].legendValue leaks while series[i].values is real). A
            # list of SCALARS is itself a leaf (the legendValue / stackOrder array) — fall through to the leaf test below.
            if isinstance(dflt, list) and any(isinstance(e, dict) for e in node):
                raw_is_list = isinstance(raw, list)
                for i, el in enumerate(node):
                    if i < len(dflt):
                        rv = raw[i] if (raw_is_list and i < len(raw)) else _NO_RAW
                        _walk(el, dflt[i], rv, f"{path}[{i}]", toks + (str(i),), True)
                return
        # a leaf (scalar / scalar-array / str)
        if not _seed_worth_policing(node):
            return
        # EXCEPT a chrome LABEL that bakes a stale data magnitude into its text ('Rated: 131A', 'Limit: 5%') — a
        # fabricated reading dressed as chrome (card 69): even as metadata, when it equals the seed the number is stripped.
        _mag_label = _embeds_data_magnitude(node)

        # ── AUTHORITATIVE WALL: the strip's own DATA/METADATA classification (raw vs stripped) ──────────────────────
        if have_raw and raw is not _NO_RAW:
            try:
                is_metadata = (raw == dflt)          # strip kept it byte-identical → metadata; changed it → data
            except Exception:
                is_metadata = None
            if is_metadata is True:
                # METADATA — the strip kept it byte-identical → SUPPOSED to equal the template default; NEVER a data seed
                # for a STRING / non-numeric ARRAY / chrome leaf (this is the fix for the stackOrder/columnOrder/
                # titleConnector/… over-blank — those are string/array chrome the strip keeps verbatim). TWO carve-outs,
                # both only on an UNWRITTEN, byte-identical-to-raw leaf:
                #   (a) a magnitude-bearing chrome LABEL ('Rated: 131A' → 'Rated: —') — a fabricated reading dressed as text;
                #   (b) a NUMERIC RENDERED-VALUE leaf the strip MISSED (raw==stripped for legendValue=52 — a strip bug, not
                #       real metadata: a per-series legend READING). Without (b) the authoritative wall silently re-exempts
                #       the card-73 legendValue fabrication whenever shape_ref is threaded (the strip keeps the scalar
                #       verbatim), regressing CLASS 4's original charter. NARROW: (b) fires ONLY on a data-VALUE-word key
                #       (value/val — fab_guards.data_value_keys), so presentation CONFIG the strip legitimately keeps
                #       (curveSag / rowHeight / dimOpacity / bandThresholds.divisors.kw / minWidth) is NEVER blanked; a
                #       numeric CHROME leaf (decimals/order/scaleMaxPct) is doubly-exempt via _is_chrome_leaf_key.
                if not _is_written(toks, written):
                    try:
                        same_raw = (node == raw)
                    except Exception:
                        same_raw = False
                    if same_raw and _mag_label:
                        _do_blank(node, path, toks, strip_mag=True)   # 'Rated: 131A' → 'Rated: —'
                    elif same_raw and _is_numeric_data_seed(node) and toks \
                            and _is_data_value_key(toks[-1]) and not _is_chrome_leaf_key(toks):
                        _do_blank(node, path, toks, strip_mag=False)  # strip-missed legend READING (legendValue)
                return
            if is_metadata is False:
                # DATA leaf — seed test is byte-identity to the RAW harvested seed (never the stripped placeholder).
                if _is_written(toks, written):
                    return                                     # filled real — protected even if it equals the seed
                try:
                    same_raw = (node == raw)
                except Exception:
                    same_raw = False
                if not same_raw:
                    return                                     # a real fill / honest-blank placeholder — keep it
                _do_blank(node, path, toks, strip_mag=_mag_label)
                return
            # is_metadata unknown (comparison threw) → fall through to the legacy wall (under-blank preference)

        # ── FALLBACK (no raw default at this leaf): legacy chrome-vocab wall + stripped comparison [belt-and-braces] ──
        _chrome = _is_structural_chrome(toks) or _is_chrome_leaf(node, toks, in_el)
        if _chrome and not _mag_label:
            return                                             # chrome equals its default BY DESIGN — never a data seed
        if _is_written(toks, written):
            return                                             # filled real — protected even if it equals the seed
        try:
            same = node == dflt
        except Exception:
            same = False
        if not same:
            return
        _do_blank(node, path, toks, strip_mag=(_chrome and _mag_label))

    _walk(out, default_payload, raw_default if have_raw else _NO_RAW, "", ())
    return blanked


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  CHROME-RESTORE — a PRESENTATION-CONFIG leaf (active-view selector / enum dir-glyph / filter preset / gauge scale /
#  tone-badge enum) an upstream pass stripped to null/0/'' is RESTORED from the default. These are the switch/scale/enum
#  discriminants CMD_V2 components index UNGUARDED, so a null/0 there CRASHES SSR or EMPTIES the card (not an honest
#  blank). Runs EARLY in fill() (before view_select, so a restored selector can still be re-pointed at a data-bearing
#  view) — a card always renders its chrome; only genuine DATA leaves honest-blank. Generic + DB-driven, NO card ids.
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
_SCALE_SELECTOR_KEYS_DEFAULT = {"scalemaxpct", "limitpct", "scalemax", "defaultlimit"}


def _scale_selector_keys():
    """The chrome-selector keys whose BLANK is a degenerate 0/0.0 (a gauge SCALE/limit that can't draw a bar at
    zero-max) — a SUBSET of chrome_selector_keys, kept a separate row so a new scale key is added with no code change.
    DB knob fab_guards.scale_selector_keys (JSON list, lowercased) with the code-default mirror."""
    try:
        from config.app_config import cfg
        rows = cfg("fab_guards.scale_selector_keys", None)
        if rows:
            return {str(k).strip().lower() for k in rows}
    except Exception:
        pass
    return set(_SCALE_SELECTOR_KEYS_DEFAULT)


def _scale_selector_key(k):
    """A chrome-selector key whose BLANK is a degenerate 0/0.0 (a gauge SCALE/limit that can't draw a bar at zero-max),
    not a null/'' string selector. For these the restore treats a numeric 0 as blank; for a string selector/enum it
    does not (0 is not a selector value). Keyed off the DB-driven scale-key vocab (a subset of the selector vocab)."""
    return k in _scale_selector_keys()


def _chrome_is_blank(cur, key):
    """Is the current chrome leaf value BLANK (stripped) — a string selector/enum None/'' , OR a scale key at 0/0.0?
    A non-blank real chrome value (a live selector the fill legitimately set) is NEVER overwritten by the restore."""
    if cur is None or cur == "":
        return True
    if _scale_selector_key(key) and _is_num(cur) and float(cur) == 0.0:
        return True
    return False


def restore_chrome(out, default_payload, written=None):
    """Walk `out` and `default_payload` in parallel; wherever a leaf whose KEY is a chrome SELECTOR/enum/scale key
    (fab_guards._chrome_selector_keys) is BLANK in `out` (null/''/a zero scale) while the default holds a NON-blank
    value, RESTORE the default value. Over-reach-safe:
      • ONLY chrome-selector keys are touched (a genuine measurement/data key is never in the vocab → still honest-blanks);
      • a WRITTEN leaf (the fill set it real — in / under `written`) is left as-is (a live selector wins over the default);
      • the default value must itself be non-blank (never restores a null over a null — no fabrication).
    It descends every dict/list uniformly (a selector can sit inside a bottomStats/quickStats object list); the selector-
    key vocab is the ONLY wall — never a shape heuristic — so a `dir` nested in a stat-object list is reached, while a
    warn/trip threshold LINE (not in the vocab) is never touched.
    Mutates `out` in place; returns the set of restored token-tuples. Never raises (fail-open on the honest fill)."""
    if not isinstance(out, dict) or not isinstance(default_payload, dict):
        return set()
    wtoks = _written_toks(written)
    restored = set()

    def _walk(node, dflt, toks):
        if isinstance(node, dict):
            if not isinstance(dflt, dict):
                return
            for k, v in list(node.items()):
                if isinstance(k, str) and k.startswith("_"):
                    continue
                if k not in dflt:
                    continue
                kl = str(k).lower()
                if isinstance(v, (dict, list)):
                    _walk(v, dflt[k], toks + (str(k),))
                    continue
                if kl not in _chrome_selector_keys():
                    continue
                if not _chrome_is_blank(v, kl):
                    continue                                    # a live/real chrome value — never overwrite
                if _is_written(toks + (str(k),), wtoks):
                    continue                                    # the fill set this leaf real
                dv = dflt[k]
                if dv is None or dv == "" or isinstance(dv, (dict, list)):
                    continue                                    # nothing non-blank to restore (never null-over-null)
                _set_path(out, ".".join(str(t) for t in toks + (str(k),)), dv)
                restored.add(toks + (str(k),))
            return
        if isinstance(node, list):
            if isinstance(dflt, list):
                for i, el in enumerate(node):
                    if i < len(dflt):
                        _walk(el, dflt[i], toks + (str(i),))
            return

    try:
        _walk(out, default_payload, ())
    except Exception:
        return restored
    return restored


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  apply — the ONE post-fill guard entry wired into fill.py (after every honest fill pass).
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
def apply(out, fields, present_cols, asset_table, default_payload=None, written_paths=None, shape_ref=None):
    """Scan the FINISHED payload and blank the four fabrication CLASSES slot-independently. Returns (out, gaps): the
    (mutated) payload and the per-leaf gap records the caller MERGES into its gaps channel. Never raises — a guard that
    throws leaves the payload as it found it (fail-open on the honest fill, never fabricates).

    `default_payload` (optional) = the card's STRIPPED default skeleton (card_payloads.payload_stripped); `shape_ref`
    (optional) = the card's RAW harvested default (card_payloads.payload); `written_paths` = the leaf paths fill() wrote
    real. Together they drive CLASS 4 (seed-leak): a DATA leaf (raw != stripped) that is UNWRITTEN and byte-identical to
    its RAW default is an unstripped seed → blanked; a METADATA leaf (raw == stripped) is exempt whatever its key. When
    `shape_ref` is absent CLASS 4 falls back to the legacy chrome-vocab wall (under-blank preference)."""
    gaps = []
    if not isinstance(out, dict):
        return out, gaps
    try:
        skip = _apply_class1(out, gaps) if _guard_on("epoch_ms") else set()
    except Exception:
        skip = set()
    try:
        _apply_class2_class3(out, fields or [], present_cols or frozenset(), asset_table, gaps, skip)
    except Exception:
        pass
    try:
        if _guard_on("seed_leak") and default_payload is not None:
            _apply_class4_seed_leak(out, default_payload, _written_toks(written_paths), gaps, raw_default=shape_ref)
    except Exception:
        pass
    return out, gaps
