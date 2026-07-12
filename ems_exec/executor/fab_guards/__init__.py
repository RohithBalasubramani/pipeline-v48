"""ems_exec/executor/fab_guards — DETERMINISTIC POST-FILL FABRICATION GUARDS (slot-name-INDEPENDENT class killers).

ONE post-fill pass that scans the FINISHED payload and blanks whole FABRICATION CLASSES regardless of the slot the AI
mislabeled — because the adversarial audit keeps finding the SAME class on a DIFFERENT slot each fire, so per-slot fixes
never generalize. Each guard is a CLASS killer, not a card fix; every blank carries a per-leaf reason on the SAME gaps
channel (gaps.py GAPS_KEY) the host pops. Runs as the LAST fabrication-guard pass in fill() — AFTER every honest-fill
pass (series + roster + yscale + display + freshness all done) so it sees the fully-assembled payload and never fights
an earlier honest fill; the three measurable RESCUES that follow (scalar_mean/scalar_tile/load_factor) only ADD
DB-verified values onto now-blank leaves (never fabricate), so no fabrication class survives this pass.

  CLASS 1 — EPOCH-MILLIS TIME-LEAK [card 46 maxLine/minLine/expectedMax/expectedMin ← [1783362600000,…]; card 59/43
            timestamps-as-data]. A leaf that is NOT a designated time axis (its key is NOT in the time-axis token set)
            but whose numeric value (scalar OR EVERY element of a numeric array) is an EPOCH-MILLIS magnitude
            (>= ~1e12, plausibly ms) is a timestamp that leaked into a value/scale leaf → BLANK it. Permanently kills the
            kind=time-over-application class no matter which slot the AI mislabels. A genuine reading (kW/V/A/%/count —
            all far below 1e12) is never touched.

  CLASS 2 — NULL-COLUMN-AS-READING [card 47 vThd.valuePct=0.0 while thd_compliance_v_avg is 0/61793 non-null]. A WRITTEN
            data leaf whose bound column is 100% NULL over the whole table (neuract.column_logged == False) must not
            ship 0.0/a placeholder as a reading — BLANK it (honest 'not measured — column all-null'). Only when the
            column is GENUINELY all-null; a real 0.0 measurement (its column IS logged) stays.

  CLASS 3 — NO-SOURCE VALUE [card 04 iThdPk=265.0 etc. — a peak-THD leaf filled from a non-THD source / with no source
            column]. A WRITTEN numeric leaf whose field has NO resolved source — no present column, no derivation fn,
            no nameplate rating, and no roster-source (the field/roster element is declared null) — must stay BLANK,
            never a stray value. A const/text literal the AI authored (label chrome) is NOT a no-source reading and is
            left alone; only numeric MEASUREMENT leaves are policed.

  CLASS 4 — UNSTRIPPED SEED-LEAK [card 73 backupHistory.series[*].legendValue = [52,71,85,43] byte-identical to the
            card-53 DEFAULT payload legendValue]. A leaf whose FINAL value is BYTE-IDENTICAL to the card's HARVESTED
            DEFAULT payload value at the SAME path AND was NOT written by any fill (its path is not in the written-path
            set / was never filled real) is an UNSTRIPPED SEED that survived into the served payload — BLANK it. Slot-
            name-INDEPENDENT (it never reasons about the key), OVER-REACH-SAFE: a FILLED-real leaf is protected by the
            written-path set (even if it coincidentally equals the seed scalar), and only ARRAY / STRING / compound
            seeds and NON-TRIVIAL scalars are policed (a bare 0 / None / '' / a single-digit is never blanked — those
            are legit values a real fill or an honest blank produces). CHROME WALL [metadata-stripping root cause,
            run r_627ae7b326]: a CHROME/STRUCTURAL leaf is SUPPOSED to equal the card's template default — CLASS 4
            polices only DATA leaves. Exempt: (a) a STRING leaf whose key (or its container's key) is in the
            chrome-string vocab (title/label/name/unit/prefix/suffix/legend/axis-label/tab/id/key/kind/color —
            fab_guards.chrome_string_keys, last-word matched so metricId/axisKey/xAxisLabel/railLabels qualify);
            (b) an axis/scale ARRAY (yLabels/yTicks/ticks/labels — the same vocab on a scalar list); (c) the existing
            structural-chrome + selector-key exemptions. The wall NEVER covers a leaf inside a LIST ELEMENT (a
            per-record narrative title/why/severity stays policed) and never a numeric reading — the card-73
            legendValue [52,71,85,43] numeric seed still blanks.

Every threshold is a DB knob (config.app_config, section 'fab_guards') with a code default — no magic literals baked
here. Never raises; a guard that cannot decide leaves the leaf untouched (never an over-reach blank). [atomic]
"""

# ── package layout (atomic rule: one guard class per module) ─────────────────────────────────────────────────────────
#   knobs.py            DB valves + epoch floor + time-axis vocab + gap helpers
#   class1_epoch.py     CLASS 1 epoch-millis scan
#   class23_source.py   CLASS 2/3 per-written-field source audit (+ _ROWS_CACHE, the one dict)
#   class4_seed.py      CLASS 4 seed-leak wall + the chrome vocabulary
#   restore.py          restore_chrome — the EARLY chrome-restoration pass
#   apply.py            apply() — the ONE post-fill entry (fill.py)
# This __init__ re-exports the original module surface byte-compatibly; _ROWS_CACHE is the SAME dict object
# class23_source owns (tests .clear() it — never rebind it).
from ems_exec.executor.fab_guards.knobs import (                        # noqa: F401
    _epoch_floor, _guard_on, _time_axis_suffixes, _time_axis_exact, _is_time_axis_key, _reason, _add_gap, _is_num)
from ems_exec.executor.fab_guards.class1_epoch import _is_epoch_scalar, _is_epoch_array, _apply_class1   # noqa: F401
from ems_exec.executor.fab_guards.class23_source import (               # noqa: F401
    _ROWS_CACHE, _table_has_rows, _field_leaf_path, _field_has_source, _apply_class2_class3, _blank_numeric_leaf)
from ems_exec.executor.fab_guards.class4_seed import (                  # noqa: F401
    _written_toks, _is_written, _trivial_scalar, _structural_chrome_keys, _chrome_selector_keys,
    _chrome_string_keys, _key_words, _is_chrome_key, _is_chrome_leaf, _is_config_object_series,
    _seed_worth_policing, _is_numeric_data_seed, _is_chrome_leaf_key, _data_value_keys, _is_data_value_key,
    _blank_seed, _embeds_data_magnitude, _strip_stale_magnitude, _apply_class4_seed_leak)
from ems_exec.executor.fab_guards.restore import (                      # noqa: F401
    _scale_selector_keys, _scale_selector_key, _chrome_is_blank, restore_chrome)
from ems_exec.executor.fab_guards.apply import apply                    # noqa: F401
