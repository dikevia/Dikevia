-- V3.40 — Account-level discovery trial and individual lifetime founder entitlements.
-- Additive only. Applying this migration is a separate, explicitly approved operation.
BEGIN;
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS email_verified_at timestamptz,
  ADD COLUMN IF NOT EXISTS trial_started_at timestamptz,
  ADD COLUMN IF NOT EXISTS trial_expires_at timestamptz;
ALTER TABLE users ADD CONSTRAINT users_trial_window_check CHECK (
  (trial_started_at IS NULL AND trial_expires_at IS NULL)
  OR (trial_started_at IS NOT NULL AND trial_expires_at = trial_started_at + interval '72 hours')
);
CREATE INDEX IF NOT EXISTS users_trial_expiry_idx ON users(trial_expires_at)
  WHERE trial_expires_at IS NOT NULL;
CREATE TABLE IF NOT EXISTS founder_entitlements (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slot_number smallint NOT NULL CHECK (slot_number BETWEEN 1 AND 10),
  user_id uuid NOT NULL REFERENCES users(id),
  granted_by uuid NOT NULL REFERENCES users(id),
  granted_at timestamptz NOT NULL DEFAULT now(),
  revoked_at timestamptz,
  note text NOT NULL DEFAULT ''
);
CREATE UNIQUE INDEX IF NOT EXISTS founder_entitlements_one_active_per_slot_idx
  ON founder_entitlements(slot_number) WHERE revoked_at IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS founder_entitlements_one_active_per_user_idx
  ON founder_entitlements(user_id) WHERE revoked_at IS NULL;
ALTER TABLE founder_entitlements ENABLE ROW LEVEL SECURITY;
ALTER TABLE founder_entitlements FORCE ROW LEVEL SECURITY;
CREATE POLICY founder_entitlements_self_read ON founder_entitlements
  FOR SELECT USING (user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid);
GRANT SELECT ON founder_entitlements TO cfdt_juris_app;

CREATE OR REPLACE FUNCTION platform_admin_grant_founder_entitlement(
  p_admin_id uuid, p_slot_number smallint, p_user_id uuid, p_note text
) RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
SET search_path=public,pg_temp SET row_security=off AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM platform_admins WHERE user_id=p_admin_id) THEN
    RAISE EXCEPTION 'platform administrator required' USING ERRCODE='42501';
  END IF;
  IF p_slot_number NOT BETWEEN 1 AND 10 OR length(trim(coalesce(p_note,''))) < 8 THEN
    RAISE EXCEPTION 'invalid founder entitlement arguments' USING ERRCODE='22023';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM users WHERE id=p_user_id AND status='ACTIVE' AND email_verified_at IS NOT NULL) THEN
    RAISE EXCEPTION 'active verified account required' USING ERRCODE='23514';
  END IF;
  PERFORM pg_advisory_xact_lock(33010340);
  IF EXISTS (SELECT 1 FROM founder_entitlements WHERE user_id=p_user_id AND revoked_at IS NULL) THEN
    RAISE EXCEPTION 'user already has an active founder entitlement' USING ERRCODE='23505';
  END IF;
  IF EXISTS (SELECT 1 FROM founder_entitlements WHERE slot_number=p_slot_number AND revoked_at IS NULL) THEN
    RAISE EXCEPTION 'founder slot already assigned' USING ERRCODE='23505';
  END IF;
  INSERT INTO founder_entitlements(slot_number,user_id,granted_by,note)
    VALUES(p_slot_number,p_user_id,p_admin_id,trim(p_note));
  INSERT INTO platform_audit_events(actor_user_id,event_type,target_type,target_id,metadata)
    VALUES(p_admin_id,'FOUNDER_ENTITLEMENT_GRANTED','founder_entitlement',p_user_id,
      jsonb_build_object('slot_number',p_slot_number,'note',trim(p_note)));
  RETURN true;
END; $$;

CREATE OR REPLACE FUNCTION platform_admin_revoke_founder_entitlement(
  p_admin_id uuid, p_slot_number smallint, p_reason text
) RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
SET search_path=public,pg_temp SET row_security=off AS $$
DECLARE target_user uuid;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM platform_admins WHERE user_id=p_admin_id) THEN
    RAISE EXCEPTION 'platform administrator required' USING ERRCODE='42501';
  END IF;
  IF length(trim(coalesce(p_reason,''))) < 8 THEN
    RAISE EXCEPTION 'reason required' USING ERRCODE='22023';
  END IF;
  PERFORM pg_advisory_xact_lock(33010340);
  UPDATE founder_entitlements SET revoked_at=now(),note=trim(p_reason)
    WHERE slot_number=p_slot_number AND revoked_at IS NULL RETURNING user_id INTO target_user;
  IF target_user IS NULL THEN RETURN false; END IF;
  INSERT INTO platform_audit_events(actor_user_id,event_type,target_type,target_id,metadata)
    VALUES(p_admin_id,'FOUNDER_ENTITLEMENT_REVOKED','founder_entitlement',target_user,
      jsonb_build_object('slot_number',p_slot_number,'reason',trim(p_reason)));
  RETURN true;
END; $$;
CREATE OR REPLACE FUNCTION platform_admin_list_founder_entitlements(p_admin_id uuid)
RETURNS TABLE(slot_number smallint,user_id uuid,email text,granted_at timestamptz,revoked_at timestamptz,note text)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=public,pg_temp SET row_security=off AS $fn$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM platform_admins WHERE user_id=p_admin_id) THEN
    RAISE EXCEPTION 'platform administrator required' USING ERRCODE='42501';
  END IF;
  RETURN QUERY SELECT f.slot_number,f.user_id,u.email,f.granted_at,f.revoked_at,f.note
    FROM founder_entitlements f JOIN users u ON u.id=f.user_id ORDER BY f.slot_number;
END; $fn$;
REVOKE ALL ON FUNCTION platform_admin_grant_founder_entitlement(uuid,smallint,uuid,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_admin_revoke_founder_entitlement(uuid,smallint,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_admin_list_founder_entitlements(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION platform_admin_grant_founder_entitlement(uuid,smallint,uuid,text)
  TO cfdt_juris_platform_admin;
GRANT EXECUTE ON FUNCTION platform_admin_revoke_founder_entitlement(uuid,smallint,text)
  TO cfdt_juris_platform_admin;
GRANT EXECUTE ON FUNCTION platform_admin_list_founder_entitlements(uuid)
  TO cfdt_juris_platform_admin;
COMMIT;
