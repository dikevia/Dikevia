-- V3.30 hardening: privileged platform operations use a dedicated DB login.
-- Apply only after cfdt_juris_platform_admin has been created by deploy/init/04-create-platform-admin-role.sh.
BEGIN;
DO $
DECLARE admin_role_oid oid;
BEGIN
  SELECT oid INTO admin_role_oid FROM pg_roles
   WHERE rolname='cfdt_juris_platform_admin' AND rolcanlogin
     AND NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole
     AND NOT rolbypassrls AND NOT rolinherit AND NOT rolreplication;
  IF admin_role_oid IS NULL THEN
    RAISE EXCEPTION 'Dedicated least-privilege role cfdt_juris_platform_admin is missing or unsafe';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_auth_members WHERE member=admin_role_oid) THEN
    RAISE EXCEPTION 'Platform-admin DB role must not inherit or be able to SET ROLE into another role';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_shdepend WHERE refclassid='pg_authid'::regclass
      AND refobjid=admin_role_oid AND deptype='o') THEN
    RAISE EXCEPTION 'Platform-admin DB role must not own database objects';
  END IF;
END $;

-- Remove any accidental pre-existing direct table grants before applying the allowlist.
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM cfdt_juris_platform_admin;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM cfdt_juris_platform_admin;

REVOKE EXECUTE ON FUNCTION platform_admin_list_organizations(uuid) FROM cfdt_juris_app;
REVOKE EXECUTE ON FUNCTION platform_admin_set_organization_status(uuid,uuid,text) FROM cfdt_juris_app;
REVOKE EXECUTE ON FUNCTION platform_admin_commercial_summary(uuid,date) FROM cfdt_juris_app;
REVOKE EXECUTE ON FUNCTION platform_admin_commercial_invoices(uuid,integer) FROM cfdt_juris_app;
REVOKE EXECUTE ON FUNCTION platform_admin_organization_seat_counts(uuid,uuid) FROM cfdt_juris_app;
REVOKE EXECUTE ON FUNCTION private_instance_pending_members(uuid) FROM cfdt_juris_app;
REVOKE EXECUTE ON FUNCTION private_instance_set_member_status(uuid,uuid,uuid,text) FROM cfdt_juris_app;

GRANT EXECUTE ON FUNCTION platform_admin_list_organizations(uuid) TO cfdt_juris_platform_admin;
GRANT EXECUTE ON FUNCTION platform_admin_set_organization_status(uuid,uuid,text) TO cfdt_juris_platform_admin;
GRANT EXECUTE ON FUNCTION platform_admin_commercial_summary(uuid,date) TO cfdt_juris_platform_admin;
GRANT EXECUTE ON FUNCTION platform_admin_commercial_invoices(uuid,integer) TO cfdt_juris_platform_admin;
GRANT EXECUTE ON FUNCTION platform_admin_organization_seat_counts(uuid,uuid) TO cfdt_juris_platform_admin;
GRANT EXECUTE ON FUNCTION private_instance_pending_members(uuid) TO cfdt_juris_platform_admin;
GRANT EXECUTE ON FUNCTION private_instance_set_member_status(uuid,uuid,uuid,text) TO cfdt_juris_platform_admin;

-- Platform allowlist writes and its audit trail are also isolated from the API role.
REVOKE INSERT, UPDATE ON platform_free_email_access FROM cfdt_juris_app;
REVOKE INSERT ON platform_audit_events FROM cfdt_juris_app;
GRANT SELECT, INSERT, UPDATE ON platform_free_email_access TO cfdt_juris_platform_admin;
GRANT INSERT ON platform_audit_events TO cfdt_juris_platform_admin;
COMMIT;
