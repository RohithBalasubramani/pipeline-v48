-- db/seed_resolver_full_listing.sql — T0-7 [AI-first, deterministic_audit_20260714 L1B-3/pattern-05]: DEFAULT OFF.
--
-- resolver.full_listing — read by layer1b/resolve/asset_resolve.py (_full_listing_on): when ON, the 1b asset
-- resolver shows the model the FULL registry candidate list instead of the class_from_subject-narrowed subset.
-- The keyword class prior can MIS-narrow ('temperature in the transformer room' hides the non-Transformer rows the
-- model would pick correctly from a full list); the audit's challenge kept the prior ONLY as the class_mismatch
-- telemetry input + the class-narrowed empty-fallback picker — both preserved under this flag.
-- When OFF (this default) the resolver listing is BYTE-IDENTICAL to the legacy narrowed one.
--
-- ON CONFLICT DO NOTHING (not UPDATE): re-running this seed must never flip an operator's 'on' back to 'off'.
-- Idempotent. Run: psql (cmd_catalog DSN per config/databases.py) -f db/seed_resolver_full_listing.sql

INSERT INTO app_config (key, value, data_type, section, note) VALUES
 ('resolver.full_listing', 'off', 'text', 'resolver',
  'T0-7 AI-first: on = the 1b asset resolver sees the FULL registry listing (class prior kept for telemetry + the empty-fallback picker only); off = legacy class-narrowed listing, byte-identical (layer1b/resolve/asset_resolve.py)')
ON CONFLICT (key) DO NOTHING;
