-- payload_db/schema.sql — card/subcard default payloads harvested from CMD_V2 Storybook (:6008).
-- One row per story = one card or subcard payload (the resolved args the component receives).
CREATE TABLE IF NOT EXISTS card_payloads (
    story_id       text PRIMARY KEY,                 -- storybook story id
    title          text NOT NULL,                    -- full storybook title path (EMS/shell/page/group)
    story_name     text NOT NULL,                    -- export display name
    story_group    text NOT NULL,                    -- EMS | nav | 3D Mapper
    shell          text,                             -- Panel Overview | Equipment Detail
    page           text,                             -- Energy & Power ...
    card_group     text,                             -- Cards | Sub-Cards | Rail Cards | Main Heatmap Card | Overview Rail
    is_subcard     boolean NOT NULL DEFAULT false,
    page_key       text,                             -- mapped cmd_catalog page_key (soft ref), null if non-EMS/unmapped
    variant        text,                             -- payload.variant discriminator
    payload        jsonb NOT NULL,                   -- the card/subcard default payload (resolved args)
    payload_keys   text[],                           -- top-level keys
    import_path    text,
    component_path text,
    card_id        integer,                          -- nullable link to cmd_catalog.cards.id (resolved in enrich phase)
    harvested_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS card_payloads_page_key_idx ON card_payloads(page_key);
CREATE INDEX IF NOT EXISTS card_payloads_group_idx   ON card_payloads(story_group);
CREATE INDEX IF NOT EXISTS card_payloads_variant_idx ON card_payloads(variant);
CREATE INDEX IF NOT EXISTS card_payloads_payload_gin ON card_payloads USING gin(payload);
