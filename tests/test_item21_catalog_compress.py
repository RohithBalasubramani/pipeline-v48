"""Item 21 [AI_QUALITY_BACKLOG D5] — 1a catalog compression + 1b label dedup.

(a) layer1a: the PAGES catalog the router sees collapses purpose/theme/answers (3 prose restatements, ~10.4K of the
    14.7K-char user message) into ONE deduplicated story line per page. RECALL PROOF: every canonical page_key and
    every title still resolve VERBATIM from the compressed text, and the near-tie story keywords the routing rules in
    layer1a/prompts/system.md key on (battery/autonomy, fuel, harmonic, panel/feeder granularity) survive on their
    page's own line.
(b) layer1b: the column dictionary label was ALWAYS the trivial title-case of the column name — a pure repeat in every
    basket prompt line — so describe() emits it only when it differs (today: never; ~1-1.4K chars/call saved).

Offline-safe: fixture tests below run without the DB; the *_live tests read cmd_catalog/neuract like the rest of the
layer1 suites (no LLM call — not `live`-marked, per suite convention).
"""
from config.available_pages import AVAILABLE_PAGES
from layer1a.catalog_compress import merge_story
from layer1b.basket.describe import describe, title_label


# ── (a) merge_story: generic clause dedup (offline fixtures) ──────────────────────────────────────────────────────
THEME = "Per-asset engine health diagnostics — thermal + mechanical timeseries against the physical machine."
ANSWERS = ("Is the engine running hot? How do oil pressure, speed and load track the temperature over the window? "
           "When did run-state events occur?")
PURPOSE = ("Give the operator a single-generator engine & cooling diagnostic view that pairs the physical 3D engine "
           "model with the thermal / mechanical history needed to judge overheating, oil-pressure, speed and load "
           "behaviour over the selected window.")


def test_merge_story_dedups_restatements():
    merged = merge_story(PURPOSE, THEME, ANSWERS, min_new_tokens=4, min_new_ratio=0.6, max_chars=320)  # code defaults
    assert merged.startswith("Per-asset engine health diagnostics")           # theme framing kept first
    assert len(merged) < len(PURPOSE) + len(THEME) + len(ANSWERS)             # genuinely compressed
    # answers clause restating theme words ('Is the engine running hot?' — engine already seen) dedups away ...
    assert "Is the engine running hot?" not in merged
    assert "oil pressure, speed and load track the temperature" in merged     # ... while the NEW question words stay
    # purpose (longest restatement, ordered LAST) is the tail the default cap cuts at a clause boundary
    assert "Give the operator a single-generator" not in merged
    assert merged == merge_story(PURPOSE, THEME, ANSWERS, min_new_tokens=4, min_new_ratio=0.6, max_chars=320)  # deterministic


def test_merge_story_keeps_granularity_keywords():
    # the routing rules key on granularity words (panel / feeder / single-generator) — first mention is always kept
    m = merge_story("", "Live cross-feeder monitoring of the whole panel (metric heatmap + time scrubber)",
                    "Which feeders are hot right now for this metric?", max_chars=0)
    assert "panel" in m.lower() and "feeder" in m.lower()


def test_merge_story_cap_cuts_at_clause_boundary():
    m = merge_story(PURPOSE, THEME, ANSWERS, min_new_tokens=4, min_new_ratio=0.6, max_chars=60)
    assert m == THEME.split(" — ")[0].rstrip(".")            # first clause survives whole, never mid-word
    assert merge_story("", "", "") == ""                     # empty fields → empty story, never raises


# ── (a) live recall proof: 18 canonical page_keys resolve verbatim from the COMPRESSED catalog ────────────────────
def _block():
    from layer1a.db_reads.page_specs import read_page_specs
    from layer1a.db_reads.card_titles import read_card_titles
    from layer1a.route import _candidate_block
    from config.available_pages import filter_to_available
    specs = filter_to_available(read_page_specs())
    return specs, _candidate_block(specs, read_card_titles())


def test_catalog_recall_page_keys_and_titles_verbatim_live():
    specs, blk = _block()
    assert [k for k in AVAILABLE_PAGES if k not in blk] == []                 # EVERY canonical page_key, verbatim
    assert [s["title"] for s in specs if s["title"] not in blk] == []         # every title, verbatim
    # one-line page entries: every '- ' entry carries key|title|story|cards on the SAME line
    entries = [ln for ln in blk.splitlines() if ln.startswith("- ")]
    assert len(entries) == len(specs)
    assert all(" | cards: " in ln for ln in entries)


def test_catalog_compressed_size_live():
    specs, blk = _block()
    uncompressed = sum(len(s["purpose"]) + len(s["theme"]) + len(s["answers"]) for s in specs)
    stories = sum(len(ln.split(" | story: ", 1)[1].split(" | cards: ")[0])
                  for ln in blk.splitlines() if " | story: " in ln)
    assert stories < 0.6 * uncompressed                       # the 3-restatement prose collapsed by >40%
    assert len(blk) < 10_500                                  # was 14,733; measured 7,954 (lenient DB-drift bound)


def test_catalog_near_tie_keywords_survive_live():
    # the near-tie routes in layer1a/prompts/system.md decide on these story words — each page's OWN line keeps them
    _specs, blk = _block()
    lines = {ln.split(" | ", 1)[0][2:]: ln.lower() for ln in blk.splitlines() if ln.startswith("- ")}
    assert "battery" in lines["ups-asset-dashboard/battery-autonomy"]
    assert "fuel" in lines["diesel-generator-asset-dashboard/fuel-efficiency"]
    assert "harmonic" in lines["individual-feeder-meter-shell/power-quality"]
    assert "voltage" in lines["individual-feeder-meter-shell/voltage-current"]
    rtm = lines["panel-overview-shell/real-time-monitoring"]
    assert "panel" in rtm and ("real-time" in rtm or "live" in rtm)
    assert "feeder" in lines["panel-overview-shell/real-time-monitoring"]     # panel-vs-feeder granularity evidence


# ── (b) 1b label dedup ────────────────────────────────────────────────────────────────────────────────────────────
def test_describe_label_dedup_offline():
    # label field rides EMPTY when it equals title_label(col) (today: always); kind/unit positions untouched
    assert describe("voltage_ll_ry") == ["", "raw", "V"]
    assert describe("active_power_total_kw")[1:] == ["raw", "kW"]
    assert describe("sag_event_active") == ["", "event", ""]                  # event rule intact, no unit
    assert title_label("voltage_ll_ry") == "Voltage Ll Ry"                    # the on-demand display derivation


def test_col_dict_rows_deduped_and_saving_live():
    from layer1b.basket.col_dict import col_dict
    rows = col_dict("gic_03_n6_ahu_5_p1")                                     # the suite's anchor meter
    assert rows and all(r[1] == "" for r in rows)                             # every label deduped away
    saved = sum(len(title_label(r[0])) for r in rows)                         # chars the basket lines no longer carry
    assert saved > 800                                                        # ~1-1.4K/call on a ~63-71 col meter
