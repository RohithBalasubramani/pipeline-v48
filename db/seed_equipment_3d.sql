-- db/seed_equipment_3d.sql — stream D knobs: the equipment kit-preview 3D fallback (cmd_catalog.app_config).
-- Run:  psql -h 127.0.0.1 -p 5432 -U postgres -d cmd_catalog -f db/seed_equipment_3d.sql
--
-- BOTH rows ship the feature OFF/inert (cert freeze — the 5th resolve tier changes PAYLOAD content on bridged
-- assets, so it follows the staged flip: staging rows ON -> 18-page sweep + SSR gate -> live psql flip). Each row
-- doubles as the kill-switch. ON CONFLICT DO NOTHING: re-applying seeds NEVER flips an operator-tuned value.
--
--   equipment.kitpreview.enabled    — gate for the 5th tier in layer2/emit/metadata/asset_3d._resolve_object.
--                                     'off' (default) -> the tier never runs; object=null exactly as today.
--   equipment.kitpreview.media_base — BY CONTRACT a LOCAL filesystem directory: the dir the ems_backend serves as
--                                     /media/ (rsync the cmd_equipment media objects/*.glb into it — 39 referenced).
--                                     The tier DEFAULT-DENIES unless this resolves to a readable local directory
--                                     actually containing the model's glb_file: unset('') / a remote URL /
--                                     unreadable -> NO url ever ships (object stays null + gap cause
--                                     'glb_not_in_media_root'). The SERVED url is built separately by
--                                     config/asset3d_media.glb_url (the /media/ HTTP route), never this path.
INSERT INTO app_config (key, value, data_type, section, note) VALUES
  ('equipment.kitpreview.enabled', 'off', 'text', 'equipment',
   'Kill-switch for the 3D kit-preview fallback tier (layer2/emit/metadata/asset_3d tier 5 over the local equipment kitpreview_* tables). off = tier inert, object=null exactly as today. Flip only via the staged cert pass.'),
  ('equipment.kitpreview.media_base', '', 'text', 'equipment',
   'LOCAL filesystem directory (BY CONTRACT — never a URL) holding the kit-preview GLBs; the same dir the ems_backend serves as /media/. Empty/unreadable/remote -> DEFAULT-DENY: no 3D url ever ships (gap cause glb_not_in_media_root).')
ON CONFLICT (key) DO NOTHING;
