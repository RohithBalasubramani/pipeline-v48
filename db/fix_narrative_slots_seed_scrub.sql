-- db/fix_narrative_slots_seed_scrub.sql — extend the narrative-slot scrub list (db-data hardening, 2026-07-03).
-- Idempotent (full-value SET on conflict). Run:
--   psql -U postgres -h 127.0.0.1 -p 5432 -d cmd_catalog -f db/fix_narrative_slots_seed_scrub.sql
--   then REBUILD: scripts/build_stripped_payloads.py (payload_stripped is derived from this policy).
--
-- DEFECT (adversarial batches 4/5/6): grounding.default_assemble.strip_to_placeholders scrubs a metadata STRING leaf
-- only when its EXACT lowercased key is in narrative_slots. Several composite-key narrative leaves carry FABRICATED
-- metric text that survives the strip and leaks into the resting honest-blank payload:
--   · why              chart.events[].why  = "level 12% · 1.0hr" / "load 92%" (fabricated fuel/load event annotation, card 65/67)
--   · headroomCaption  lifeCapacity        = "8280kVA headroom"  (fabricated capacity, contradicts real rated_kva=2500, card 75)
--   · agingCaption     lifeCapacity        = "Aging: 1.0x"        (fabricated aging factor, card 75)
--   · lifeNote         aging.kpis          = "20.5 / 25 yr left"  (fabricated remaining-life, card 77)
--   · aiSummaryText    ai summary          = "UPS-06 leads at 244 kW (40% load)…" (fabricated fleet narrative)
-- VERIFIED (2026-07-03) across all 155 card_payloads: EVERY distinct value at each of these keys is fabricated
-- narrative — none is static chrome — so adding them to the exact-key scrub list is safe (checked value-by-value).
-- NOT added (mixed chrome, would corrupt real labels): `source` (overwhelmingly sankey topology node ids), `note`
-- (phase-pair labels "(B-Y)"), `caption` (already in list; the composite feederOutputCaption/sourceInputCaption are
-- static section labels left intact by design).
INSERT INTO data_quality_policy (key, num_value, txt_value, note) VALUES
 ('narrative_slots', NULL,
  'insight,text,summary,note,caption,subtitle,likelysource,nextpriority,trendlabel,message,headline,description,'
  'detail,commentary,aisummary,aisummarytext,why,headroomcaption,agingcaption,lifenote',
  'metadata string slots that embed a fabricated metric -> scrubbed to placeholder.narrative in '
  'strip_to_placeholders [VC-02, META-01]. Extended 2026-07-03: aisummarytext,why,headroomcaption,agingcaption,'
  'lifenote (composite narrative keys leaking fabricated capacity/aging/life/event text).')
ON CONFLICT (key) DO UPDATE SET num_value = EXCLUDED.num_value, txt_value = EXCLUDED.txt_value, note = EXCLUDED.note;
