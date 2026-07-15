"""layer2/emit/asset_facts.py — NAMEPLATE + DATA WINDOW fact lines for the Layer-2 ASSET block. [C3]

The two rules the AI most often violated depended on facts it was never given:
  · CONST-SOURCE / nameplate fns — it emitted rated consts (I_RATED=131, ratedKw=600) ON FAITH because the prompt
    never said whether THIS asset's rating exists. NAMEPLATE line = the real cmd_catalog.asset_nameplate row (the
    re-seeded, honest table: real-source ratings or NULL — the fabricated class_default rows are gone). A '—' value
    means the rating is UNKNOWN: any fn/const needing it is UNBINDABLE — omit (honest-blank), never guess.
  · WINDOW/RANGE choice — 28/38 window emits chose range='today' over a lagging/static dataset (empty fills, 255
    no_reading blanks). DATA WINDOW line = the table's real first/last logged ts + age, with the anchor rule.

FACTS ONLY — verbatim DB values, no suggestions. Any failure → '' (line omitted, honest-degrade; never raises,
never blocks an emit on a DB outage).
"""


def _fmt(v):
    return "—" if v in (None, "", "NULL") else str(v)


def bucket_ts(v):
    """The timestamp fact bucketed to the HOUR [Stage 4, emit.prompt_stability]: nanosecond-precision `last=` stamps
    changed EVERY run (~char 1080 of the user prompt), so identical prompts never byte-repeated — killing pinned-seed
    reproducibility and any prompt-keyed reuse. The fact stays honest ('the logged window, to the hour'); the date and
    the day-granular age text are unchanged by construction. Unparsable/absent → the raw value (fail-open)."""
    if v in (None, "", "NULL"):
        return v
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(str(v))
        return dt.replace(minute=0, second=0, microsecond=0).isoformat()
    except Exception:
        return v


def nameplate_line(asset):
    """One NAMEPLATE fact line for the resolved asset (its neuract table), or '' (no asset/table/outage).
    Values come from config.nameplates (per-asset asset_nameplate row + the derived rating field-set); a missing
    rating prints '—' with the unbindable rule attached — the honest fact that STOPS a faith-based const."""
    table = (asset or {}).get("table")
    if not table:
        return ""
    try:
        from config.nameplates import get_nameplate, derive_ratings
        np = get_nameplate(table)
        derived = derive_ratings(np.get("rated_kva"), np.get("nominal_voltage_ll")) if np else {}
        src = f" (source={np.get('source')})" if np and np.get("source") not in (None, "", "none") else ""
        return (f"NAMEPLATE (this asset's real rating row{src}): rated_kva={_fmt((np or {}).get('rated_kva'))} | "
                f"rated_kw={_fmt(derived.get('rated_kw'))} | rated_current_a={_fmt(derived.get('rated_current_a'))} | "
                f"contracted_kw={_fmt(derived.get('contracted_kw'))} — ★ '—' ⇒ that rating is UNKNOWN for this asset: "
                f"any fn/const needing it is UNBINDABLE — omit the field (honest-blank), NEVER guess a number.")
    except Exception:
        return ""


def data_window_line(asset, basket=None):
    """One DATA WINDOW fact line — the resolved data table's real first/last logged ts + last-sample age — or ''
    (no table / empty table / outage). Uses the BASKET's selected table first (for an aggregate panel that is the
    representative feeder table; the panel's own device table is an empty stub), else the asset table — the same
    choice validate/build.py probes, so the fact matches what fills."""
    table = ((basket or {}).get("tables") or [None])[0] or (asset or {}).get("table")
    if not table:
        return ""
    try:
        from datetime import datetime, timezone
        from config import neuract_dsn as _dsn
        from ems_exec.data import neuract as _nx
        ts = _dsn.ts_col()
        first_row, last_row = _nx.window(table, [ts], None, None)
        first, last = (first_row or {}).get(ts), (last_row or {}).get(ts)
        if not last:
            return ""
        age = ""
        try:
            last_dt = datetime.fromisoformat(str(last))
            from replay.clock import now as _replay_now         # frozen during replay: this age lands in PROMPT bytes
            now = _replay_now(last_dt.tzinfo or timezone.utc)
            age = f" (last sample is {max(0, (now - last_dt).days)}d old)"
        except Exception:
            pass
        from layer2.emit.diet import prompt_stability as _stab
        if _stab():
            first, last = bucket_ts(first), bucket_ts(last)   # hour-bucketed facts → byte-stable prompts [Stage 4]
        return (f"DATA WINDOW (table {table}'s real logged rows): first={_fmt(first)} last={_fmt(last)}{age} — "
                f"★ anchor every range/window to LAST, not wall-clock 'today': on a lagging/static dataset a "
                f"wall-clock 'today' window is EMPTY and every leaf blanks. Declare the range the story needs; "
                f"the fill anchors it to the data's own reference now.")
    except Exception:
        return ""
