-- BT-035: retained evidence for permanent digital-asset purge outcomes.
ALTER TABLE digital_asset_trash_item ADD COLUMN purge_operation_uuid TEXT;
ALTER TABLE digital_asset_trash_item ADD COLUMN purged_at TEXT;
ALTER TABLE digital_asset_trash_item ADD COLUMN purged_by_token_uuid TEXT;
ALTER TABLE digital_asset_trash_item ADD COLUMN purge_photo_count INTEGER;
ALTER TABLE digital_asset_trash_item ADD COLUMN purge_byte_count INTEGER;
ALTER TABLE digital_asset_trash_item ADD COLUMN purge_inventory_digest TEXT;
