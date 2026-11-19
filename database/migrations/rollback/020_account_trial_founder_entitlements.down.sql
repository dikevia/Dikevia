-- Roll back account trial metadata and individual founder entitlements.
-- This intentionally removes trial history and entitlement assignments; export/audit first.
BEGIN;
DROP FUNCTION IF EXISTS platform_admin_list_founder_entitlements(uuid);
DROP FUNCTION IF EXISTS platform_admin_revoke_founder_entitlement(uuid,smallint,text);
DROP FUNCTION IF EXISTS platform_admin_grant_founder_entitlement(uuid,smallint,uuid,text);
DROP TABLE IF EXISTS founder_entitlements;
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_trial_window_check;
ALTER TABLE users DROP COLUMN IF EXISTS trial_expires_at;
ALTER TABLE users DROP COLUMN IF EXISTS trial_started_at;
ALTER TABLE users DROP COLUMN IF EXISTS email_verified_at;
COMMIT;
