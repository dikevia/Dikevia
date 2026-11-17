-- V3.23 — New TTC subscription tiers and individually allowlisted free email access.
-- Existing paid plans are renamed as legacy to preserve their seat limits and Stripe metadata.
BEGIN;
UPDATE subscriptions SET plan_code='LEGACY_ESSENTIAL_3' WHERE plan_code='ESSENTIAL_3';
UPDATE organizations SET plan_code='LEGACY_ESSENTIAL_3' WHERE plan_code='ESSENTIAL_3';
UPDATE subscriptions SET plan_code='LEGACY_SYNDICAT_10' WHERE plan_code='SYNDICAT_10';
UPDATE organizations SET plan_code='LEGACY_SYNDICAT_10' WHERE plan_code='SYNDICAT_10';

CREATE TABLE IF NOT EXISTS platform_free_email_access (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email_normalized text NOT NULL UNIQUE CHECK(email_normalized=lower(trim(email_normalized))),
  note text NOT NULL DEFAULT '',
  granted_by uuid NOT NULL REFERENCES users(id),
  expires_at timestamptz,
  revoked_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS platform_free_email_active_idx
  ON platform_free_email_access(email_normalized) WHERE revoked_at IS NULL;

CREATE TABLE IF NOT EXISTS platform_audit_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  actor_user_id uuid NOT NULL REFERENCES users(id),
  event_type text NOT NULL,
  target_type text NOT NULL,
  target_id uuid,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS platform_audit_events_created_idx ON platform_audit_events(created_at DESC);

GRANT SELECT, INSERT, UPDATE ON platform_free_email_access TO cfdt_juris_app;
GRANT SELECT, INSERT ON platform_audit_events TO cfdt_juris_app;

-- SECURITY DEFINER counters are required because users are protected by self-only RLS.
-- The function is tenant-bound to app.current_org_id and exposes counts only.
CREATE OR REPLACE FUNCTION tenant_billing_seat_counts(p_organization_id uuid)
RETURNS TABLE(paid_active_users bigint, free_active_users bigint,
              pending_paid_invitations bigint, pending_free_invitations bigint)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public, pg_temp
SET row_security = off
AS $$
BEGIN
  IF NULLIF(current_setting('app.current_org_id', true), '') IS NULL
     OR NULLIF(current_setting('app.current_org_id', true), '')::uuid <> p_organization_id THEN
    RAISE EXCEPTION 'tenant context required' USING ERRCODE = '42501';
  END IF;
  RETURN QUERY
  SELECT
    (SELECT count(*) FROM memberships m JOIN users u ON u.id=m.user_id
      WHERE m.organization_id=p_organization_id AND m.status='ACTIVE'
        AND NOT EXISTS (SELECT 1 FROM platform_free_email_access f
          WHERE f.email_normalized=lower(u.email) AND f.revoked_at IS NULL
            AND (f.expires_at IS NULL OR f.expires_at>now()))),
    (SELECT count(*) FROM memberships m JOIN users u ON u.id=m.user_id
      WHERE m.organization_id=p_organization_id AND m.status='ACTIVE'
        AND EXISTS (SELECT 1 FROM platform_free_email_access f
          WHERE f.email_normalized=lower(u.email) AND f.revoked_at IS NULL
            AND (f.expires_at IS NULL OR f.expires_at>now()))),
    (SELECT count(*) FROM invitations i WHERE i.organization_id=p_organization_id
      AND i.status='PENDING' AND i.expires_at>now()
      AND NOT EXISTS (SELECT 1 FROM platform_free_email_access f
        WHERE f.email_normalized=i.email_normalized AND f.revoked_at IS NULL
          AND (f.expires_at IS NULL OR f.expires_at>now()))),
    (SELECT count(*) FROM invitations i WHERE i.organization_id=p_organization_id
      AND i.status='PENDING' AND i.expires_at>now()
      AND EXISTS (SELECT 1 FROM platform_free_email_access f
        WHERE f.email_normalized=i.email_normalized AND f.revoked_at IS NULL
          AND (f.expires_at IS NULL OR f.expires_at>now())));
END;
$$;
REVOKE ALL ON FUNCTION tenant_billing_seat_counts(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION tenant_billing_seat_counts(uuid) TO cfdt_juris_app;

COMMIT;
