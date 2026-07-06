"""validate/leaf_classify.py — classify payload leaves DATA vs METADATA by TYPE only (non-AI).

DATA   = the measured values a worker fills: numbers, numeric arrays, time-series.
METADATA = design chrome the AI morphs: strings (labels/units/colors), booleans (flags).
The morph is per-LEAF (most content objects are 'mixed'), so we walk to the leaves and decide by type.
"""
import re

from config.validation import SMALL_ARRAY_MAX

_BOOL = (bool,)

# CMD_V2 stores a MEASURED KPI value as a numeric STRING at `value`/`val`, sitting next to a human `label`
# (summary:{label,value:'427'}, metrics[i]:{label,value:'2.3'}). The type-only rule below would miss these
# (string → metadata) so the Storybook seed leaks AND the AI never sees the slot to bind it. Such a value/val string
# with a sibling label IS data. An axis tick (band.labels[i]:{value,unit,separator} — NO label) has no label sibling,
# so it correctly stays chrome. This single signal separates measured KPI values from gauge/axis chrome — no keyword list.
def _vocab_keys(name):
    """DB-driven key vocab (config.vocab row, the single home — no code literals). Empty set on miss/outage:
    the KPI-string signal disappears and classification honestly degrades to type-only."""
    try:
        from config.vocab import vocab
        return {str(k).lower() for k in (vocab(name) or ())}
    except Exception:
        return set()


def _value_keys():
    return _vocab_keys("value_keys")


def _label_keys():
    return _vocab_keys("label_keys")


def _chrome_subtree_keys():
    """Keys whose WHOLE subtree is DESIGN CHROME even though it holds numbers (band/shade thresholds, divisors) —
    a DB row (vocab.chrome_subtree_keys), NOT a code list. Empty on miss → no exception (type rule decides)."""
    return _vocab_keys("chrome_subtree_keys")


def _chrome_element_keys():
    """Element keys whose NUMERIC value is DESIGN CHROME, not a measurement (warn/trip thresholds, width, decimals,
    from/to band bounds — the SAME vocab row slot_catalog already excludes from fillable value keys:
    vocab.element_chrome_keys). Without this the strip data-classified a series-config element's warn:200/trip:140/
    width:2.2 and zeroed them — the card-62 '0.0 crit' threshold defect: design chrome MUST survive byte-identical.
    Empty on miss → type rule decides (no exemption)."""
    return _vocab_keys("element_chrome_keys")


def _occurrence_bool_parents():
    """Event/activity/tick ROLE keys (vocab.occurrence_bool_parents row; code default mirrors
    db/seed_residual_seed_scrub.sql): a BOOLEAN ARRAY whose own key or immediate parent key is one of these is
    OCCURRENCE DATA — each `true` asserts 'an event happened here' (c55 activity.ticks replayed 2 FAKE transfer events
    from the Storybook seed). The type-only rule called booleans chrome, so the seed survived the strip. A boolean
    array OUTSIDE these roles (structural toggles) stays chrome. [seed-leak class (a)]"""
    return _vocab_keys("occurrence_bool_parents") or {
        "ticks", "activity", "events", "anomalies", "event", "anomaly", "transfers", "occurrences"}


def _numeric_axis_keys():
    """Axis-tick ROLE keys (vocab.numeric_axis_keys row; code default mirrors db/seed_residual_seed_scrub.sql): an
    array of NUMERIC STRINGS under one of these (yTicks ['430'..'390'], yLabels ['380'..'80']) is a SEEDED AXIS —
    tick values scaled to the Storybook demo data, presented as live (c36/37/38 rendered a 430–390 V scale over
    228–240 V live data). Numeric axis arrays (c67 yTicks [11.8..10]) are already data by type; the STRING-typed ones
    dodged the strip. REAL design bands live under chrome/dictionary subtrees (bandThresholds — kept); an axis array
    outside these role keys stays chrome. [seed-leak class (c)]"""
    return _vocab_keys("numeric_axis_keys") or {
        "yticks", "ylabels", "xticks", "xlabels", "ticklabels", "axislabels"}


def _own_and_parent_keys(path):
    """(own_key, parent_key) of a classify path, lowercased, list indices skipped ('activity.ticks' → ('ticks',
    'activity'); 'a.b[0].events' → ('events','b'))."""
    segs = [s.rstrip("]") for s in re.split(r"[.\[]", path or "") if s]
    segs = [s for s in segs if not s.isdigit()]
    own = segs[-1].lower() if segs else ""
    parent = segs[-2].lower() if len(segs) > 1 else ""
    return own, parent
# FULL-STRING numeric detector: value must be a number (optionally grouped/decimal/exponent) with at most a short
# trailing unit token. The old prefix-only `^\s*[+-]?\d` missed '.5'-style decimals (seed-leak risk) and matched
# digit-leading TEXT like '3 Phase' / '24x7' (chrome misclassified as a fillable data scalar). Still generic — no
# card vocab. [AUDIT-2 numeric-string edge]
# A measured value can also arrive PAREN-WRAPPED — the composed delta display string '(+1.0%)' is prefix+value+qualifier.
# Allow an optional single wrapping paren so that framed numeric-string measured values (delta/deviation next to a label)
# are detected as data too; a non-numeric paren token ('(N/A)', '(Today)', '(coolant)') still fails. [AUDIT-3 framed-delta]
_NUM_STR = re.compile(r"^\s*\(?\s*[+-]?(\d+([.,]\d+)*|\.\d+)([eE][+-]?\d+)?\s*(%|[a-zA-Z%/°]{0,6})?\s*\)?\s*$")


def _num_str(v):
    return isinstance(v, str) and bool(_NUM_STR.match(v))


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, _BOOL)


def _all_numeric(lst):
    return bool(lst) and all(_is_num(x) for x in lst)


def classify(payload):
    """Return {data_leaves:[{path,kind}], metadata_leaves:int, demand:{scalars,arrays,series}}.
    kind in {scalar, array, series}."""
    data, meta = [], [0]
    chrome = _chrome_subtree_keys()
    chrome_el = _chrome_element_keys()

    def walk(o, path):
        if _is_num(o):
            data.append({"path": path, "kind": "scalar"}); return
        if isinstance(o, str) or isinstance(o, _BOOL) or o is None:
            meta[0] += 1; return
        if isinstance(o, list):
            if not o:
                meta[0] += 1; return
            own, parent = _own_and_parent_keys(path)
            # OCCURRENCE boolean array (event/activity/tick role — vocab row): each true IS a data assertion ('a
            # transfer happened at tick 7'), so the whole array is DATA and strips to empty (all-false honest rest).
            if all(isinstance(x, _BOOL) for x in o) and (
                    own in _occurrence_bool_parents() or parent in _occurrence_bool_parents()):
                data.append({"path": path, "kind": "array" if len(o) <= SMALL_ARRAY_MAX else "series"}); return
            # SEEDED NUMERIC-STRING AXIS (yTicks/yLabels role — vocab row): tick strings scaled to the demo data are
            # live-looking values, DATA not chrome (numeric-typed axis arrays are already data by the type rule).
            if own in _numeric_axis_keys() and all(_num_str(x) for x in o):
                data.append({"path": path, "kind": "array" if len(o) <= SMALL_ARRAY_MAX else "series"}); return
            if _all_numeric(o):
                data.append({"path": path, "kind": "array" if len(o) <= SMALL_ARRAY_MAX else "series"}); return
            if all(isinstance(x, dict) for x in o):
                # list of objects: a series if any object carries a numeric leaf — EXCLUDING vocab-declared chrome
                # element keys (warn/trip/width…): an array whose only numerics are design thresholds is a CONFIG
                # array, not a series, so its chrome survives the per-element walk byte-identical. [card-62 family]
                # If so, those per-object numeric leaves ARE the series — don't recurse (no double-count).
                if any(any(_is_num(v) and str(k).lower() not in chrome_el for k, v in x.items()) for x in o):
                    data.append({"path": path, "kind": "series"}); return
                # walk EVERY element — a truncated walk ([:3]) left items 3+ unclassified, so the strip missed them
                # and the Storybook seed (heatmap history[3..11]) replayed as if live. [seed-leak root cause]
                for i, x in enumerate(o):
                    walk(x, f"{path}[{i}]")
                return
            for i, x in enumerate(o):
                walk(x, f"{path}[{i}]")
            return
        if isinstance(o, dict):
            has_label = any(str(k).lower() in _label_keys() for k in o.keys())
            for k, v in o.items():
                child = f"{path}.{k}" if path else k
                # DESIGN-CHROME subtree (vocab.chrome_subtree_keys row — e.g. bandThresholds): numbers here are shade/
                # band boundaries harvested as design, NOT measured data — keep byte-identical, never strip/fill.
                if str(k).lower() in chrome:
                    meta[0] += 1
                    continue
                # DESIGN-CHROME element key (vocab.element_chrome_keys row — warn/trip/width/decimals/from/to): a
                # NUMERIC (or numeric-string) leaf under such a key is a design threshold/geometry literal, NOT a
                # measurement — metadata, byte-identical through strip and fill. [card-62 '0.0 crit' family]
                if str(k).lower() in chrome_el and (_is_num(v) or _num_str(v)):
                    meta[0] += 1
                    continue
                # a numeric-string value/val next to a label = a measured KPI value (data); else classify by type.
                if has_label and str(k).lower() in _value_keys() and _num_str(v):
                    data.append({"path": child, "kind": "scalar"})
                else:
                    walk(v, child)
            return
        meta[0] += 1

    walk(payload, "")
    demand = {"scalars": sum(1 for d in data if d["kind"] == "scalar"),
              "arrays": sum(1 for d in data if d["kind"] == "array"),
              "series": sum(1 for d in data if d["kind"] == "series")}
    return {"data_leaves": data, "metadata_leaves": meta[0], "demand": demand}
