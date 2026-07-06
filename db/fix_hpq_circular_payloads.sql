-- db/fix_hpq_circular_payloads.sql — resolve the '[Circular]' harvest artifacts in the harmonics-pq default
-- payloads (card_payloads cards 23 + 25). The Storybook harvest serializer lost REPEATED object references:
-- stats.worst / stats.worstIThd / stats.worstVThd / selectedPanel are references INTO period.panels
-- (CMD_V2 viewModel.periodStats + defaultPanelIdForFocus), stored as the literal string "[Circular]" — which
-- would render verbatim if a component reads those leaves. This re-derives each leaf from data already in the
-- SAME row, exactly as CMD_V2 harmonics-pq/viewModel.ts does:
--   worstIThd = argmax(panels.iThd);  worstVThd = argmax(panels.vThd);
--   worst     = argmax(pqScore), pqScore = iThd*7 + vThd*5 + kFactor*3 + pfGap*8 + neutralA*0.18;
--   selectedPanel (focus=iThd) = first panel ordered by iThd desc above the limit (== worstIThd here).
-- Idempotent: each leaf is replaced ONLY while it is still the literal "[Circular]".

-- card 23 (issue-summary-strip): the strip payload carries no roster, but worst == the worstIThd object
-- already inline in the same stats (ups-05 is both max-iThd and max-pqScore in the harvested fixture).
UPDATE card_payloads
SET payload = jsonb_set(payload, '{strip,stats,worst}', payload#>'{strip,stats,worstIThd}')
WHERE card_id = 23 AND is_subcard = false
  AND payload#>'{strip,stats,worst}' = '"[Circular]"'::jsonb
  AND jsonb_typeof(payload#>'{strip,stats,worstIThd}') = 'object';

-- card 25 (ai-summary-card): resolve all four leaves from summary.period.panels in the same row.
WITH p AS (
  SELECT story_id,
    (SELECT e FROM jsonb_array_elements(payload#>'{summary,period,panels}') e
      ORDER BY (e->>'iThd')::numeric DESC LIMIT 1) AS worst_ithd,
    (SELECT e FROM jsonb_array_elements(payload#>'{summary,period,panels}') e
      ORDER BY (e->>'vThd')::numeric DESC LIMIT 1) AS worst_vthd,
    (SELECT e FROM jsonb_array_elements(payload#>'{summary,period,panels}') e
      ORDER BY ((e->>'iThd')::numeric*7 + (e->>'vThd')::numeric*5 + (e->>'kFactor')::numeric*3
               + (e->>'pfGap')::numeric*8 + (e->>'neutralA')::numeric*0.18) DESC LIMIT 1) AS worst
  FROM card_payloads WHERE card_id = 25 AND is_subcard = false
)
UPDATE card_payloads c
SET payload = jsonb_set(jsonb_set(jsonb_set(jsonb_set(c.payload,
      '{summary,stats,worstIThd}',
        CASE WHEN c.payload#>'{summary,stats,worstIThd}' = '"[Circular]"'::jsonb THEN p.worst_ithd
             ELSE c.payload#>'{summary,stats,worstIThd}' END),
      '{summary,stats,worstVThd}',
        CASE WHEN c.payload#>'{summary,stats,worstVThd}' = '"[Circular]"'::jsonb THEN p.worst_vthd
             ELSE c.payload#>'{summary,stats,worstVThd}' END),
      '{summary,stats,worst}',
        CASE WHEN c.payload#>'{summary,stats,worst}' = '"[Circular]"'::jsonb THEN p.worst
             ELSE c.payload#>'{summary,stats,worst}' END),
      '{summary,selectedPanel}',
        CASE WHEN c.payload#>'{summary,selectedPanel}' = '"[Circular]"'::jsonb THEN p.worst_ithd
             ELSE c.payload#>'{summary,selectedPanel}' END)
FROM p
WHERE c.card_id = 25 AND c.is_subcard = false AND c.story_id = p.story_id
  AND p.worst_ithd IS NOT NULL;

-- card 19 (voltage-current ai-summary): same artifact class. CMD_V2 voltage-current/viewModel.periodStats:
--   worstVoltage = argmax |vDeviation|; worstCurrent = argmax iUnbalance;
--   selectedPanel = selectedPeriod.panels[0] (the story fixture picks the FIRST roster panel).
WITH p AS (
  SELECT story_id,
    (SELECT e FROM jsonb_array_elements(payload#>'{summary,period,panels}') e
      ORDER BY abs((e->>'vDeviation')::numeric) DESC LIMIT 1) AS worst_v,
    (SELECT e FROM jsonb_array_elements(payload#>'{summary,period,panels}') e
      ORDER BY (e->>'iUnbalance')::numeric DESC LIMIT 1) AS worst_i,
    payload#>'{summary,period,panels,0}' AS first_panel
  FROM card_payloads WHERE card_id = 19 AND is_subcard = false
)
UPDATE card_payloads c
SET payload = jsonb_set(jsonb_set(jsonb_set(c.payload,
      '{summary,stats,worstVoltage}',
        CASE WHEN c.payload#>'{summary,stats,worstVoltage}' = '"[Circular]"'::jsonb THEN p.worst_v
             ELSE c.payload#>'{summary,stats,worstVoltage}' END),
      '{summary,stats,worstCurrent}',
        CASE WHEN c.payload#>'{summary,stats,worstCurrent}' = '"[Circular]"'::jsonb THEN p.worst_i
             ELSE c.payload#>'{summary,stats,worstCurrent}' END),
      '{summary,selectedPanel}',
        CASE WHEN c.payload#>'{summary,selectedPanel}' = '"[Circular]"'::jsonb THEN p.first_panel
             ELSE c.payload#>'{summary,selectedPanel}' END)
FROM p
WHERE c.card_id = 19 AND c.is_subcard = false AND c.story_id = p.story_id
  AND p.worst_v IS NOT NULL;

-- card 49 (equipment-detail load-impact): views share ONE xLabels/xLabelIndexes array object; the harvest kept
-- the first view's ('pf-health') and collapsed the repeats ('k-stress', 'pf-angle') to "[Circular]". Copy the
-- surviving arrays into every view whose leaf is still the literal marker.
UPDATE card_payloads
SET payload = jsonb_set(jsonb_set(payload,
      '{loadImpact,views,k-stress,xLabels}',
        CASE WHEN payload#>'{loadImpact,views,k-stress,xLabels}' = '"[Circular]"'::jsonb
             THEN payload#>'{loadImpact,views,pf-health,xLabels}'
             ELSE payload#>'{loadImpact,views,k-stress,xLabels}' END),
      '{loadImpact,views,k-stress,xLabelIndexes}',
        CASE WHEN payload#>'{loadImpact,views,k-stress,xLabelIndexes}' = '"[Circular]"'::jsonb
             THEN payload#>'{loadImpact,views,pf-health,xLabelIndexes}'
             ELSE payload#>'{loadImpact,views,k-stress,xLabelIndexes}' END)
WHERE card_id = 49 AND is_subcard = false
  AND jsonb_typeof(payload#>'{loadImpact,views,pf-health,xLabels}') = 'array';

UPDATE card_payloads
SET payload = jsonb_set(jsonb_set(payload,
      '{loadImpact,views,pf-angle,xLabels}',
        CASE WHEN payload#>'{loadImpact,views,pf-angle,xLabels}' = '"[Circular]"'::jsonb
             THEN payload#>'{loadImpact,views,pf-health,xLabels}'
             ELSE payload#>'{loadImpact,views,pf-angle,xLabels}' END),
      '{loadImpact,views,pf-angle,xLabelIndexes}',
        CASE WHEN payload#>'{loadImpact,views,pf-angle,xLabelIndexes}' = '"[Circular]"'::jsonb
             THEN payload#>'{loadImpact,views,pf-health,xLabelIndexes}'
             ELSE payload#>'{loadImpact,views,pf-angle,xLabelIndexes}' END)
WHERE card_id = 49 AND is_subcard = false
  AND jsonb_typeof(payload#>'{loadImpact,views,pf-health,xLabels}') = 'array';
