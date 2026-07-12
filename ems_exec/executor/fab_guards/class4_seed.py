"""fab_guards/class4_seed.py — CLASS 4: the SEED-LEAK wall + the chrome vocabulary (structural/selector/string
key sets, the trivial-scalar thresholds, the data-magnitude regex machinery) deciding which surviving default
values are policed as leaked Storybook seeds vs kept as chrome."""
from __future__ import annotations

from ems_exec.executor.paths import _toks, _set_path
from ems_exec.executor.series_fill import _element_value_key, _element_time_key
from ems_exec.executor.fab_guards.knobs import _is_num, _add_gap

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


# LAZY, vocab-keyed regex cache (the old module-level `_MAGNITUDE_RE = _mag_re()` froze the DB vocab at import —
# editing the fab_guards.magnitude_units row + reload() never reached it; per-call compile would tax the hot
# string-leaf scan, so compile once per DISTINCT vocab instead).
_MAG_RE_CACHE = {}


def _magnitude_re():
    units = tuple(_mag_units())
    r = _MAG_RE_CACHE.get(units)
    if r is None:
        r = _MAG_RE_CACHE[units] = _re.compile(
            r"(?<![\w#.])\d[\d,]*(?:\.\d+)?\s*(?:"
            + "|".join(sorted((_re.escape(u) for u in units), key=len, reverse=True)) + r")\b")
    return r


def _embeds_data_magnitude(v):
    """True when a STRING chrome label embeds a numeric data magnitude+unit (a rating/limit/range value baked into the
    label text). Such a label is NOT pure chrome — when it equals a stale default seed it must be neutralized, not
    blanket-exempted. Never raises."""
    try:
        return isinstance(v, str) and bool(_magnitude_re().search(v))
    except Exception:
        return False


def _strip_stale_magnitude(s):
    """Neutralize the stale data magnitude in a chrome label seed: 'Rated: 131A' → 'Rated: —' (keeps the label chrome,
    drops the fabricated number). Returns None if nothing is left but the number itself."""
    try:
        out = _magnitude_re().sub("—", s).strip()
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
