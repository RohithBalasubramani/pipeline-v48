"""config/metrics.py — the metric vocabulary + normalization. Add/remove keywords/aliases here."""
from config.app_config import cfg

METRIC_DEFAULT = cfg("metrics.default", "power")

# Canonical dominant-quantity keywords (1a output normalizes to exactly one of these).
METRIC_VOCAB = cfg("metrics.vocab", ["current", "voltage", "power", "energy", "thd", "pf", "frequency", "temperature"])

# Natural-phrase -> canonical keyword (so 1a never leaks a phrase like 'power factor').
METRIC_ALIASES = cfg("metrics.aliases", {
    "power factor": "pf", "reactive power": "pf", "powerfactor": "pf",
    "harmonic distortion": "thd", "harmonics": "thd", "total harmonic distortion": "thd",
    "distortion": "thd", "power quality": "thd", "pq": "thd",
    "voltage/current": "voltage", "current/voltage": "voltage", "voltage and current": "voltage",
    "amps": "current", "ampere": "current", "amperage": "current", "amperes": "current",
    "volt": "voltage", "volts": "voltage", "kv": "voltage",
    "kw": "power", "kva": "power", "kilowatt": "power", "load": "power", "demand": "power", "supply": "power",
    "kwh": "energy", "consumption": "energy", "kwh consumption": "energy",
    "temp": "temperature", "thermal": "temperature", "heat": "temperature",
    "freq": "frequency", "hz": "frequency",
})


def normalize_metric(raw):
    """Map any 1a-returned metric to exactly one canonical keyword (never a phrase)."""
    m = (raw or "").strip().lower()
    if not m:
        return METRIC_DEFAULT
    if m in METRIC_VOCAB:
        return m
    if m in METRIC_ALIASES:
        return METRIC_ALIASES[m]
    for v in METRIC_VOCAB:           # a vocab word contained in the phrase
        if v in m:
            return v
    for k, v in METRIC_ALIASES.items():
        if k in m:
            return v
    return METRIC_DEFAULT


# ── SLOT SEMANTICS + QUANTITY-FAMILY (emit-correctness E/G) ──────────────────────────────────────────────────────────
# A leaf whose semantic lives in its PATH TOKEN (`vThd`, `flickerPst`, `lifeRemainingYears`) rather than a sibling
# `label` key used to reach the AI as "(no label)", so it guessed. humanize/slot_semantic_label surface that token as a
# readable label. quantity_family classifies a slot label / column name / fn-quantity to its mutually-exclusive PHYSICAL
# DOMAIN, so a cross-domain fill (a current column in a voltage slot; an energy fn in a 'years' slot) can be caught. All
# DB-driven (cfg rows), generic — no per-card / per-pair hardcoding. quantity_family returns None on no confident match
# (callers MUST treat None as "don't flag" to avoid false positives on legitimate binds).
import re as _re  # noqa: E402

_CAMEL = _re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z0-9]+|[A-Z]+")
# standalone single-letter electrical shorthands expanded so the DOMAIN is explicit to both the AI and quantity_family
SLOT_SHORTHAND = cfg("metrics.slot_shorthand", {"v": "voltage", "i": "current"})
# path tokens that carry NO semantic (structural containers / generic value words) — skipped when deriving a slot label
GENERIC_SLOT_TOKENS = set(cfg("metrics.generic_slot_tokens",
    ["value", "val", "amount", "data", "vm", "kpis", "snapshot", "views", "view", "series",
     "points", "stats", "legend", "label", "pct"]))
# stem (normalized, no separators) -> mutually-exclusive physical DOMAIN. Longest stem wins (checked first). DB-driven.
DOMAIN_STEMS = cfg("metrics.domain_stems", {
    "voltage": "voltage", "volt": "voltage",
    "current": "current",
    "powerfactor": "powerfactor", "displacementpf": "powerfactor", "truepf": "powerfactor",
    "power": "power", "kva": "power", "kvar": "power", "watt": "power", "demand": "power", "kw": "power",
    "energy": "energy", "kwh": "energy", "kvarh": "energy", "kvah": "energy", "mvah": "energy",
    "mvarh": "energy", "consumption": "energy",
    "frequency": "frequency", "hertz": "frequency",
    "temperature": "temperature", "thermal": "temperature", "hotspot": "temperature",
    "winding": "temperature", "oil": "temperature",
    "lifetime": "lifetime", "lifespan": "lifetime", "ageing": "lifetime", "aging": "lifetime",
    "years": "lifetime", "year": "lifetime", "life": "lifetime",
    "flicker": "flicker", "pst": "flicker", "plt": "flicker",
    "crest": "crest",
})
_DOMAIN_ORDER = sorted(DOMAIN_STEMS, key=len, reverse=True)   # longest stem first so 'voltage' beats a shorter accident


def humanize_token(key):
    """A payload leaf/parent key → readable words (camelCase + underscore split), single-letter electrical shorthands
    expanded (vThd → 'voltage thd', lifeRemainingYears → 'life remaining years'). Generic; no card ids."""
    parts = [p.lower() for p in _CAMEL.findall(key or "") if p]
    parts = [SLOT_SHORTHAND.get(p, p) for p in parts]
    return " ".join(parts)


def slot_semantic_label(slot):
    """A readable label for a slot path when the payload carries none — the humanized nearest MEANINGFUL path token
    (skips numeric indices + generic container/value tokens). `snapshot.vThd.valuePct` → 'voltage thd'. None if nothing
    meaningful. Generic + DB-driven (SLOT_SHORTHAND / GENERIC_SLOT_TOKENS)."""
    toks = _re.findall(r"[^.\[\]]+", slot or "")
    for t in reversed(toks):
        if t.isdigit():
            continue
        h = humanize_token(t)
        base = (h.split() or [""])[0]
        if h and base not in GENERIC_SLOT_TOKENS:
            return h
    return None


def quantity_family(text):
    """The mutually-exclusive physical DOMAIN of a slot label / column name / fn-quantity string, or None if
    unrecognized. Generic + DB-driven (DOMAIN_STEMS). None = unknown → callers MUST NOT flag a mismatch (no false
    positive on a legitimate same-quantity bind whose name simply isn't in the stem map)."""
    t = _re.sub(r"[^a-z0-9]+", "", (text or "").lower())
    if not t:
        return None
    for stem in _DOMAIN_ORDER:
        if stem in t:
            return DOMAIN_STEMS[stem]
    return None
