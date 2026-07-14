-- db/seed_resolver_alias_reprompt.sql — T2.3-2 [AI-first, deterministic_audit_20260714 L1B-2]: DEFAULT OFF.
--
-- resolver.alias_reprompt — read by layer1b/resolve/asset_resolve.py (_alias_reprompt_on): _alias_rescue is the ONE
-- place deterministic code REWRITES the model's answer (an all-panel-ambiguous outcome whose spelled aliases uniquely
-- name ONE panel -> a confident pin). When ON, instead of silently substituting, it RE-ASKS the model once with the
-- pcc_panel_alias dictionary fact appended ('these aliases ALL name PCC-Panel-1, its bus sections') so the MODEL owns
-- the pin (how='alias-fact-ai'); a re-answer that does not confirm the panel falls to the existing deterministic pin
-- (how='alias-dictionary', the reproducibility floor). One extra resolver call ONLY on this rare path.
-- When OFF (this default) the deterministic pin stands, byte-identical.
--
-- ON CONFLICT DO NOTHING (not UPDATE): re-running this seed must never flip an operator's 'on' back to 'off'.

INSERT INTO app_config (key, value, data_type, section, note) VALUES
 ('resolver.alias_reprompt', 'off', 'text', 'resolver',
  'T2.3-2 AI-first: on = _alias_rescue re-asks the model with the pcc_panel_alias dictionary fact instead of silently substituting (how=alias-fact-ai; deterministic pin is the fallback floor); off = byte-identical deterministic pin (layer1b/resolve/asset_resolve.py)')
ON CONFLICT (key) DO NOTHING;
