"""config/metrics.py — the metric vocabulary + normalization. Add/remove keywords/aliases here.

Every vocab constant is a LAZY module attribute (PEP 562): each access re-reads cfg(), so a DB row edit +
app_config.reload() reaches the 1a router / emit passes without a process restart (the old import-time binding
pinned whatever cfg() returned at first import — including code defaults from a boot during a DB outage)."""
from config.app_config import cfg

import re as _re

_METRIC_VOCAB_DEFAULT = ["current", "voltage", "power", "energy", "thd", "pf", "frequency", "temperature"]

# Natural-phrase -> canonical keyword (so 1a never leaks a phrase like 'power factor').
_METRIC_ALIASES_DEFAULT = {
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
}

# standalone single-letter electrical shorthands expanded so the DOMAIN is explicit to both the AI and quantity_family
_SLOT_SHORTHAND_DEFAULT = {"v": "voltage", "i": "current"}

# path tokens that carry NO semantic (structural containers / generic value words) — skipped when deriving a slot label
_GENERIC_SLOT_TOKENS_DEFAULT = ["value", "val", "amount", "data", "vm", "kpis", "snapshot", "views", "view", "series",
                                "points", "stats", "legend", "label", "pct"]

# stem (normalized, no separators) -> mutually-exclusive physical DOMAIN. Longest stem wins (checked first). DB-driven.
_DOMAIN_STEMS_DEFAULT = {
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
}

_LAZY = {
    "METRIC_DEFAULT":      lambda: cfg("metrics.default", "power"),
    # Canonical dominant-quantity keywords (1a output normalizes to exactly one of these).
    "METRIC_VOCAB":        lambda: cfg("metrics.vocab", _METRIC_VOCAB_DEFAULT),
    "METRIC_ALIASES":      lambda: cfg("metrics.aliases", _METRIC_ALIASES_DEFAULT),
    "SLOT_SHORTHAND":      lambda: cfg("metrics.slot_shorthand", _SLOT_SHORTHAND_DEFAULT),
    "GENERIC_SLOT_TOKENS": lambda: set(cfg("metrics.generic_slot_tokens", _GENERIC_SLOT_TOKENS_DEFAULT)),
    "DOMAIN_STEMS":        lambda: cfg("metrics.domain_stems", _DOMAIN_STEMS_DEFAULT),
}


def __getattr__(name):
    if name in _LAZY:
        return _LAZY[name]()
    raise AttributeError(f"module 'config.metrics' has no attribute {name!r}")


def _strict_on():
    """The metrics.normalize_strict flag (DB knob, seed db/seed_metrics_normalize_strict.sql). Lazy import + fail-open
    to OFF: a config/DB error must never change normalization behavior (off = legacy byte-identical). [T0-6]"""
    try:
        from config.app_config import flag_on
        return flag_on("metrics.normalize_strict", False)
    except Exception:
        return False


def _record_unresolved(m):
    """metric_unresolved telemetry (obs.failures, keyed by the current ai_log run id) for a metric text that fell
    through every matching tier. Telemetry ONLY - never raises, never gates the returned default. [T0-6]"""
    try:
        from obs import ai_log, failures
        failures.record("metric_normalize", "metric_unresolved", detail=str(m)[:120],
                        run_id=getattr(ai_log, "_RUN_ID", "default"))
    except Exception:
        pass


def normalize_metric(raw):
    """Map any 1a-returned metric to exactly one canonical keyword (never a phrase).

    Exact tiers always run: vocab word, then alias phrase. The two legacy SUBSTRING loops (vocab-word-in-phrase before
    alias-key-in-phrase - the order-dependence that sends 'power factor trend' to 'power' instead of 'pf') run only
    while metrics.normalize_strict is OFF (byte-identical legacy). Strict ON skips them: exact-only, fallthrough
    returns the default. The terminal fall-through records metric_unresolved in BOTH modes (telemetry only). [T0-6]"""
    default, vocab, aliases = _LAZY["METRIC_DEFAULT"](), _LAZY["METRIC_VOCAB"](), _LAZY["METRIC_ALIASES"]()
    m = (raw or "").strip().lower()
    if not m:
        return default
    if m in vocab:
        return m
    if m in aliases:
        return aliases[m]
    if not _strict_on():
        for v in vocab:              # legacy: a vocab word contained in the phrase
            if v in m:
                return v
        for k, v in aliases.items():  # legacy: an alias key contained in the phrase
            if k in m:
                return v
    _record_unresolved(m)
    return default


def metric_hint(text):
    """WORD-BOUNDARY metric scan of free prompt text -> canonical vocab keyword, or None when nothing hits whole.

    Aliases first, LONGEST key first ('total harmonic distortion' beats 'harmonic distortion' beats 'distortion'),
    then bare vocab words - each matched with regex word boundaries on the stripped/lowered text, so 'empower the
    team' does NOT hit 'power'. Pure scan, single concern: no default, no telemetry - normalize_metric owns the
    fallback policy. [T0-6]"""
    t = (text or "").strip().lower()
    if not t:
        return None
    vocab, aliases = _LAZY["METRIC_VOCAB"](), _LAZY["METRIC_ALIASES"]()
    for k in sorted(aliases, key=len, reverse=True):
        if _re.search(r"\b" + _re.escape(k) + r"\b", t):
            return aliases[k]
    for v in vocab:
        if _re.search(r"\b" + _re.escape(v) + r"\b", t):
            return v
    return None


def prompt_metric_hint(prompt):
    """The ONE-LINE prompt->metric hint for a free-text PROMPT caller (layer1b basket). Strict flag ON: word-boundary
    metric_hint first (correct phrase precedence), falling back to normalize_metric (exact tiers, then default +
    metric_unresolved telemetry). Flag OFF: byte-identical legacy normalize_metric(prompt). [T0-6]"""
    if _strict_on():
        return metric_hint(prompt) or normalize_metric(prompt)
    return normalize_metric(prompt)


# ── SLOT SEMANTICS + QUANTITY-FAMILY (emit-correctness E/G) ──────────────────────────────────────────────────────────
# A leaf whose semantic lives in its PATH TOKEN (`vThd`, `flickerPst`, `lifeRemainingYears`) rather than a sibling
# `label` key used to reach the AI as "(no label)", so it guessed. humanize/slot_semantic_label surface that token as a
# readable label. quantity_family classifies a slot label / column name / fn-quantity to its mutually-exclusive PHYSICAL
# DOMAIN, so a cross-domain fill (a current column in a voltage slot; an energy fn in a 'years' slot) can be caught. All
# DB-driven (cfg rows), generic — no per-card / per-pair hardcoding. quantity_family returns None on no confident match
# (callers MUST treat None as "don't flag" to avoid false positives on legitimate binds).
_CAMEL = _re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z0-9]+|[A-Z]+")


def humanize_token(key):
    """A payload leaf/parent key → readable words (camelCase + underscore split), single-letter electrical shorthands
    expanded (vThd → 'voltage thd', lifeRemainingYears → 'life remaining years'). Generic; no card ids."""
    shorthand = _LAZY["SLOT_SHORTHAND"]()
    parts = [p.lower() for p in _CAMEL.findall(key or "") if p]
    parts = [shorthand.get(p, p) for p in parts]
    return " ".join(parts)


def slot_semantic_label(slot):
    """A readable label for a slot path when the payload carries none — the humanized nearest MEANINGFUL path token
    (skips numeric indices + generic container/value tokens). `snapshot.vThd.valuePct` → 'voltage thd'. None if nothing
    meaningful. Generic + DB-driven (SLOT_SHORTHAND / GENERIC_SLOT_TOKENS)."""
    generic = _LAZY["GENERIC_SLOT_TOKENS"]()
    toks = _re.findall(r"[^.\[\]]+", slot or "")
    for t in reversed(toks):
        if t.isdigit():
            continue
        h = humanize_token(t)
        base = (h.split() or [""])[0]
        if h and base not in generic:
            return h
    return None


def quantity_family(text):
    """The mutually-exclusive physical DOMAIN of a slot label / column name / fn-quantity string, or None if
    unrecognized. Generic + DB-driven (DOMAIN_STEMS). None = unknown → callers MUST NOT flag a mismatch (no false
    positive on a legitimate same-quantity bind whose name simply isn't in the stem map)."""
    t = _re.sub(r"[^a-z0-9]+", "", (text or "").lower())
    if not t:
        return None
    stems = _LAZY["DOMAIN_STEMS"]()
    for stem in sorted(stems, key=len, reverse=True):   # longest stem first so 'voltage' beats a shorter accident
        if stem in t:
            return stems[stem]
    return None
