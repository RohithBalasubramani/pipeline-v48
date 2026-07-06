-- db/stripped_payload_schema.sql — STORED STRIPPED PAYLOADS: pre-clean each card_payloads skeleton in the DB so the
-- AI context is a stored, inspectable row (payload_stripped) instead of a per-run transform. `payload` stays the RAW
-- byte-identical harvested truth (seed-leak sentinel, element templates, graft default_payload keep reading it).
-- payload_stripped = grounding.default_assemble.strip_to_placeholders(payload), built by
-- scripts/build_stripped_payloads.py (re-run it after editing payload or the strip policy rows).
ALTER TABLE card_payloads
    ADD COLUMN IF NOT EXISTS payload_stripped jsonb,
    ADD COLUMN IF NOT EXISTS stripped_at timestamptz;

COMMENT ON COLUMN card_payloads.payload_stripped IS
    'strip_to_placeholders(payload): data leaves -> typed placeholders (0/[]), narrative/clock strings scrubbed. '
    'Built by scripts/build_stripped_payloads.py — STALE after editing payload or the policy rows '
    '(app_config vocab.*, data_quality_policy placeholder/narrative/clock); re-run the builder.';
COMMENT ON COLUMN card_payloads.stripped_at IS
    'when payload_stripped was last built (scripts/build_stripped_payloads.py).';
