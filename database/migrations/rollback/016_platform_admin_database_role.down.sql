-- Roll back only the privilege split; restore the V3.30 pre-hardening grants.
BEGIN;
GRANT EXECUTE ON FUNCTION platform_admin_create_organization(uuid,uuid,text,text,text,boolean) TO cfdt_juris_app;
GRANT EXECUTE ON FUNCTION platform_admin_grant_free_access(uuid,uuid,text) TO cfdt_juris_app;
GRANT EXECUTE ON FUNCTION platform_admin_list_organizations(uuid) TO cfdt_juris_app;
GRANT EXECUTE ON FUNCTION platform_admin_set_organization_status(uuid,uuid,text) TO cfdt_juris_app;
GRANT EXECUTE ON FUNCTION platform_admin_commercial_summary(uuid,date) TO cfdt_juris_app;
GRANT EXECUTE ON FUNCTION platform_admin_commercial_invoices(uuid,integer) TO cfdt_juris_app;
GRANT EXECUTE ON FUNCTION platform_admin_organization_seat_counts(uuid,uuid) TO cfdt_juris_app;
GRANT EXECUTE ON FUNCTION private_instance_pending_members(uuid) TO cfdt_juris_app;
GRANT EXECUTE ON FUNCTION private_instance_set_member_status(uuid,uuid,uuid,text) TO cfdt_juris_app;
GRANT INSERT, UPDATE ON platform_free_email_access TO cfdt_juris_app;
GRANT INSERT ON platform_audit_events TO cfdt_juris_app;
-- Keep the dedicated role's grants so the updated API remains operational after rollback.
COMMIT;
