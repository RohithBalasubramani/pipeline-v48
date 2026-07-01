"""Alias layer — fills the EMS alias gap (no alias table exists in cmd_catalog).

Three sources, applied in build_index.py:
  * curated  — hand-written high-value synonyms (this file)
  * embedded — cleaned/short forms extracted from verbose asset names
  * llm      — colloquial synonyms generated offline by the 4B model
"""
import json
import re

# alias -> needle that must appear in a METRIC's column_name/display (lowercased)
METRIC_ALIAS = {
    "amps": "current", "amperage": "current", "amp": "current", "current": "current",
    "volts": "voltage", "voltage": "voltage", "v": "voltage",
    "power": "active_power", "kw": "active_power", "real power": "active_power",
    "active power": "active_power",
    "pf": "power_factor", "power factor": "power_factor", "powerfactor": "power_factor",
    "reactive": "reactive_power", "kvar": "reactive_power", "reactive power": "reactive_power",
    "apparent": "apparent_power", "kva": "apparent_power", "apparent power": "apparent_power",
    "energy": "active_energy", "kwh": "active_energy", "consumption": "active_energy",
    "units": "active_energy",
    "freq": "frequency", "frequency": "frequency", "hz": "frequency",
    "thd": "thd", "harmonics": "thd", "distortion": "thd", "harmonic": "thd",
    "unbalance": "unbalance", "imbalance": "unbalance",
    "temp": "temperature", "temperature": "temperature", "thermal": "temperature",
    "fuel": "fuel", "autonomy": "autonomy", "load": "load", "loading": "load",
    "demand": "demand", "neutral": "neutral", "sag": "sag", "swell": "swell",
    "oil": "oil", "speed": "speed", "rpm": "speed",
}

# alias -> needle that must appear in an ASSET's name/class (lowercased)
ASSET_ALIAS = {
    "trans": "transformer", "transformer": "transformer", "tx": "transformer",
    "xfmr": "transformer", "tfmr": "transformer",
    "dg": "diesel generator", "genset": "diesel generator", "generator": "diesel generator",
    "diesel": "diesel generator",
    "ups": "ups",
    "pcc": "pcc panel", "panel": "panel",
    "ahu": "ahu", "air handler": "ahu", "air handling": "ahu", "ahus": "ahu",
    "chiller": "chiller", "compressor": "compressor", "comp": "compressor",
    "apfc": "apfc", "ht": "ht panel", "lt": "lt panel",
    "solar": "solar", "pv": "solar", "feeder": "feeder",
    "bpdb": "bpdb", "hhf": "hhf", "cwp": "cwp", "air washer": "air washer",
}

# verbose name -> spec tokens stripped to make a clean display + extra aliases
_SPEC_PATTERNS = [
    re.compile(r"\bCL:?\s*\d+\s*KVA\b", re.I),
    re.compile(r"\+?\s*\d+\s*KVAR\b", re.I),
    re.compile(r"\b\d+\s*A\b", re.I),
    re.compile(r"\(TYPE-?\d+\)", re.I),
    re.compile(r"\([^)]*\)"),
]


def clean_display(name: str) -> str:
    """Strip rating/spec noise from an asset name for a tidy display label."""
    out = name
    for pat in _SPEC_PATTERNS:
        out = pat.sub("", out)
    out = re.sub(r"\s{2,}", " ", out).strip(" -·,")
    return out or name


def embedded_aliases(name: str):
    """Short/clean forms and spec tokens worth indexing as aliases."""
    out = set()
    clean = clean_display(name)
    if clean and clean.lower() != name.lower():
        out.add(clean)
    # leading id token, e.g. 'UPS-01', 'HHF-01', 'AHU-5'
    m = re.match(r"^([A-Za-z]+[- ]?\d+)", name)
    if m:
        out.add(m.group(1))
    return {a for a in out if a and len(a) >= 2}


# ---- offline LLM alias generation (build-time, latency irrelevant) ----
def gen_llm_aliases(items, batch=24, timeout=30.0):
    """items: list of (entity_id, kind, display). Returns {entity_id: [alias,...]}.

    Asks the 4B model for short colloquial synonyms an operator might type.
    Best-effort: any batch that fails is skipped.
    """
    import llm  # local import so build works even if endpoint is down

    result = {}
    for i in range(0, len(items), batch):
        chunk = items[i:i + batch]
        listing = "\n".join(f"{eid}\t{kind}\t{disp}" for eid, kind, disp in chunk)
        sys = (
            "You generate short search synonyms for EMS dashboard entities. "
            "For each line 'id<TAB>kind<TAB>name', return colloquial words/abbreviations "
            "an operator might type to mean it (lowercase, 1-3 words, no specs/ratings, no the name itself). "
            "Return STRICT JSON: {\"<id>\": [\"syn1\",\"syn2\"]}. Max 4 per item. Skip if none."
        )
        try:
            txt = llm.chat(
                [{"role": "system", "content": sys},
                 {"role": "user", "content": listing}],
                temperature=0.4, max_tokens=900, timeout=timeout,
                response_format={"type": "json_object"},
            )
            obj = json.loads(txt)
            for k, v in obj.items():
                if isinstance(v, list):
                    eid = int(k)
                    result[eid] = [str(a).strip().lower() for a in v if str(a).strip()][:4]
        except Exception:
            continue
    return result
