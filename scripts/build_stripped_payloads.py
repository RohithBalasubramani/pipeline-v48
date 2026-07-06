"""scripts/build_stripped_payloads.py — build card_payloads.payload_stripped for EVERY row (stored stripped skeletons).

The stored column IS the AI-context skeleton: strip_to_placeholders(payload) — the canonical strip+scrub
(grounding.default_assemble: data leaves → typed placeholders 0/[], narrative/clock strings scrubbed) — persisted so
the skeleton is an inspectable DB row, not a per-run transform. Raw `payload` is NEVER touched. This is the ONE AND
ONLY runtime caller of strip_to_placeholders: readers now consume payload_stripped DIRECTLY (runtime stripping retired).

★ MUST BE RE-RUN after editing card_payloads.payload OR the strip policy rows:
    · app_config vocab.* rows
    · data_quality_policy placeholder rows (placeholder.scalar, placeholder.narrative)
    · data_quality_policy narrative_slots / scrub.clock_strings rows
  (payload_stripped is a DERIVED column — stale until this builder runs again.)

Idempotent: recomputes and UPDATEs every row each run (one transaction). A NULL payload_stripped now makes readers
FAIL LOUDLY (no on-the-fly fallback) — so this builder MUST have been run before Layer 2 emits.

Run:  PYTHONPATH=/home/rohith/desktop/BFI/backend/layer2/pipeline_v48 \
      /home/rohith/.pyenv/versions/3.11.9/bin/python3.11 scripts/build_stripped_payloads.py
"""
import json

from data.db_client import pg_connect
from grounding.default_assemble import strip_to_placeholders
from grounding.exemplar_reduce import reduce_repeated
from validate.leaf_classify import classify


def main():
    conn = pg_connect("cmd_catalog")
    built, leaves_total = 0, 0
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT story_id, payload FROM card_payloads ORDER BY story_id")
            rows = cur.fetchall()
            for story_id, payload in rows:
                stripped = strip_to_placeholders(payload)
                # EMIT-ONCE: collapse a large DATA-bearing repeated array (cards 5 heatmap.history / 24 timeline.periods)
                # to ONE exemplar so the AI copies one frame, not N — the executor rebuilds all N from real ems.
                # No-op for the other 153 cards (only a >threshold repeated array with a series leaf is reduced).
                stripped = reduce_repeated(stripped, payload)
                try:
                    leaves_total += len(classify(payload).get("data_leaves") or [])
                except Exception:
                    pass                                    # count is summary telemetry only — never blocks the build
                cur.execute(
                    "UPDATE card_payloads SET payload_stripped = %s::jsonb, stripped_at = now() "
                    "WHERE story_id = %s",
                    (json.dumps(stripped), story_id))
                built += 1
        conn.commit()
    finally:
        conn.close()
    print(f"build_stripped_payloads: rows built = {built}, data leaves stripped total = {leaves_total}")


if __name__ == "__main__":
    main()
