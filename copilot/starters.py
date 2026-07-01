"""Starter 'suggested commands' for the empty state.

Fully AI-driven: the model is shown the real v48 assets (grouped by class, from the
index) and CHOOSES which to feature + composes the command for each. Generated once and
cached. Each = {tag, text}: a short mono mnemonic + a readable command that seeds the
prompt bar on click.

Relevance rules baked into the prompt: ONE asset per command, a metric that fits that
asset's type, 5 DISTINCT intents (real-time / trend / V&I / power-quality / alarms).
"""
import json

import llm
import retrieve

_CACHE = None

_SYS = (
    "You write the empty-state 'suggested commands' for an EMS (Energy Management System) dashboard "
    "copilot. You are given the real assets (grouped by class); YOU choose which to feature. Produce "
    "EXACTLY 5 starter commands an operator would actually click.\n"
    "RULES:\n"
    "- ONE asset per command — NEVER combine multiple assets in a single command.\n"
    "- Use ONLY the provided real assets. Pick 5 DIVERSE, representative assets across different "
    "equipment types (don't cluster on one type); skip spare/unassigned feeders.\n"
    "- Pair each asset with a metric that genuinely FITS its type: transformer / panel / feeder / meter "
    "=> power, current, voltage, harmonics, power factor (transformer also loading); UPS => battery, "
    "autonomy, load; diesel generator => fuel, load, runtime; chiller / AHU / air washer => temperature, "
    "airflow, status, power; compressor => pressure, status, power.\n"
    "- The 5 commands cover 5 DISTINCT intents, one each, in this order: (1) real-time monitoring, "
    "(2) energy or power trend over time, (3) voltage & current, (4) power quality / harmonics, "
    "(5) active alarms or events. Use an electrical asset (transformer/panel/feeder/meter) for the "
    "power-quality and voltage&current commands (harmonics/voltage don't belong on a chiller/AHU).\n"
    "- Short, natural, operator-like (e.g. 'real-time power and current for Transformer 01', "
    "'voltage and current for BPDB-01 For Lamination', 'chiller 1 temperature trend today').\n"
    'Return STRICT JSON only: {"starters":[{"tag":"<2-4 char UPPERCASE, e.g. RT / TRND / V·I / PQ / ALM>",'
    '"text":"<the command>"}]}. No prose.'
)


def _asset_listing(ix, per_class=10):
    """Real assets grouped by class for the model to choose from (spares excluded as noise)."""
    by_class = {}
    for e in ix.by_type.get("asset", []):
        cls = e["class_scope"] or "?"
        if cls == "Spare":
            continue
        by_class.setdefault(cls, []).append(e["display"])
    return "\n".join(f"{cls}: " + ", ".join(names[:per_class]) for cls, names in sorted(by_class.items()))


def starters(n=5, timeout=30.0):
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    ix = retrieve.index()
    listing = _asset_listing(ix)
    user = ("REAL ASSETS BY CLASS (choose ONLY from these):\n" + listing +
            f"\n\nYOU choose {n} diverse, representative assets and compose {n} single-asset "
            f"starter commands as JSON.")
    try:
        raw = llm.chat([{"role": "system", "content": _SYS}, {"role": "user", "content": user}],
                       temperature=0.5, timeout=timeout, response_format={"type": "json_object"})
        arr = json.loads(raw).get("starters", [])
        out = [{"tag": (str(s.get("tag") or "•").strip()[:4] or "•"),
                "text": str(s.get("text") or "").strip()}
               for s in arr if str(s.get("text") or "").strip()][:n]
        if out:
            _CACHE = out
            return out
    except Exception:
        pass
    # fallback (model down): first asset of a few distinct non-spare classes
    picks, seen = [], set()
    for e in ix.by_type.get("asset", []):
        c = e["class_scope"] or "?"
        if c == "Spare" or c in seen:
            continue
        seen.add(c)
        picks.append(e["display"])
        if len(picks) >= 5:
            break
    a = picks + ["the panel"] * 6
    _CACHE = [
        {"tag": "RT", "text": f"real-time power and current for {a[0]}"},
        {"tag": "TRND", "text": f"energy and power trend for {a[1]} today"},
        {"tag": "V·I", "text": f"voltage and current for {a[2]}"},
        {"tag": "PQ", "text": f"power quality and harmonics for {a[3]}"},
        {"tag": "ALM", "text": f"active alarms and events for {a[4]}"},
    ][:n]
    return _CACHE
