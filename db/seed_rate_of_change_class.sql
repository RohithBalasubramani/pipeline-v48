-- db/seed_rate_of_change_class.sql — add the RATE-OF-CHANGE (percent-per-hour / trend-rate) quantity class to the
-- physical-quantity vocabulary (layer2/quantity_class.py). DEFECT 1, card 47 (pg09 power-quality):
--
--   snapshot.trendPctPerHour = 275.0  ← the emit bound {metric:current_avg, column:current_avg, kind:raw,
--   unit:'%/hour', label:'Trend Rate'} — a raw CURRENT column (amps) poured into a RATE-OF-CHANGE (%/hour) slot,
--   shown on-screen as a '+275 %/hour Trend Rate'. CURRENT is not a rate-of-change; the meter has no trend-rate
--   column, so a re-labelled amps magnitude is a cross-quantity fabrication → the quantity wall must honest-blank it.
--
-- FIX (DB vocab + code-default mirror in quantity_class.py): a rate-of-change / %-per-hour / trend-rate quantity gets
-- its OWN class 'rate-of-change', distinct from the raw magnitude AND from the bare occurrence 'rate' (a count-per-
-- hour). The class is anchored on:
--   • quantity.unit_classes — the '%/hour' family of units ('%/hr','%/h','pct/hour','pctperhour',…). Keeps the '%' so
--     it never collides with the bare '/hr'/'ops/hr' OCCURRENCE-rate keys already in the row.
--   • quantity.name_classes — PAIR tokens only: 'pct'+'per' = pctper (as in trendPctPerHour / …PctPerHr), 'trend'+
--     'rate', 'rate'+'pct'/'percent'. PAIR-only is deliberate: a bare 'trend'/'rate'/'per'/'hour' token must NOT
--     classify, so a COUNT-per-hour ('tapChangesPerHour'→count) / ENERGY-per-hour ('kwhPerHour'→energy) slot keeps
--     its own leading quantity token (leaf-most-first) and is NEVER re-classed rate-of-change (corpus-verified).
--
-- Then compatible('rate-of-change', <current|voltage|power|energy>) is False (both classified, different, neither
-- weak) → gates.enforce_honest_blank drops the current_avg field → the leaf honest-blanks. A GENUINE %/hour rate
-- (fn thdTrendRatePctPerHour → tokens thd/trend/rate/pct/per/hour → the 'pctper' pair → rate-of-change) is
-- compatible with the slot and still fills.
--
-- MERGE-only (jsonb ||), so it adds the new keys to the existing quantity.unit_classes / quantity.name_classes rows
-- WITHOUT touching any other key (no accidental drift catch-up). Idempotent (re-merging the same keys is a no-op).
-- Code default in layer2/quantity_class.py behaves identically until this row is edited.
-- Run: psql (cmd_catalog DSN per config/databases.py) -f db/seed_rate_of_change_class.sql

UPDATE app_config
   SET value = ((value::jsonb) || '{
          "%/hour":"rate-of-change","%/hr":"rate-of-change","%/h":"rate-of-change",
          "pct/hour":"rate-of-change","pct/hr":"rate-of-change","pctperhour":"rate-of-change",
          "pctperhr":"rate-of-change","%perhour":"rate-of-change","%perhr":"rate-of-change"
       }'::jsonb)::text,
       updated_at = now()
 WHERE key = 'quantity.unit_classes';

UPDATE app_config
   SET value = ((value::jsonb) || '{
          "pctper":"rate-of-change","trendrate":"rate-of-change",
          "ratepct":"rate-of-change","ratepercent":"rate-of-change"
       }'::jsonb)::text,
       updated_at = now()
 WHERE key = 'quantity.name_classes';
