# Payload DB — `cmd_catalog.card_payloads`

> Built 2026-06-29 on the directive: *"first make a proper db with the payload for all the cards and subcards. the payloads you can find in http://100.90.185.31:6008/."*
> That URL = the running **CMD_V2 Storybook**. Each story's **resolved args = that card/subcard's default payload** — the ground truth Layer 2 morphs and byte-matches against.

## What it is
One row per Storybook story = one **card or subcard default payload** (the exact `args` the React component receives), stored as `jsonb`, linked to its `cmd_catalog` card, with each payload key classified **DATA-fill vs METADATA-morph**.

## Coverage (verified)
- **125 rows** total · **59 EMS** = **36 cards + 23 subcards** across all **9 available pages** · 66 non-EMS (nav atoms / 3D Mapper) for reference.
- `jsonb` round-trips **byte-equal** to the harvest (125/125). `card_id` mapped + adversarially verified (59/59, 0 dangling).

## Columns
| column | meaning |
|---|---|
| `story_id` (PK) | storybook story id |
| `title` / `story_name` | full title path / export display name |
| `story_group` | EMS \| nav \| 3D Mapper |
| `shell` / `page` / `card_group` | Panel Overview\|Equipment Detail / page / Cards\|Sub-Cards\|Rail Cards\|… |
| `is_subcard` | card_group contains "sub" |
| `page_key` | mapped `cmd_catalog` page_key (e.g. `panel-overview-shell/voltage-current`) |
| `variant` | the payload's `variant` discriminator |
| **`payload`** (jsonb) | **the card/subcard default payload** |
| `payload_keys` | top-level keys |
| `card_id` | → `cmd_catalog.cards.id` (verified) |
| `card_match_confidence` / `card_match_reason` | high\|medium\|low + why (incl. rival-card refutation) |
| `parent_story_id` | for subcards: the parent CARD story they belong to |
| `key_roles` (jsonb) | `{top_level_key: data \| metadata \| mixed}` |
| `match_verified` | passed adversarial verify |
| `match_notes` | per-LEAF data-vs-metadata breakdown (which leaves a worker fills vs the AI morphs) |

## The morph split (key insight for Layer 2)
Across 59 EMS payloads: **70 metadata · 60 mixed · 1 pure-data** top-level keys. Most content objects (`data`, `health`, `history`, `snapshot`, `row`…) are **mixed** — they carry BOTH design metadata (titles, labels, units, thresholds, colors, axis config the AI morphs) AND live readings (per-phase values, KPI numbers, series points the worker fills). So the morph is **per-leaf, not per-top-level-key**. `match_notes` records the exact leaf split per payload. `variant` is always metadata (the design discriminator).

## How it was built (atomic, `payload_db/`)
1. `harvest_payloads.mjs` — Playwright reads `__STORYBOOK_PREVIEW__.storyStoreValue.args.initialArgsByStoryId[id]` per story → `/tmp/ems_payloads.json`. **Run from `/home/rohith/CMD_V2`** (playwright lives there).
2. `page_map.py` — Storybook (shell, page) → `page_key`.
3. `schema.sql` + `load_payloads.py` — create + psycopg2 upsert (idempotent on story_id).
4. `verify.py` — counts + jsonb byte-faithfulness → PASS.
5. `enrich/` — the `enrich-payload-db` workflow (9 pages × map→adversarial-verify) → `mappings.json`; `write_enrichment.py` writes `card_id`/`key_roles`/notes back. Inputs/outputs snapshotted in `enrich/`.

## Re-run
```
node /home/rohith/CMD_V2/_harvest_payloads.mjs           # from CMD_V2; refresh /tmp/ems_payloads.json
PYTHONPATH=. python3 payload_db/load_payloads.py         # upsert
PYTHONPATH=. python3 payload_db/verify.py                # faithfulness PASS
PYTHONPATH=. python3 payload_db/enrich/write_enrichment.py   # re-apply mappings.json
```

## Query examples
```sql
-- the RTM heatmap card's default payload (the Layer-2 byte-match target)
SELECT payload FROM card_payloads
WHERE page_key='panel-overview-shell/real-time-monitoring' AND story_name='Main Heatmap Card';

-- a card + its subcards, with morph roles
SELECT story_name, is_subcard, card_id, key_roles
FROM card_payloads WHERE card_id=42 ORDER BY is_subcard;
```
