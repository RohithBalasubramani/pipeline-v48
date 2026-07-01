export const meta = {
  name: 'enrich-payload-db',
  description: 'Map each Storybook card/subcard payload to its cmd_catalog card_id + classify each payload key as DATA-fill vs METADATA-morph, adversarially verified',
  phases: [
    { title: 'Map+Classify', detail: 'per page: story→card_id + key DATA/METADATA roles' },
    { title: 'Verify', detail: 'adversarial refute of weak card mappings + key roles' },
  ],
}

const A = typeof args === 'string' ? JSON.parse(args) : args
const PAGES = A.page_keys
const BUNDLE = A.bundle_path

const MAP_SCHEMA = {
  type: 'object',
  required: ['page_key', 'mappings'],
  properties: {
    page_key: { type: 'string' },
    mappings: {
      type: 'array',
      items: {
        type: 'object',
        required: ['story_id', 'card_id', 'card_match_confidence', 'card_match_reason', 'is_subcard', 'key_roles'],
        properties: {
          story_id: { type: 'string' },
          card_id: { type: ['integer', 'null'] },
          card_match_confidence: { type: 'string', enum: ['high', 'medium', 'low', 'none'] },
          card_match_reason: { type: 'string' },
          is_subcard: { type: 'boolean' },
          parent_story_id: { type: ['string', 'null'] },
          variant: { type: ['string', 'null'] },
          key_roles: { type: 'object', additionalProperties: { type: 'string', enum: ['data', 'metadata', 'mixed'] } },
          notes: { type: 'string' },
        },
      },
    },
  },
}

const VERIFY_SCHEMA = {
  type: 'object',
  required: ['page_key', 'mappings', 'changes'],
  properties: {
    page_key: { type: 'string' },
    changes: { type: 'array', items: { type: 'string' } },
    mappings: {
      type: 'array',
      items: {
        type: 'object',
        required: ['story_id', 'card_id', 'card_match_confidence', 'is_subcard', 'key_roles', 'verified'],
        properties: {
          story_id: { type: 'string' },
          card_id: { type: ['integer', 'null'] },
          card_match_confidence: { type: 'string', enum: ['high', 'medium', 'low', 'none'] },
          card_match_reason: { type: 'string' },
          is_subcard: { type: 'boolean' },
          parent_story_id: { type: ['string', 'null'] },
          variant: { type: ['string', 'null'] },
          key_roles: { type: 'object', additionalProperties: { type: 'string', enum: ['data', 'metadata', 'mixed'] } },
          verified: { type: 'boolean' },
          notes: { type: 'string' },
        },
      },
    },
  },
}

const MORPH_RULE = `KEY ROLE classification (payload-morph model — the CMD_V2 §B4 split):
- METADATA = what the design AI MORPHS and is fixed by the card's design: variant discriminator, titles/labels/captions, units, axis/scale config, thresholds/bands/ranges, color/theme/icon keys, formatting, option flags, column headers, legend text, layout/chrome.
- DATA = the measured values a backend WORKER fills from the live EMS feed: series points, current/voltage/power readings, history arrays, KPI numbers, status/state values, timestamps, per-phase values, computed stats.
- mixed = a top-level key whose object holds BOTH (e.g. a 'data' object with both labels and readings) — mark 'mixed' and explain in notes.
Classify EVERY top-level key in payload_keys.`

const results = await pipeline(
  PAGES,
  // STAGE 1 — map + classify
  (pk) => agent(
`You map Storybook card/subcard PAYLOADS to their cmd_catalog card row, and classify each payload's keys.

Read ${BUNDLE} (JSON). Use:
- pages[${JSON.stringify(pk)}].payloads  — the cards/subcards on this page (story_id, story_name, card_group, is_subcard, variant, payload_keys, payload_preview).
- pages[${JSON.stringify(pk)}].layout_anchors — HIGH-CONFIDENCE card_id anchors for this page (card_id, card_title, tab, region). Prefer these.
- cards_catalog — ALL 145 cmd_catalog cards (card_id, title, page_label, visualization, purpose). Map to any of these when no anchor fits.

For EACH payload return one mapping:
- card_id: the cmd_catalog card it renders. Prefer a layout_anchor; else best semantic match from cards_catalog (match by story_name vs card title/purpose/visualization). null if genuinely no card matches.
- card_match_confidence: high (anchor or exact title) / medium (clear semantic) / low (guess) / none (null).
- card_match_reason: one line.
- is_subcard + parent_story_id: subcards (card_group contains 'Sub') are sub-components of a parent CARD payload on the SAME page — set parent_story_id to that card's story_id when inferable, and card_id to the PARENT card's cmd_catalog id (subcards share the parent's card row).
- variant: echo payload.variant.
- key_roles: classify EVERY top-level key.

${MORPH_RULE}

Return JSON {page_key, mappings:[...]}. Be exhaustive — one mapping per payload, none skipped.`,
    { label: `map:${pk.split('/')[1]}`, phase: 'Map+Classify', schema: MAP_SCHEMA }
  ),
  // STAGE 2 — adversarial verify
  (mapped, pk) => agent(
`You ADVERSARIALLY verify card-payload mappings. Default to skeptical: a mapping survives only if defensible.

Read ${BUNDLE}. Focus pages[${JSON.stringify(pk)}] + cards_catalog.

STAGE-1 RESULT to scrutinize:
${JSON.stringify(mapped, null, 1)}

For EACH mapping, try to REFUTE:
- Is card_id really the card this payload renders? A high title-overlap with the WRONG card (wrong metric/role/tab) is a WRONG match — downgrade to null/low and say why.
- Is the confidence honest? Downgrade overconfident guesses.
- For subcards: is parent_story_id / inherited card_id correct?
- Are the key_roles correct per the morph rule below? Fix any DATA mislabeled as METADATA or vice-versa.

${MORPH_RULE}

Return JSON {page_key, mappings:[...with 'verified' bool each...], changes:[short strings describing every override you made]}. Keep all payloads; never drop one.`,
    { label: `verify:${pk.split('/')[1]}`, phase: 'Verify', schema: VERIFY_SCHEMA }
  )
)

const ok = results.filter(Boolean)
const allMappings = ok.flatMap(r => r.mappings)
const changes = ok.flatMap(r => (r.changes || []).map(c => `[${r.page_key}] ${c}`))
return {
  pages_done: ok.length,
  total_mappings: allMappings.length,
  mapped_card: allMappings.filter(m => m.card_id != null).length,
  unmapped: allMappings.filter(m => m.card_id == null).map(m => m.story_id),
  changes,
  mappings: allMappings,
}