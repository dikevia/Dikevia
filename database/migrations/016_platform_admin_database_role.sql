-- V3.30 hardening: privileged platform operations use a dedicated DB login.
-- Apply only after cfdt_juris_platform_admin has been created by deploy/init/04-create-platform-admin-role.sh.
BEGIN;

CREATE OR REPLACE FUNCTION platform_admin_create_organization(
  p_user_id uuid, p_organization_id uuid, p_slug text, p_legal_name text,
  p_display_name text, p_private_instance boolean
) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=public,pg_temp SET row_security=off AS $fn$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM platform_admins WHERE user_id=p_user_id) THEN
    RAISE EXCEPTION 'platform administrator required' USING ERRCODE='42501';
  END IF;
  IF p_private_instance THEN
    PERFORM pg_advisory_xact_lock(33010329);
    IF EXISTS (SELECT 1 FROM organizations) THEN
      RAISE EXCEPTION 'private instance is limited to one organization' USING ERRCODE='23505';
    END IF;
  END IF;
  INSERT INTO organizations(id,slug,legal_name,display_name,plan_code)
    VALUES(p_organization_id,p_slug,p_legal_name,p_display_name,'FOUNDING_FREE');
  INSERT INTO memberships(organization_id,user_id,role,status)
    VALUES(p_organization_id,p_user_id,'ORG_ADMIN','ACTIVE');
  INSERT INTO organization_settings(organization_id) VALUES(p_organization_id);
  INSERT INTO subscriptions(organization_id,plan_code,status)
    VALUES(p_organization_id,'FOUNDING_FREE','FOUNDING_FREE');
  INSERT INTO audit_events(organization_id,actor_user_id,event_type,target_type,target_id)
    VALUES(p_organization_id,p_user_id,'ORGANIZATION_CREATED','organization',p_organization_id);
  RETURN true;
END; $fn$;

CREATE OR REPLACE FUNCTION platform_admin_grant_free_access(
  p_user_id uuid, p_organization_id uuid, p_reason text
) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=public,pg_temp SET row_security=off AS $fn$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM platform_admins WHERE user_id=p_user_id) THEN
    RAISE EXCEPTION 'platform administrator required' USING ERRCODE='42501';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM organizations WHERE id=p_organization_id) THEN
    RETURN false;
  END IF;
  INSERT INTO subscriptions(organization_id,plan_code,status,admin_note,updated_at)
    VALUES(p_organization_id,'FOUNDING_FREE','FOUNDING_FREE',p_reason,now())
    ON CONFLICT(organization_id) DO UPDATE SET plan_code='FOUNDING_FREE',status='FOUNDING_FREE',
      provider=NULL,provider_customer_id=NULL,provider_subscription_id=NULL,
      free_access_until=NULL,admin_note=EXCLUDED.admin_note,updated_at=now();
  UPDATE organizations SET plan_code='FOUNDING_FREE' WHERE id=p_organization_id;
  INSERT INTO audit_events(organization_id,actor_user_id,event_type,target_type,metadata)
    VALUES(p_organization_id,p_user_id,'FOUNDING_ACCESS_GRANTED','subscription',
      jsonb_build_object('reason',p_reason));
  RETURN true;
END; $fn$;

DO $body$
DECLARE admin_role_oid oid;
BEGIN
  SELECT oid INTO admin_role_oid FROM pg_roles
   WHERE rolname='cfdt_juris_platform_admin' AND rolcanlogin
     AND NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole
     AND NOT rolbypassrls AND NOT rolinherit AND NOT rolreplication;
  IF admin_role_oid IS NULL THEN
    RAISE EXCEPTION 'Dedicated least-privilege role cfdt_juris_platform_admin is missing or unsafe';
  END IF;
  -- Neon grants its project owner ADMIN OPTION on newly created roles by default.
  -- Permit only that control-plane membership when it cannot INHERIT or SET ROLE;
  -- the application role itself must never inherit another role or be inherited by one.
  IF EXISTS (
    SELECT 1 FROM pg_auth_members
    WHERE member=admin_role_oid
       OR (roleid=admin_role_oid AND NOT (
            member=(SELECT oid FROM pg_roles WHERE rolname='neondb_owner')
            AND admin_option AND NOT inherit_option AND NOT set_option
          ))
  ) THEN
    RAISE EXCEPTION 'Platform-admin DB role has an unsafe role membership';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_shdepend WHERE refclassid='pg_authid'::regclass
      AND refobjid=admin_role_oid AND deptype='o') THEN
    RAISE EXCEPTION 'Platform-admin DB role must not own database objects';
  END IF;
END $body$;

-- Remove any accidental pre-existing direct table grants before applying the allowlist.
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM cfdt_juris_platform_admin;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM cfdt_juris_platform_admin;
REVOKE ALL ON SCHEMA public FROM cfdt_juris_platform_admin;
GRANT USAGE ON SCHEMA public TO cfdt_juris_platform_admin;
DO $database$
BEGIN
  EXECUTE format('REVOKE ALL ON DATABASE %I FROM cfdt_juris_platform_admin', current_database());
  EXECUTE format('GRANT CONNECT ON DATABASE %I TO cfdt_juris_platform_admin', current_database());
END;
$database$;

REVOKE ALL ON FUNCTION platform_admin_create_organization(uuid,uuid,text,text,text,boolean) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_admin_grant_free_access(uuid,uuid,text) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION platform_admin_create_organization(uuid,uuid,text,text,text,boolean) FROM cfdt_juris_app;
REVOKE EXECUTE ON FUNCTION platform_admin_grant_free_access(uuid,uuid,text) FROM cfdt_juris_app;
REVOKE EXECUTE ON FUNCTION platform_admin_list_organizations(uuid) FROM cfdt_juris_app;
REVOKE EXECUTE ON FUNCTION platform_admin_set_organization_status(uuid,uuid,text) FROM cfdt_juris_app;
REVOKE EXECUTE ON FUNCTION platform_admin_commercial_summary(uuid,date) FROM cfdt_juris_app;
REVOKE EXECUTE ON FUNCTION platform_admin_commercial_invoices(uuid,integer) FROM cfdt_juris_app;
REVOKE EXECUTE ON FUNCTION platform_admin_organization_seat_counts(uuid,uuid) FROM cfdt_juris_app;
REVOKE EXECUTE ON FUNCTION private_instance_pending_members(uuid) FROM cfdt_juris_app;
REVOKE EXECUTE ON FUNCTION private_instance_set_member_status(uuid,uuid,uuid,text) FROM cfdt_juris_app;

GRANT EXECUTE ON FUNCTION platform_admin_create_organization(uuid,uuid,text,text,text,boolean) TO cfdt_juris_platform_admin;
GRANT EXECUTE ON FUNCTION platform_admin_grant_free_access(uuid,uuid,text) TO cfdt_juris_platform_admin;
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
GRANT SELECT ON platform_free_email_access TO cfdt_juris_platform_admin;
GRANT INSERT (email_normalized,note,granted_by,expires_at) ON platform_free_email_access TO cfdt_juris_platform_admin;
GRANT UPDATE (note,granted_by,expires_at,revoked_at,updated_at) ON platform_free_email_access TO cfdt_juris_platform_admin;
GRANT INSERT (actor_user_id,event_type,target_type,target_id,metadata) ON platform_audit_events TO cfdt_juris_platform_admin;
COMMIT;
