"""fab_guards/class23_source.py — CLASS 2/3: the per-written-field SOURCE audit (a value claiming a column the
table doesn't have / a table with no rows is not a reading). _ROWS_CACHE lives HERE (module-global, re-exported
by-reference from the package __init__ — tests clear() it between cases; the dict object must stay THE one)."""
from __future__ import annotations

from ems_exec.data import neuract as _nx
from config import nameplate_slot_map as _slot_map
from ems_exec.executor.paths import _leaf_at, _set_path, _leaf_path_for
from ems_exec.executor.series_fill import _element_value_key
from ems_exec.executor.fab_guards.knobs import _guard_on, _is_num, _add_gap

# [S2] TTL cache (was a plain dict that NEVER invalidated): a table probed during a tunnel flap (latest_ts→None→False)
# used to hold that stale False for the whole process life, biasing CLASS 2 to stand down forever on a since-recovered
# table. TTLCache self-heals after cache.resolution_ttl_s (or fab_guards.logged_cache_ttl_s if pinned). Tests still
# .clear() it by reference (dict semantics preserved).
try:
    from data.ttl_cache import TTLCache as _TTLCache

    def _rows_ttl():
        try:
            from config.app_config import cfg
            v = cfg("fab_guards.logged_cache_ttl_s", None)
            return int(v) if v is not None else None
        except Exception:
            return None
    _ROWS_CACHE = _TTLCache(ttl=_rows_ttl())
except Exception:
    _ROWS_CACHE = {}


def _table_has_rows(asset_table):
    """Is the table demonstrably REACHABLE with at least one row? The CLASS-2 conclusiveness gate: a genuine all-null
    column is only distinguishable from a DB outage when the table itself HAS data (neuract.latest_ts is not None). DB
    down / empty / missing table → None → False → CLASS 2 stays its hand (never blanks a real reading it can't disprove).
    Cached per table per process (latest_ts is itself cached upstream). Never raises."""
    if not asset_table:
        return False
    hit = _ROWS_CACHE.get(asset_table)
    if hit is not None:
        return hit
    try:
        ok = _nx.latest_ts(asset_table) is not None
    except Exception:
        ok = False
    _ROWS_CACHE[asset_table] = ok
    return ok


def _field_leaf_path(out, field):
    """The dotted leaf path a field resolved to (the SAME resolution fill() used: data.<slot> or <slot>, then metric,
    then target_column). None when the skeleton has no such leaf."""
    slot = field.get("slot") or field.get("target_column") or field.get("metric")
    return (_leaf_path_for(out, slot)
            or _leaf_path_for(out, field.get("metric"))
            or _leaf_path_for(out, field.get("target_column")))


def _field_has_source(field, present_cols):
    """Does this field carry a RESOLVED data source (ANY of the executor's fill paths)? A superset of every legit fill:

      • kind='time'                       — fills from the card's own bucket axis (a real derived time source);
      • a PRESENT column (raw/bucketed/event) — the meter carries it;
      • a derivation fn/metric that binds   — kind='derived', OR a column-less field whose fn/metric resolves a
        cmd_catalog.derivation_binding row (metric='loadPct' → kpiKwLoadPctOfRated — the column-less series family);
      • a nameplate rating slot             — a const/text slot the slot-map maps to a real rating.

    False = NONE of those resolved: the field is declared null (its roster/binding has no source) and any numeric value
    surviving on its leaf is a no-source stray (CLASS 3). A const/text LITERAL is handled by the caller (chrome)."""
    kind = (field.get("kind") or "raw").lower()
    if kind == "time":
        return True                                             # fills from the card's bucket axis (real source)
    if kind == "derived" and (field.get("fn") or field.get("metric")):
        return True
    col = field.get("column")
    if col and col in present_cols:
        return True
    # a COLUMN-LESS series/scalar field whose fn/metric resolves a derivation_binding row IS sourced (the column-less
    # family — the same resolution indexed_families/wildcards use). Reuse that ONE resolver, never re-implement it.
    try:
        from ems_exec.executor.indexed_families import _binding_for_field
        if _binding_for_field(field):
            return True
    except Exception:
        pass
    # a const/text nameplate slot resolves from the real rating — a real source
    rk = _slot_map.rating_key_for(field.get("slot")) or _slot_map.rating_key_for(field.get("metric"))
    if rk:
        return True
    return False


def _live_literal_on():
    """fab_guards.live_literal [S1a, default on]: the STRING-only guard that blanks a const/text leaf CLAIMING
    source='live' with no column and no rating source (card-78 tapPosition 'AUTO' / status.tone 'Nominal') — a literal
    DRESSED as a live reading. Split off its own valve from `no_source` (whose NUMERIC branch is retired) because this
    string charter never fought a legitimate writer and stays. Fail-open to ON."""
    try:
        from config.app_config import flag_on
        return flag_on("fab_guards.live_literal", True)
    except Exception:
        return True


def _writer_aware_on():
    """fab_guards.null_column_writer_aware [S2, default off]: on a PANEL-AGGREGATE fill the raw values came from the
    member ROLL-UP (ctx['_agg_row']), NOT from asset_table — so CLASS 2's column_logged(asset_table, col) audit is
    invalid (asset_table is the panel's control table; the real source is the members). When on + agg_row present,
    CLASS 2 stands down for that card (the roll-up reducers already honest-null when no member reports; this is the
    generalization of the card-15 roster-slot exemption to the whole panel fill). Fail-open to OFF (byte-identical)."""
    try:
        from config.app_config import flag_on
        return flag_on("fab_guards.null_column_writer_aware", False)
    except Exception:
        return False


def _apply_class2_class3(out, fields, present_cols, asset_table, gaps, skip_paths, agg_row_present=False):
    """For every field the executor filled, audit its leaf's SOURCE:

      CLASS 2 — the field binds a PRESENT column that is 100% NULL on the table (neuract.column_logged == False): a
                written numeric leaf is 0.0/placeholder posing as a reading → blank it ('not measured — column
                all-null'). Present-and-logged columns (a real 0.0) are exempt. WRITER-AWARE [S2]: skipped for a
                panel-aggregate fill (`agg_row_present`) — those values came from the member roll-up, not asset_table.

      LIVE-LITERAL — a const/text leaf CLAIMING source='live' with no column/rating (a string literal dressed as a live
                reading) is blanked. Own valve fab_guards.live_literal (STRING-only charter).

      CLASS 3 (no_source, NUMERIC) — DEPRECATED/RETIRING: the field has NO resolved source yet a numeric value survives
                → blank it. Its true positives are already caught PRE-FILL by the layer2 honest-blank walls
                (walls.py _blankable_field/_quantity_mismatch/_const_without_source), cross_domain and column_override
                (all cert-covered by wall_corpus_replay), and its only distinct surface (post-fill strays) produced 100%
                false positives in a week of served traffic (the card-15 panel family). Gated by fab_guards.no_source;
                retire by flipping that valve off after the shadow-fleet baseline confirms zero true-positive fires.

    Only WRITTEN numeric MEASUREMENT leaves are touched (scalar, or a numeric array / series-of-objects value key).
    `skip_paths` = the CLASS-1-blanked (+ roster-exempt) paths. Never raises."""
    for field in fields:
        kind = (field.get("kind") or "raw").lower()
        if kind in ("const", "text"):
            # LIVE-LITERAL (string charter, own valve). A genuine static label (source != 'live') stays untouched.
            if _live_literal_on() and str(field.get("source") or "").lower() == "live":
                _rk = _slot_map.rating_key_for(field.get("slot")) or _slot_map.rating_key_for(field.get("metric"))
                _c0 = field.get("column")
                if not _rk and not (_c0 and _c0 in present_cols):
                    _p = _field_leaf_path(out, field)
                    _cur = _leaf_at(out, _p) if _p else None
                    if _p and _p not in skip_paths and isinstance(_cur, str) and _cur.strip() not in ("", "—"):
                        _set_path(out, _p, None)
                        _add_gap(gaps, _p, "no_source_value", field.get("label") or field.get("slot") or "value", column=None)
            continue
        path = _field_leaf_path(out, field)
        if not path or path in skip_paths:
            continue
        cur = _leaf_at(out, path)
        col = field.get("column")
        has_col = bool(col and col in present_cols)

        # CLASS 2 — bound column present but 100% NULL over the whole table → any written value is not a reading.
        # CONCLUSIVENESS GATE (never over-reach on a DB outage): column_logged() returns False BOTH for a genuinely
        # all-null column AND for an unreachable/errored read — so we only trust the all-null verdict when the table is
        # demonstrably REACHABLE and has rows (_table_has_rows via latest_ts). DB down / empty table → inconclusive →
        # leave the real reading alone. WRITER-AWARE [S2]: on a panel-aggregate fill the value came from the member
        # roll-up (agg_row), not asset_table, so probing asset_table's column is meaningless → stand down.
        if _guard_on("null_column") and not (agg_row_present and _writer_aware_on()) \
                and has_col and _table_has_rows(asset_table) and not _nx.column_logged(asset_table, col):
            if _blank_numeric_leaf(out, path, cur):
                metric = field.get("label") or field.get("metric") or col
                _add_gap(gaps, path, "null_column_reading", metric, column=col)
            continue

        # CLASS 3 (numeric no-source) — retiring; gated by fab_guards.no_source (flip off to retire). Also stands down
        # on a writer-aware panel fill (the value came from the roll-up, not the declared field's dead column).
        if _guard_on("no_source") and not (agg_row_present and _writer_aware_on()) \
                and not _field_has_source(field, present_cols):
            if _blank_numeric_leaf(out, path, cur):
                metric = field.get("label") or field.get("metric") or field.get("slot") or "value"
                _add_gap(gaps, path, "no_source_value", metric, column=col)


def _blank_numeric_leaf(out, path, cur):
    """Blank the leaf at `path` IF it currently carries a NUMERIC value (scalar, a numeric array, or a series-of-objects
    whose value key holds numbers). Returns True when something was blanked. A leaf already blank (None/'—'/[]/all-None)
    is left as-is (no double work); a non-numeric string/dict leaf is never touched (not a measurement)."""
    if _is_num(cur):
        _set_path(out, path, None)
        return True
    if isinstance(cur, list) and cur:
        # numeric array → [] ; series-of-objects → blank each element's value key
        if all(_is_num(x) or x is None for x in cur) and any(_is_num(x) for x in cur):
            _set_path(out, path, [])
            return True
        if all(isinstance(e, dict) for e in cur):
            vk = _element_value_key(cur[0])
            blanked = False
            if vk:
                for el in cur:
                    if _is_num(el.get(vk)):
                        el[vk] = None
                        blanked = True
            return blanked
    return False


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  CLASS 4 — UNSTRIPPED SEED-LEAK — a leaf byte-identical to the DEFAULT payload at the same path, never filled → blank.
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
