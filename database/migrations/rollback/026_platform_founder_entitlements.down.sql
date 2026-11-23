BEGIN;
DROP FUNCTION IF EXISTS platform_admin_list_founder_entitlements(uuid);
DROP FUNCTION IF EXISTS platform_admin_revoke_founder_entitlement(uuid,uuid);
DROP FUNCTION IF EXISTS platform_admin_grant_founder_entitlement(uuid,uuid,text);
DROP TABLE IF EXISTS platform_founder_entitlements;
COMMIT;
