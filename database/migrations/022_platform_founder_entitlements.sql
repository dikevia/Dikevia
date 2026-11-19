-- V3.44: permanent founder entitlement bound to a verified OIDC identity.
-- Email addresses are deliberately not used as entitlement keys.
BEGIN;

CREATE TABLE platform_founder_entitlements (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    oidc_issuer text NOT NULL CHECK (length(oidc_issuer) BETWEEN 1 AND 500),
    oidc_subject text NOT NULL CHECK (length(oidc_subject) BETWEEN 1 AND 500),
    note text NOT NULL DEFAULT '',
    granted_by uuid NOT NULL REFERENCES users(id),
    granted_at timestamptz NOT NULL DEFAULT now(),
    revoked_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (oidc_issuer, oidc_subject)
);
CREATE INDEX platform_founder_active_idx
    ON platform_founder_entitlements(user_id) WHERE revoked_at IS NULL;

ALTER TABLE platform_founder_entitlements ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform_founder_entitlements FORCE ROW LEVEL SECURITY;
CREATE POLICY platform_founder_self_read ON platform_founder_entitlements
    FOR SELECT USING (
      user_id IN (
        SELECT id FROM users
        WHERE oidc_issuer=NULLIF(current_setting('app.oidc_issuer',true),'')
          AND oidc_subject=NULLIF(current_setting('app.oidc_subject',true),'')
          AND status='ACTIVE'
      )
    );
GRANT SELECT ON platform_founder_entitlements TO cfdt_juris_app;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON platform_founder_entitlements FROM cfdt_juris_app;

-- A subject can be granted only after that exact issuer/subject has authenticated
-- successfully and exists as an active user. No email matching or guessing.
CREATE OR REPLACE FUNCTION platform_admin_grant_founder_entitlement(
    p_actor_user_id uuid,
    p_target_user_id uuid,
    p_note text
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=public,pg_temp
SET row_security=off
AS $$
DECLARE
    v_target_user_id uuid;
    v_target_issuer text;
    v_target_subject text;
    v_entitlement_id uuid;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM platform_admins WHERE user_id=p_actor_user_id) THEN
      RAISE EXCEPTION 'platform administrator required' USING ERRCODE='42501';
    END IF;
    IF p_target_user_id IS NULL OR length(COALESCE(p_note,'')) NOT BETWEEN 8 AND 500 THEN
      RAISE EXCEPTION 'invalid founder entitlement request' USING ERRCODE='22023';
    END IF;

    SELECT id,oidc_issuer,oidc_subject
      INTO v_target_user_id,v_target_issuer,v_target_subject
      FROM users WHERE id=p_target_user_id AND status='ACTIVE';
    IF v_target_user_id IS NULL OR v_target_issuer IS NULL OR v_target_subject IS NULL THEN
      RETURN NULL;
    END IF;

    INSERT INTO platform_founder_entitlements(
      user_id,oidc_issuer,oidc_subject,note,granted_by,granted_at,revoked_at,updated_at
    ) VALUES (
      v_target_user_id,v_target_issuer,v_target_subject,p_note,p_actor_user_id,now(),NULL,now()
    )
    ON CONFLICT(user_id) DO UPDATE SET
      oidc_issuer=EXCLUDED.oidc_issuer,oidc_subject=EXCLUDED.oidc_subject,
      note=EXCLUDED.note,granted_by=EXCLUDED.granted_by,
      granted_at=now(),revoked_at=NULL,updated_at=now()
    RETURNING id INTO v_entitlement_id;

    INSERT INTO platform_audit_events(actor_user_id,event_type,target_type,target_id,metadata)
      VALUES(p_actor_user_id,'FOUNDER_ENTITLEMENT_GRANTED','user',v_target_user_id,
        jsonb_build_object('note',p_note));
    RETURN v_target_user_id;
END;
$$;

CREATE OR REPLACE FUNCTION platform_admin_revoke_founder_entitlement(
    p_actor_user_id uuid,
    p_target_user_id uuid
) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=public,pg_temp
SET row_security=off
AS $$
DECLARE v_changed boolean;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM platform_admins WHERE user_id=p_actor_user_id) THEN
      RAISE EXCEPTION 'platform administrator required' USING ERRCODE='42501';
    END IF;
    UPDATE platform_founder_entitlements SET revoked_at=now(),updated_at=now()
      WHERE user_id=p_target_user_id AND revoked_at IS NULL;
    v_changed := FOUND;
    IF v_changed THEN
      INSERT INTO platform_audit_events(actor_user_id,event_type,target_type,target_id,metadata)
        VALUES(p_actor_user_id,'FOUNDER_ENTITLEMENT_REVOKED','user',p_target_user_id,'{}'::jsonb);
    END IF;
    RETURN v_changed;
END;
$$;

CREATE OR REPLACE FUNCTION platform_admin_list_founder_entitlements(
    p_actor_user_id uuid
) RETURNS TABLE(user_id uuid,note text,granted_at timestamptz,revoked_at timestamptz)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=public,pg_temp
SET row_security=off
AS $founder_list$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM platform_admins pa WHERE pa.user_id=p_actor_user_id) THEN
      RAISE EXCEPTION 'platform administrator required' USING ERRCODE='42501';
    END IF;
    RETURN QUERY SELECT e.user_id,e.note,e.granted_at,e.revoked_at
      FROM platform_founder_entitlements e ORDER BY e.granted_at DESC LIMIT 200;
END;
$founder_list$;

REVOKE ALL ON FUNCTION platform_admin_grant_founder_entitlement(uuid,uuid,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_admin_revoke_founder_entitlement(uuid,uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_admin_list_founder_entitlements(uuid) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION platform_admin_grant_founder_entitlement(uuid,uuid,text) FROM cfdt_juris_app;
REVOKE EXECUTE ON FUNCTION platform_admin_revoke_founder_entitlement(uuid,uuid) FROM cfdt_juris_app;
GRANT EXECUTE ON FUNCTION platform_admin_grant_founder_entitlement(uuid,uuid,text) TO cfdt_juris_platform_admin;
GRANT EXECUTE ON FUNCTION platform_admin_revoke_founder_entitlement(uuid,uuid) TO cfdt_juris_platform_admin;
REVOKE SELECT ON platform_founder_entitlements FROM cfdt_juris_platform_admin;
GRANT EXECUTE ON FUNCTION platform_admin_list_founder_entitlements(uuid) TO cfdt_juris_platform_admin;

COMMIT;
