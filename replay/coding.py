"""replay/coding.py — typed JSON encode/decode. Injected rows must be INDISTINGUISHABLE from live psycopg2 reads:
datetime/date/time/Decimal survive the round-trip as the same Python types, tuples stay tuples (cursor.fetchall
returns list-of-tuples and downstream code indexes r[0] / formats datetimes). Plain JSON types pass through."""
import base64
import datetime as _dt
from decimal import Decimal

_TAG = "__replay_t"


def encode(v):
    """Any pipeline value → JSON-safe structure (lossless for the DB scalar types the pipeline sees)."""
    if isinstance(v, _dt.datetime):
        return {_TAG: "dt", "v": v.isoformat()}
    if isinstance(v, _dt.date):
        return {_TAG: "d", "v": v.isoformat()}
    if isinstance(v, _dt.time):
        return {_TAG: "tm", "v": v.isoformat()}
    if isinstance(v, Decimal):
        return {_TAG: "dec", "v": str(v)}
    if isinstance(v, bytes):
        return {_TAG: "b", "v": base64.b64encode(v).decode()}
    if isinstance(v, tuple):
        return {_TAG: "tup", "v": [encode(x) for x in v]}
    if isinstance(v, list):
        return [encode(x) for x in v]
    if isinstance(v, dict):
        return {str(k): encode(x) for k, x in v.items()}
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    return {_TAG: "repr", "v": repr(v)}                        # last resort: visible, never silently dropped


def decode(v):
    if isinstance(v, dict):
        tag = v.get(_TAG)
        if tag == "dt":
            return _dt.datetime.fromisoformat(v["v"])
        if tag == "d":
            return _dt.date.fromisoformat(v["v"])
        if tag == "tm":
            return _dt.time.fromisoformat(v["v"])
        if tag == "dec":
            return Decimal(v["v"])
        if tag == "b":
            return base64.b64decode(v["v"])
        if tag == "tup":
            return tuple(decode(x) for x in v["v"])
        if tag == "repr":
            return v["v"]                                      # irreversible; the repr string is the honest stand-in
        return {k: decode(x) for k, x in v.items()}
    if isinstance(v, list):
        return [decode(x) for x in v]
    return v
