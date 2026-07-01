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
