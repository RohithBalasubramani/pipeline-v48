-- db/fix_cards_profile_81_74.sql — cards profile-row accuracy repairs on the ROUTABLE surface (db-data hardening,
-- 2026-07-03). Idempotent keyed UPDATEs; safe to re-run.
--
-- CARD 81 (transformer-asset-dashboard/tap-rtcc, ROUTABLE): the whole cards profile described a DIFFERENT card
-- ('Loss Analysis' — copper/core/stray loss decomposition, TapPositionGauge). Ground truth per card_handling +
-- card_data_recipe + card_payloads: the card is 'Tap Activity & Wear' (TapActivityCard/ChartBars — hourly
-- tap_changer_operations_count bars + cumulative line, Total/Peak-hour/Average KPIs, contact-life FillBar verdict vs
-- tap_contact_life_max, AI wear narrative). 1a's page-cards line and L2's card profile both read THIS row, so the
-- wrong prose misroutes loss-analysis prompts and mis-primes L2. Re-authored from the real component:
UPDATE cards SET
  title = 'Tap Activity & Wear',
  primary_component = 'ChartBars',
  card_purpose = 'Counts the transformer''s OLTC tap-changer operations through the day (hourly bars plus a cumulative lifetime counter), derives peak-hour and average activity, and converts the running total into a contact-life-remaining wear verdict against the tap contact''s rated operations.',
  user_question = 'How often is this transformer''s tap changer operating, when does the activity peak, and how much tap contact life remains?',
  inputs = 'Hourly tap_changer_operations_count series for the selected transformer (24 today-buckets plus the cumulative lifetime counter); derived peak-hour and average-operations KPIs; the tap_contact_life_max rated-operations constant; user-selected time mode and Hourly/Daily sampling (display-only picker).',
  output_insight = 'A ChartBars timeline of hourly tap operations with a cumulative right-axis line, Total / Peak-hour / Average KPI tiles, a FillBar contact-life-remaining verdict (''/5 million left''), and an AI wear narrative covering the peak hour, today''s total and the wear percentage.',
  decision_support = 'Flags abnormal tap hunting (excessive operation counts or peak-hour clustering) for voltage-regulation investigation, and tracks contact wear so maintenance can schedule OLTC inspection or refurbishment before the contact life runs out.',
  relationship_to_page = 'The Tap/RTCC tab of the transformer detail view — the tap-changer activity and wear lens, beside Tap Position Optimization, the Voltage Regulation Timeline and Recent Tap Changes.',
  visualization = 'Hourly bar chart (24 today-buckets) with a cumulative-total line on a dual axis, crosshair tooltip and interactive today/total legend rail; KPI row (total / peak hour / average); contact-life FillBar verdict; AI summary line.',
  sem_card_name = 'Tap Activity & Wear',
  sem_purpose = 'Track tap-changer operation counts and derive contact-wear / contact-life-remaining verdicts',
  sem_answers = 'How many tap operations occurred, when activity peaked, and how much tap contact life remains'
WHERE id = 81 AND title = 'Loss Analysis';

-- CARD 74 (transformer-asset-dashboard/thermal-life, ROUTABLE): cosmetic title drift — the harvested payload's own
-- title leaf is 'Thermal Life' (card_payloads /thermalLife/title), matching card_handling. Align cards.title.
UPDATE cards SET title = 'Thermal Life', sem_card_name = 'Thermal Life'
 WHERE id = 74 AND title = 'Thermal & Life';

-- NOT TOUCHED (deliberate): cards 82 / 100 / 101 / 102 / 105 / 107 / 113 also show cards-vs-card_handling title
-- drift, but all sit on NON-ROUTABLE BMS/legacy pages, their two titles differ in phrasing more than substance, and
-- re-authoring their profile prose needs the same per-card evidence pass as card 81 — deferred (finding 6 explicitly
-- ranks them lower priority; nothing on the 18-page acceptance surface reads them).
