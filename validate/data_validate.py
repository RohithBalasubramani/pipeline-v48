"""validate/data_validate.py — per basket-column data-quality verdict from the pandas frame (non-AI). [validate]

NULL-GATE POLICY (2026-07-07, validate/null_gate.py): the >MAX_NULL_RATE check is DB-driven
(validate.null_gate_mode fail|warn|off, default warn — an informational annotation, no longer a verdict=fail),
and EVENT/COUNTER/BOOLEAN-semantic columns (name-token vocab / boolean dtype) treat NULL as 'no event' ≡ 0 for
the verdict statistics — a 99.85%-null *_event_active burst column is NORMAL sparsity, never a page 'N fail'.
Electrical quantities are NEVER coerced (a null voltage is NOT 0 V); their raw sparsity still surfaces (warn)."""
import pandas as pd

from config.validation import TIME_COLUMN, MAX_NULL_RATE, WARN_NULL_RATE, MIN_ROWS_SERIES
from validate.null_gate import null_gate_mode, is_event_semantic, coerce_event_nulls


def _verdict(present, null_rate, latest_ok, *, event_semantic=False, raw_null_rate=None):
    if not present:
        return "fail", ["column absent from meter table"]
    if event_semantic:
        # EVENT/COUNTER/BOOLEAN semantics: NULL = 'no event' ≡ 0 → sparsity is NORMAL, never a null-rate verdict;
        # the latest-row warn does not apply either (a null latest row means 'no event now'). Informational only.
        raw = raw_null_rate if raw_null_rate is not None else null_rate
        if raw > WARN_NULL_RATE:
            return "pass", [f"event-semantic column: null='no event' (raw null_rate {raw:.2f} is normal event sparsity)"]
        return "pass", []
    reasons = []
    v = "pass"
    if null_rate > MAX_NULL_RATE:
        mode = null_gate_mode()                # DB knob validate.null_gate_mode: fail | warn (default) | off
        if mode == "fail":
            return "fail", [f"null_rate {null_rate:.2f} > {MAX_NULL_RATE}"]
        if mode == "warn":
            v, reasons = "warn", [f"null_rate {null_rate:.2f} > {MAX_NULL_RATE} "
                                  f"(informational: mostly-null over the probe window, per-leaf telemetry not a fail)"]
        # mode == 'off' → the mostly-null annotation is silent entirely (latest-row warn below still applies)
    elif null_rate > WARN_NULL_RATE:
        v, reasons = "warn", reasons + [f"null_rate {null_rate:.2f} > {WARN_NULL_RATE}"]
    if latest_ok is False:                     # None = unordered read → the latest-row claim is UNKNOWN, not a warn
        v = "warn" if v == "pass" else v
        reasons.append("no value in latest row")
    return v, reasons


def validate_data(df, basket_columns, *, ordered=True):
    """basket_columns: [{column,label,kind,unit,...}] from 1b. `ordered`: row 0 is genuinely the newest (a table with
    no time column loads in arbitrary heap order — then latest_ok is None/'unknown', never a fabricated claim).
    Returns {columns:[...], summary, span, rows}."""
    rows = int(len(df))
    out = []
    for c in basket_columns:
        col = c["column"]
        present = col in df.columns
        event_sem = False
        if present and rows:
            s = df[col]
            dtype = str(s.dtype)
            event_sem = is_event_semantic(col, dtype=dtype)
            null_rate = float(s.isna().mean())               # RAW sparsity — always reported as honest telemetry
            nonnull = int(s.notna().sum())                   # RAW (the executor does not coerce nulls today)
            numeric = bool(pd.api.types.is_numeric_dtype(s))
            if event_sem:
                # the validate-local coercion point: verdict stats of an event column read NULL as 0 ('no event').
                # ONLY the verdict inputs — null_rate/nonnull above stay raw; the frame itself is never mutated.
                s_eff = coerce_event_nulls(s)
                latest_ok = bool(s_eff.notna().iloc[0]) if ordered else None
            else:
                latest_ok = bool(s.notna().iloc[0]) if ordered else None
        else:
            null_rate, latest_ok, nonnull, dtype, numeric = 1.0, False, 0, None, False
        verdict, reasons = _verdict(present, null_rate if not event_sem else 0.0, latest_ok,
                                    event_semantic=event_sem, raw_null_rate=null_rate)
        out.append({
            "column": col, "label": c.get("label"), "kind": c.get("kind"), "unit": c.get("unit"),
            "present": present, "rows": rows, "nonnull": nonnull, "null_rate": round(null_rate, 4),
            "latest_ok": latest_ok, "dtype": dtype, "numeric": numeric, "event_semantic": event_sem,
            "series_capable": bool(numeric and nonnull >= MIN_ROWS_SERIES),
            "verdict": verdict, "reasons": reasons,
        })
    span = None
    if TIME_COLUMN in df.columns and rows:
        # utc=True: the window can straddle the +00:00→+05:30 writer switch — without it pandas yields object dtype
        # (FutureWarning today, ValueError in pandas 3) on mixed offsets.
        ts = pd.to_datetime(df[TIME_COLUMN], errors="coerce", utc=True)
        span = {"from": str(ts.min()), "to": str(ts.max())}
    summary = {"n_columns": len(out),
               "n_pass": sum(1 for x in out if x["verdict"] == "pass"),
               "n_warn": sum(1 for x in out if x["verdict"] == "warn"),
               "n_fail": sum(1 for x in out if x["verdict"] == "fail")}
    return {"rows": rows, "span": span, "columns": out, "summary": summary}
