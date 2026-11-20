BEGIN;
-- Administrative reporting crosses tenant boundaries only through these narrowly
-- scoped SECURITY DEFINER functions. The migration owner must be a DBA/BYPASSRLS
-- role; the runtime role receives EXECUTE only, never broad table access.
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname=current_user AND (rolsuper OR rolbypassrls)) THEN
    RAISE EXCEPTION 'Migration 008 must be applied by a DBA role with BYPASSRLS';
  END IF;
END $$;
CREATE OR REPLACE FUNCTION platform_admin_list_organizations(p_user_id uuid)
RETURNS TABLE(
  id uuid, slug text, legal_name text, display_name text, organization_status text,
  plan_code text, subscription_status text, active_users bigint, pending_invitations bigint,
  created_at timestamptz, current_period_end timestamptz, free_access_until timestamptz
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
SET row_security = off
AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM platform_admins WHERE user_id = p_user_id) THEN
    RAISE EXCEPTION 'platform administrator required' USING ERRCODE = '42501';
  END IF;
  RETURN QUERY
    SELECT o.id, o.slug, o.legal_name, o.display_name, o.status,
      COALESCE(s.plan_code, o.plan_code), COALESCE(s.status, 'FOUNDING_FREE'),
      (SELECT count(*) FROM memberships m WHERE m.organization_id=o.id AND m.status='ACTIVE'),
      (SELECT count(*) FROM invitations i WHERE i.organization_id=o.id AND i.status='PENDING' AND i.expires_at>now()),
      o.created_at, s.current_period_end, s.free_access_until
    FROM organizations o LEFT JOIN subscriptions s ON s.organization_id=o.id
    ORDER BY o.created_at DESC;
END;
$$;

CREATE OR REPLACE FUNCTION platform_admin_set_organization_status(
  p_user_id uuid, p_organization_id uuid, p_status text
) RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
SET row_security = off
AS $$
DECLARE changed_id uuid;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM platform_admins WHERE user_id = p_user_id) THEN
    RAISE EXCEPTION 'platform administrator required' USING ERRCODE = '42501';
  END IF;
  IF p_status NOT IN ('ACTIVE','SUSPENDED') THEN
    RAISE EXCEPTION 'invalid organization status' USING ERRCODE = '22023';
  END IF;
  UPDATE organizations SET status=p_status WHERE id=p_organization_id RETURNING id INTO changed_id;
  IF changed_id IS NULL THEN RETURN false; END IF;
  PERFORM set_config('app.current_org_id', p_organization_id::text, true);
  INSERT INTO audit_events(organization_id, actor_user_id, event_type, target_type, target_id, metadata)
  VALUES(p_organization_id, p_user_id,
    CASE WHEN p_status='SUSPENDED' THEN 'ORGANIZATION_SUSPENDED' ELSE 'ORGANIZATION_REACTIVATED' END,
    'organization', p_organization_id, jsonb_build_object('status',p_status));
  RETURN true;
END;
$$;

REVOKE ALL ON FUNCTION platform_admin_list_organizations(uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_admin_set_organization_status(uuid,uuid,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION platform_admin_list_organizations(uuid) TO cfdt_juris_app;
GRANT EXECUTE ON FUNCTION platform_admin_set_organization_status(uuid,uuid,text) TO cfdt_juris_app;
COMMIT;
