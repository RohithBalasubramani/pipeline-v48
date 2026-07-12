"""layer2/cross_domain.py — the CROSS-DOMAIN HONESTY pass (emit-correctness E/G): a data field whose bound
column/fn measures a DIFFERENT physical quantity than its slot must honest-BLANK (a POWER value cannot be an ENERGY
reading no matter how it is relabelled) — per-leaf, never a card-block. Extracted from layer2/build.py (one concern;
build.py re-exports byte-compatibly)."""

def _fn_quantity_map():
    """{library fn -> its output quantity string} from the derivation registry, for the cross-domain honesty check."""
    try:
        from ems_exec.derivations.registry import catalog
        return {e["fn"]: e.get("quantity") for e in catalog()}
    except Exception:
        return {}


def _cross_domain_fields(di):
    """Data fields whose bound column/fn measures a DIFFERENT physical DOMAIN than the field's own slot — a wrong-KIND
    stand-in that must never claim "full" (E: a current column under a voltage-THD leaf; G: an energy fn in a 'years'
    leaf). Generic + DB-driven: config.metrics.quantity_family over the SLOT PATH's own semantic (not the AI-authored
    metric label, which the AI can bend to match its wrong pick) vs the bound column / fn quantity. A None family on
    EITHER side → NOT flagged (no false positive on a legitimate same-quantity bind). Returns
    [(slot, slot_family, source, source_family)]."""
    from config.metrics import quantity_family, slot_semantic_label
    fn_q = _fn_quantity_map()
    out = []
    for f in (di.get("fields") or []):
        if f.get("kind") in ("time", "const", "event"):
            continue
        slot = f.get("slot") or ""
        sfam = quantity_family(slot_semantic_label(slot))
        if not sfam:
            continue
        if f.get("kind") == "derived":
            src = f.get("fn") or ""
            cfam = quantity_family(fn_q.get(src) or src)
        else:                                             # raw / bucketed → its real column
            src = f.get("column") or ""
            cfam = quantity_family(src)
        if cfam and cfam != sfam:
            out.append((slot, sfam, src, cfam))
    return out


def _cross_domain_note(xdom):
    """One truthful user-facing sentence: the leaf's real quantity isn't measured, so the wrong-domain reading is
    honest-BLANKED (not rendered). The honest override for a wrong-kind fill (per-leaf degradation, never a card-block)."""
    slot, sfam, src, cfam = xdom[0]
    extra = f" (and {len(xdom) - 1} other leaf(s))" if len(xdom) > 1 else ""
    return (f"{sfam} isn't measured for this leaf on this asset — the only candidate was a {cfam} value ({src}), a "
            f"different physical quantity, so the leaf is left blank{extra} rather than shown under the wrong unit.")


def _blank_cross_domain_leaves(di, xdom):
    """PER-LEAF BLANKING PASS for the cross-domain fields _cross_domain_fields flagged (slot_family != source_family,
    both known). A wrong-QUANTITY reading is not real data (a POWER value cannot be a true ENERGY reading no matter how
    it is relabelled), so per the zero-fabrication mandate the leaf must HONEST-BLANK, exactly like column_override's
    slot-quantity guard does — NOT merely carry a telemetry note while still rendering the wrong number.

    Mirrors resolve/column_override.apply's drop convention: DROP the bound column/fn (→ None) and reroute the field to
    the FRAME honest-blank path (source='frame'), so the executor returns None for that leaf (fill.py: a raw/bucketed/
    event field with column=None honest-blanks; a derived field with fn=None+metric=None falls to the raw path and
    honest-blanks too). PER-LEAF only — it edits ONLY the flagged field dicts (matched by slot + bound source), so every
    OTHER field on the card still renders its real data; it is NEVER a card-block. Generic + DB-driven (no card ids).

    A genuine SAME-domain proxy is inherently safe: _cross_domain_fields flags ONLY cfam != sfam with both known, so a
    declared/display-morphed same-quantity proxy (cfam == sfam, the R7 rule already honored in _cross_domain_fields) is
    never in `xdom` and is never touched here. Mutates di['fields'] in place; returns the count of leaves blanked."""
    flagged = {(str(s), str(src)) for (s, _sf, src, _cf) in xdom}
    n = 0
    for f in (di.get("fields") or []):
        if not isinstance(f, dict):
            continue
        slot = str(f.get("slot") or "")
        # the SAME source string _cross_domain_fields keyed on: fn for a derived field, else the column
        src = str((f.get("fn") if f.get("kind") == "derived" else f.get("column")) or "")
        if (slot, src) not in flagged:
            continue
        # DROP the wrong-domain bind exactly like the column_override slot-quantity guard: column/fn → None, reroute to
        # the frame/honest-blank path so THIS leaf renders blank while its siblings still fill. Keep the slot/shape.
        f["column"] = None
        if f.get("kind") == "derived":
            f["fn"] = None
            f["metric"] = None                                  # so fill.py's `fn or metric` derived branch cannot re-fire
        f["source"] = "frame"
        n += 1
    return n
