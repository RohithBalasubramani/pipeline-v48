"""host/display_dash.py — the ONE generic HONEST-DASH display policy (serve-boundary, type-proven).

DEFECT (2026-07-03): CMD_V2 stat tiles print the literal text 'null' (QuickStats does String(t.value)) and some cards
CRASH their piece boundary on an unguarded fmt(null) (SupplyCard's denominator/leftKw → null.toLocaleString) when the
executor honest-blanks a display value.

POLICY (generic — applies to EVERY card, never per-card): a SCALAR null whose object also carries a UNIT-LIKE key is a
DISPLAY value the executor honest-blanked ({label?, value, unit} tile contract) → replace it with the design system's
own em-dash '—' at the SERVE boundary, so String()/template/fmt() sites render the honest dash instead of 'null' or a
crash. UNIT-LIKE = the key `unit` itself or any key ending in a configured unit suffix (`percentUnit`, `valueUnit`, …)
— vocabulary row app_config `display.unit_sibling_suffixes` (default ["unit"]); the 2026-07-03 PCC-4 defect was a
partially-null object whose only unit evidence was `percentUnit`, so its null display scalars skipped the dash and an
unguarded fmt(null) site crashed the card's boundary.

TYPE PROOF: a JSON null carries no type, and dashing a null OBJECT (e.g. supply.consumedHint — legitimately null =
"no hint row") would turn `!!hint` guards truthy and crash the component one line later. The HOST holds each card's
HARVESTED DEFAULT payload (cmd_catalog.card_payloads), so a null is dashed ONLY when the default proves the leaf is a
scalar (number/string) at that same path. No default evidence → the null is left alone (the component's own null
handling stands).

SECOND RULE — UNIT-SUFFIXED VALUE KEYS (2026-07-03 PCC-4 defect D): a roster member element ({name, kw, kwh}) carries
NO unit-like sibling, so its honest-null kw/kwh leaves skipped the dash and CMD_V2's unguarded fmt sites
(fmtKwh(null).toLocaleString — EnergyInputDistributionCard rail rows) threw, the card boundary ate 23 REAL rows. A null
whose KEY ITSELF ends in a measurement-unit suffix (`kw`, `kwh`, `totalKvar`, …) IS a display value — dash it when the
default proves the leaf NUMERIC at that path. Vocabulary row: app_config `display.unit_value_key_suffixes` (default
["kw","kwh","kva","kvar","pct"]). The code default MIRRORS the live row byte-for-byte (A6b outage parity: a DB-down
cfg() fallback must not flip dash behavior and re-crash unguarded fmt(null) sites). History: pct was originally
excluded on a NaN% guard concern (utilizationPct <= 0 → '—'), but the live row was extended to include it
(2026-07-06) — the dash still only fires when the harvested default PROVES the leaf numeric at that exact path.

FAMILY-H EXTENSIONS (2026-07-06, type-proven against the RAW harvested default):

  DIGIT CHROME  — a formatter DIGITS input (`fmt(value, decimals)` → Intl minimumFractionDigits / `toFixed(digits)`)
                  must NEVER become a string: '—' is NaN there and Intl throws RangeError (the card-21 railDecimals
                  crash). A null/dashed *decimals/*digits key whose DEFAULT is a NUMBER is restored to the DEFAULT
                  NUMBER (pure presentation chrome — a digit count asserts no data). Handles the dict form too
                  (`decimals: {thd, pfLow, pfHigh}`). Vocabulary row `display.digit_key_suffixes`
                  (default ["decimals","digits"]). Checked FIRST — digit keys are exempt from every dash rule.

  UNIT-EVIDENCE FIX — a key only counts as the unit-LIKE sibling (and is only exempt from dashing) when the evidence
                  says it IS a unit label: its default/current value is a STRING. `secKwhPerUnit` (a NUMBER — kWh per
                  production unit) was mistaken for a unit label by the bare suffix match, skipped the dash, and
                  TodaysEnergyCard's unguarded formatKwh(null) threw (card 39).

  SIBLING REHYDRATE — a null OBJECT slot whose SAME-LENGTH, ≥4-char-common-prefix SIBLING is a dict with the same
                  keyset in the DEFAULT (stats.worstVThd:null beside stats.worstIThd:{…}) is rebuilt as the DEFAULT's
                  SHAPE with every scalar leaf nulled (arrays → [], dicts recursed) — the STRUCTURE is chrome the
                  component derefs unconditionally (stats.worstVThd.vThd — card 23); the leaves stay honest-blank and
                  the dash walk then applies its own type proofs inside. consumedHint-style legit null objects have no
                  such sibling and are untouched (the 2026-07-03 guarantee stands — see test_null_object_never_dashed).

  NO-ASSERT FALLBACKS — `driverFallbackCode: 'OK'` asserts a health state for a driver that merely matched nothing
                  (or was never measured) — replaced with '—' (assert nothing). Vocabulary row
                  `display.no_assert_fallbacks` (json map key → replacement, default {"driverFallbackCode": "—"}).

ORDER: applied AFTER the render-verdict leaf accounting (_card_leaf_stats / seed count) — a dash is display chrome and
must never count as a real data leaf.

Valve: app_config `display.null_dash` ('unit_adjacent' default | 'off'). [atomic; one concern]
"""
from __future__ import annotations

DASH = "—"


def _enabled():
    try:
        from config.app_config import cfg
        return str(cfg("display.null_dash", "unit_adjacent")).strip().lower() != "off"
    except Exception:
        return True


def _unit_suffixes():
    """The UNIT-LIKE key vocabulary (lowercase suffixes) — app_config `display.unit_sibling_suffixes`, code default
    ["unit"]: matches `unit` itself and camelCase `…Unit` siblings (percentUnit / valueUnit)."""
    try:
        from config.app_config import cfg
        v = cfg("display.unit_sibling_suffixes", ["unit"])
        return [str(s).strip().lower() for s in v if str(s).strip()] or ["unit"]
    except Exception:
        return ["unit"]


def _is_unitlike(key, suffixes):
    k = str(key).lower()
    return any(k == s or k.endswith(s) for s in suffixes)


def _value_key_suffixes():
    """The unit-suffixed VALUE-key vocabulary (lowercase suffixes) — app_config `display.unit_value_key_suffixes`,
    code default ["kw","kwh","kva","kvar","pct"] (byte-equal MIRROR of the live row — A6b DB-outage parity): matches
    `kw`/`kvar`/`…Pct` themselves and camelCase `…Kw`/`…Kvar` (totalKwh, totalKvar, allTotalKw)."""
    try:
        from config.app_config import cfg
        v = cfg("display.unit_value_key_suffixes", ["kw", "kwh", "kva", "kvar", "pct"])
        return [str(s).strip().lower() for s in v if str(s).strip()] or ["kw", "kwh", "kva", "kvar", "pct"]
    except Exception:
        return ["kw", "kwh", "kva", "kvar", "pct"]


def _digit_suffixes():
    """The formatter-DIGITS key vocabulary — app_config `display.digit_key_suffixes`, code default
    ["decimals","digits"]. These keys are Intl/toFixed INPUTS: restored to the default NUMBER, never dashed."""
    try:
        from config.app_config import cfg
        v = cfg("display.digit_key_suffixes", ["decimals", "digits"])
        return [str(s).strip().lower() for s in v if str(s).strip()] or ["decimals", "digits"]
    except Exception:
        return ["decimals", "digits"]


def _no_assert_fallbacks():
    """Assertive fallback tokens replaced with the no-assert dash — app_config `display.no_assert_fallbacks`
    (json map {key: replacement}), code default {'driverFallbackCode': '—'}."""
    try:
        from config.app_config import cfg
        v = cfg("display.no_assert_fallbacks", {"driverFallbackCode": DASH})
        return {str(k): str(val) for k, val in dict(v).items()}
    except Exception:
        return {"driverFallbackCode": DASH}


def _number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def apply(payload, default_payload):
    """Dash the unit-adjacent, type-proven scalar nulls of a COMPLETED card payload, in place (and return it).
    `default_payload` = the card's harvested default (the type evidence); payload without one is returned untouched
    except where a sibling default subtree still provides evidence. Never raises."""
    try:
        if not _enabled() or not isinstance(payload, dict):
            return payload
        _walk(payload, default_payload if isinstance(default_payload, dict) else None, _unit_suffixes(),
              _value_key_suffixes(), _digit_suffixes(), _no_assert_fallbacks())
    except Exception:
        pass
    return payload


def _scalar(x):
    return isinstance(x, (int, float, str)) and not isinstance(x, bool)


def _is_unit_label(key, node, dflt, suffixes):
    """Key `key` is a REAL unit-label slot only when the suffix matches AND the evidence (current value or default)
    proves a STRING there — a number under a `…Unit` name is a VALUE (secKwhPerUnit), not a unit label."""
    if not _is_unitlike(key, suffixes):
        return False
    cur = node.get(key)
    dch = dflt.get(key) if isinstance(dflt, dict) else None
    if isinstance(cur, str):
        return True
    if cur is None and isinstance(dch, str):
        return True
    return cur is None and dch is None      # no counter-evidence → keep the conservative unit-label reading


def _blank_shape(src):
    """The DEFAULT subtree with every scalar leaf nulled (arrays → [], dicts recursed) — structure-only rehydrate."""
    if isinstance(src, dict):
        return {k: _blank_shape(v) for k, v in src.items()}
    if isinstance(src, list):
        return []
    return None


def _prefix_len(a, b):
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def _rehydrate_siblings(node, dflt):
    """SIBLING REHYDRATE (see header): a null whose DEFAULT is a dict AND whose same-length ≥4-prefix sibling is a
    dict with the same keyset → the default's blank shape. The dash walk continues inside it afterwards."""
    if not isinstance(dflt, dict):
        return
    for k, v in list(node.items()):
        if v is not None or not isinstance(dflt.get(k), dict):
            continue
        dkeys = set(dflt[k].keys())
        for k2, v2 in node.items():
            if k2 == k or not isinstance(v2, dict) or len(k2) != len(k) or _prefix_len(k, k2) < 4:
                continue
            if dkeys and len(dkeys & set(v2.keys())) >= max(1, len(dkeys) - 2):
                node[k] = _blank_shape(dflt[k])
                break


def _fix_digit_chrome(node, dflt, dsuffixes):
    """DIGIT CHROME (see header): restore null/dashed digit keys to the DEFAULT NUMBER (scalar and dict forms)."""
    for k, v in list(node.items()):
        if not _is_unitlike(k, dsuffixes):                     # same suffix matcher, digit vocabulary
            continue
        dch = dflt.get(k) if isinstance(dflt, dict) else None
        if (v is None or v == DASH) and _number(dch):
            node[k] = dch
        elif isinstance(v, dict):
            ddch = dch if isinstance(dch, dict) else {}
            for ik, iv in list(v.items()):
                if (iv is None or iv == DASH) and _number(ddch.get(ik)):
                    v[ik] = ddch[ik]


def _walk(node, dflt, suffixes, vsuffixes, dsuffixes, no_assert):
    if isinstance(node, dict):
        _fix_digit_chrome(node, dflt, dsuffixes)
        _rehydrate_siblings(node, dflt)
        for k, v in list(node.items()):
            if k in no_assert and isinstance(v, str) and v != no_assert[k]:
                node[k] = no_assert[k]                        # assertive fallback token → the no-assert dash
        has_unit = any(_is_unit_label(k, node, dflt, suffixes) for k in node)
        for k, v in node.items():
            dchild = dflt.get(k) if isinstance(dflt, dict) else None
            if _is_unitlike(k, dsuffixes):
                continue                                       # digit chrome: restored above, NEVER dashed
            if v is None:
                if has_unit and not _is_unit_label(k, node, dflt, suffixes) and _scalar(dchild):
                    node[k] = DASH                    # type-proven display scalar → the honest dash
                elif _is_unitlike(k, vsuffixes) and _number(dchild):
                    node[k] = DASH                    # unit-SUFFIXED value key (kw/kvar/…), type-proven numeric → dash
            elif isinstance(v, (dict, list)):
                _walk(v, dchild, suffixes, vsuffixes, dsuffixes, no_assert)
    elif isinstance(node, list):
        dlist = dflt if isinstance(dflt, list) else []
        for i, el in enumerate(node):
            if isinstance(el, (dict, list)):
                dref = dlist[i] if i < len(dlist) else (dlist[0] if dlist else None)
                _walk(el, dref, suffixes, vsuffixes, dsuffixes, no_assert)
