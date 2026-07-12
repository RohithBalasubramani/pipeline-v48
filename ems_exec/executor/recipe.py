"""ems_exec/executor/recipe.py — the card_fill_recipe ROW reader + the AI-emission merge for the roster interpreter.
One concern: turn (data_instructions.roster, card_id) into the NORMALIZED roster instruction list the interpreter runs.

THE PRIORITY (per the generalization package §2/§3): the recipe row is AUTHORITATIVE for everything structural (slot
paths, element keys, group semantics, reducers, floors, caps, order); the AI's only real decision surface is the COLUMN
inside a col/delta/phase_mean/prefer_abs binding. So:
  · AI emitted nothing → the recipe row ships verbatim (deterministic fail-open — the worst AI failure mode equals the
    recipe-derived output).
  · AI emitted roster entries → each is folded INTO its recipe slot: column choices (c/cs) overwrite only keys that
    exist in the recipe and are not honest-null ({"b":"null"} keys are uncolonizable); caps may only shrink; slots the
    AI omitted are appended verbatim; AI-only slots (not in the recipe) are dropped.
  · No recipe row at all → the AI roster passes through as-is (the Layer-2 gate is the validator upstream; a card with
    neither recipe nor emission simply has no roster → the interpreter no-ops).

`$same_as_slot` intra-row references (the seed rows' way of not triple-duplicating one element JSON) are expanded here,
before anything downstream sees them. Reads cmd_catalog.card_fill_recipe via data.db_client.q (SELECT-only), cached per
process; any DB outage → {} (honest fail-open: no recipe → recipe-less behavior, never a crash). [atomic]
"""
from __future__ import annotations

import copy
import json
from functools import lru_cache


@lru_cache(maxsize=256)
def read(card_id):
    """{handling_class, roster_spec} for a card from cmd_catalog.card_fill_recipe ({} when absent / unreadable), with
    every intra-row {"$same_as_slot": <slot>} reference expanded."""
    if card_id is None:
        return {}
    try:
        cid = int(card_id)
    except (TypeError, ValueError):
        return {}
    try:
        from data.db_client import q
        rows = q("cmd_catalog", f"SELECT handling_class, roster_spec FROM card_fill_recipe WHERE card_id = {cid}")
    except Exception:
        return {}
    if not rows or not rows[0]:
        return {}
    handling, spec = rows[0][0], rows[0][1]
    if isinstance(spec, str):
        try:
            spec = json.loads(spec)
        except Exception:
            return {}
    if not isinstance(spec, dict):
        return {}
    return {"handling_class": handling, "roster_spec": _expand(spec)}


def _expand(spec):
    """Expand {"$same_as_slot": "<slot>"} references: any slot part (element/group/group_agg/agg/…) declared as a
    reference is replaced by a DEEP COPY of the referenced slot's same part. One pass (references point at literal
    slots in the seed rows); an unresolvable reference honest-drops to {} rather than crashing."""
    out = copy.deepcopy(spec)
    slots = out.get("slots") or []
    by_slot = {s.get("slot"): s for s in slots if isinstance(s, dict)}
    for s in slots:
        if not isinstance(s, dict):
            continue
        for part, val in list(s.items()):
            if isinstance(val, dict) and "$same_as_slot" in val:
                ref = by_slot.get(val.get("$same_as_slot")) or {}
                s[part] = copy.deepcopy(ref.get(part)) if isinstance(ref.get(part), (dict, list)) else {}
    return out


@lru_cache(maxsize=64)
def _endpoint_card(endpoint):
    """cmd_catalog.endpoint_recipe_map: consumer endpoint → the card_fill_recipe card_id for that card FAMILY's data
    contract. The plain run_card path (and the /api/frame date re-fetch) carries NO card_id, so a single-asset card's
    recipe row was unreachable; the endpoint the emission itself declares ('current-history') names the same contract.
    None when unmapped / table absent / DB outage (honest fail-open — recipe-less behavior)."""
    if not endpoint:
        return None
    try:
        from data.db_client import q
        e = str(endpoint).replace("'", "''")
        rows = q("cmd_catalog", f"SELECT card_id FROM endpoint_recipe_map WHERE endpoint = '{e}'")
        return int(rows[0][0]) if rows and rows[0] and rows[0][0] is not None else None
    except Exception:
        return None


def _card_key(data_instructions, card_id):
    """The recipe lookup key: the explicit card_id WHEN it has its own recipe row, else the endpoint-mapped card
    FAMILY (endpoint_recipe_map — the emission's own declared endpoint names the shared data contract). An explicit
    id with NO row FALLS THROUGH to the family (a caller now passes card_id on every run_card; without the
    fallthrough it would mask the family recipe — card 69's current-history windowed-stats contract lives on family
    card 46). The consumer's endpoint wins; the AI's fetch-spec endpoint is the compat fallback."""
    if card_id is not None and read(card_id):
        return card_id
    di = data_instructions or {}
    consumer = di.get("consumer")
    endpoint = consumer.get("endpoint") if isinstance(consumer, dict) else None
    if not endpoint:
        from domain.fetch_spec import fetch_spec
        endpoint = fetch_spec(di).get("endpoint")
    return _endpoint_card(endpoint) or card_id


def roster_for(data_instructions, card_id):
    """The NORMALIZED roster instruction list for this card: the AI emission folded into the recipe row (recipe wins
    structurally), the recipe verbatim when the AI omitted it, the emission as-is when no recipe exists, [] when
    neither. Also returns nothing for a roster-less narrative recipe (mode='narrative' → slots=[])."""
    emitted = (data_instructions or {}).get("roster")
    emitted = [r for r in (emitted or []) if isinstance(r, dict)]
    spec = read(_card_key(data_instructions, card_id)).get("roster_spec") or {}
    spec_slots = [s for s in (spec.get("slots") or []) if isinstance(s, dict) and s.get("slot")]
    if not spec_slots:
        return list(emitted)                     # no recipe → gate-validated emission as-is (or nothing at all)
    by_slot = {r.get("slot"): r for r in emitted}
    normalized = []
    for s in spec_slots:
        ai = by_slot.get(s.get("slot"))
        normalized.append(_fold(ai, s) if ai else copy.deepcopy(s))
    return normalized


def coverage_attach(card_id):
    """Where this card's recipe attaches the honest coverage badge (dotted path), or None."""
    spec = read(card_id).get("roster_spec") or {}
    return spec.get("coverage_attach")


def _fold(ai, spec):
    """Fold ONE AI roster entry into its recipe slot: recipe wins every structural field; the AI's column choices
    (c / cs, incl. the bare-string shorthand) land only on element keys that exist in the recipe and are not
    honest-null; a cap may only shrink."""
    out = copy.deepcopy(spec)
    element = out.get("element")
    for k, v in (ai.get("element") or {}).items():
        b = {"b": "col", "c": v} if isinstance(v, str) else (v if isinstance(v, dict) else None)
        if b is None or not isinstance(element, dict) or k not in element:
            continue                              # unknown / invented key → recipe stands
        cur = element.get(k) or {}
        if (cur.get("b") or "").strip().lower() == "null":
            continue                              # honest-null keys are uncolonizable
        folded = dict(cur)
        for kk in ("c", "cs"):
            if kk in b:
                folded[kk] = b[kk]
        element[k] = folded
    try:
        if ai.get("cap") is not None and out.get("cap") is not None:
            out["cap"] = min(int(ai["cap"]), int(out["cap"]))
    except (TypeError, ValueError):
        pass
    return out


