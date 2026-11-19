BEGIN;
DROP FUNCTION IF EXISTS platform_admin_revoke_founder_entitlement(uuid,uuid);
DROP FUNCTION IF EXISTS platform_admin_grant_founder_entitlement(uuid,text,text,text);
DROP TABLE IF EXISTS platform_founder_entitlements;
COMMIT;
