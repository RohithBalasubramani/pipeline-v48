"""validate/data_validate.py — per basket-column data-quality verdict from the pandas frame (non-AI). [validate]"""
import pandas as pd

from config.validation import TIME_COLUMN, MAX_NULL_RATE, WARN_NULL_RATE, MIN_ROWS_SERIES


def _verdict(present, null_rate, latest_ok):
    if not present:
        return "fail", ["column absent from meter table"]
    if null_rate > MAX_NULL_RATE:
        return "fail", [f"null_rate {null_rate:.2f} > {MAX_NULL_RATE}"]
    reasons = []
    v = "pass"
    if null_rate > WARN_NULL_RATE:
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
        if present and rows:
            s = df[col]
            null_rate = float(s.isna().mean())
            latest_ok = bool(s.notna().iloc[0]) if ordered else None
            nonnull = int(s.notna().sum())
            dtype = str(s.dtype)
            numeric = bool(pd.api.types.is_numeric_dtype(s))
        else:
            null_rate, latest_ok, nonnull, dtype, numeric = 1.0, False, 0, None, False
        verdict, reasons = _verdict(present, null_rate, latest_ok)
        out.append({
            "column": col, "label": c.get("label"), "kind": c.get("kind"), "unit": c.get("unit"),
            "present": present, "rows": rows, "nonnull": nonnull, "null_rate": round(null_rate, 4),
            "latest_ok": latest_ok, "dtype": dtype, "numeric": numeric,
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
