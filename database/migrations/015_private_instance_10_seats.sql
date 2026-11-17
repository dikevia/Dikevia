-- V3.30 private instance: approval workflow and 10 active Premium seats.
BEGIN;
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname=current_user AND (rolsuper OR rolbypassrls)) THEN
    RAISE EXCEPTION 'Migration 015 must be applied by a DBA role with BYPASSRLS';
  END IF;
  IF (SELECT count(*) FROM organizations) > 1 THEN
    RAISE EXCEPTION 'Migration 015 requires at most one organization; review existing tenant data before enabling private mode';
  END IF;
  IF (SELECT count(*) FROM memberships WHERE status='ACTIVE') > 10 THEN
    RAISE EXCEPTION 'Migration 015 requires at most ten active memberships; review existing access before enabling private mode';
  END IF;
END $$;
ALTER TABLE memberships DROP CONSTRAINT IF EXISTS memberships_status_check;
ALTER TABLE memberships ADD CONSTRAINT memberships_status_check
  CHECK(status IN ('INVITED','ACTIVE','SUSPENDED','REVOKED'));

CREATE OR REPLACE FUNCTION private_instance_pending_members(p_admin_id uuid)
RETURNS TABLE(organization_id uuid, user_id uuid, email text, role text, membership_status text, created_at timestamptz)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=public,pg_temp SET row_security=off AS $$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM platform_admins WHERE user_id=p_admin_id) THEN
   RAISE EXCEPTION 'platform administrator required' USING ERRCODE='42501';
 END IF;
 RETURN QUERY
 SELECT m.organization_id,m.user_id,u.email,m.role,m.status,m.created_at
 FROM memberships m JOIN users u ON u.id=m.user_id
 WHERE m.status IN ('INVITED','ACTIVE','SUSPENDED')
 ORDER BY m.created_at;
END; $$;

CREATE OR REPLACE FUNCTION private_instance_set_member_status(
 p_admin_id uuid,p_organization_id uuid,p_user_id uuid,p_status text
) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=public,pg_temp SET row_security=off AS $$
DECLARE active_count bigint; current_status text;
BEGIN
 IF NOT EXISTS(SELECT 1 FROM platform_admins WHERE user_id=p_admin_id) THEN
   RAISE EXCEPTION 'platform administrator required' USING ERRCODE='42501';
 END IF;
 IF p_status NOT IN ('ACTIVE','SUSPENDED','REVOKED') THEN
   RAISE EXCEPTION 'invalid membership status' USING ERRCODE='22023';
 END IF;
 PERFORM pg_advisory_xact_lock(33010330);
 PERFORM 1 FROM organizations WHERE id=p_organization_id FOR UPDATE;
 SELECT status INTO current_status FROM memberships
  WHERE organization_id=p_organization_id AND user_id=p_user_id FOR UPDATE;
 IF current_status IS NULL THEN RETURN false; END IF;
 IF p_status='ACTIVE' AND current_status<>'ACTIVE' THEN
   SELECT count(*) INTO active_count FROM memberships WHERE status='ACTIVE';
   IF active_count>=10 THEN
     RAISE EXCEPTION 'private instance seat limit reached' USING ERRCODE='23514';
   END IF;
 END IF;
 UPDATE memberships SET status=p_status
  WHERE organization_id=p_organization_id AND user_id=p_user_id;
 INSERT INTO audit_events(organization_id,actor_user_id,event_type,target_type,target_id,metadata)
 VALUES(p_organization_id,p_admin_id,
   CASE p_status WHEN 'ACTIVE' THEN 'PRIVATE_MEMBER_APPROVED'
     WHEN 'SUSPENDED' THEN 'PRIVATE_MEMBER_SUSPENDED' ELSE 'PRIVATE_MEMBER_REVOKED' END,
   'membership',(SELECT id FROM memberships WHERE organization_id=p_organization_id AND user_id=p_user_id),
   jsonb_build_object('status',p_status));
 RETURN true;
END; $$;

REVOKE ALL ON FUNCTION private_instance_pending_members(uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION private_instance_set_member_status(uuid,uuid,uuid,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION private_instance_pending_members(uuid) TO cfdt_juris_app;
GRANT EXECUTE ON FUNCTION private_instance_set_member_status(uuid,uuid,uuid,text) TO cfdt_juris_app;
COMMIT;
