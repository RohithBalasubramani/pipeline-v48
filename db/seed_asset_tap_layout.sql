-- db/seed_asset_tap_layout.sql — link the 4th Transformer Tap & RTCC layout card to card_id 81 so it renders.
-- [atomic, DB-driven, idempotent, ADDITIVE-safe]
--
-- FINDING (not a missing INSERT): page_layout_cards ALREADY has 4 rows for 'transformer-asset-dashboard/tap-rtcc'
-- (slots 1-4), matching the 4 Storybook tap cards. Slots 1-3 link to cards 78/79/80; slot 4 ("Tap Activity & Wear",
-- ActivityTicks) exists but has card_id = NULL, and card 81 appears in NO layout row. So the 4th tap card does not
-- render only because it is UNLINKED — the fix is to set card_id = 81 on that existing slot, NOT to INSERT a 5th row
-- (a new row would duplicate the slot). Every other asset page already has all its layout rows linked; tap-rtcc was
-- the lone gap (1 of 4 unlinked).
--
-- Idempotent: matches the stable slot identity (page_key + slot_order + card_title) and sets card_id only where it is
-- still NULL / already 81; re-runnable with no effect once linked. Run:
--   psql -h localhost -p 5432 -d cmd_catalog -f db/seed_asset_tap_layout.sql

UPDATE page_layout_cards
   SET card_id = 81
 WHERE page_key   = 'transformer-asset-dashboard/tap-rtcc'
   AND slot_order = 4
   AND card_title = 'Tap Activity & Wear'
   AND (card_id IS NULL OR card_id = 81);
