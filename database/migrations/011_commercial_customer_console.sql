-- V3.24 — Commercial dashboard, invoice ledger and tenant invoice history.
BEGIN;
CREATE TABLE IF NOT EXISTS stripe_invoice_records (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  stripe_invoice_id text NOT NULL UNIQUE,
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  stripe_customer_id text,
  stripe_subscription_id text,
  invoice_number text,
  status text NOT NULL DEFAULT 'unknown',
  currency text NOT NULL DEFAULT 'eur',
  amount_due bigint NOT NULL DEFAULT 0,
  amount_paid bigint NOT NULL DEFAULT 0,
  amount_remaining bigint NOT NULL DEFAULT 0,
  period_start timestamptz,
  period_end timestamptz,
  due_at timestamptz,
  paid_at timestamptz,
  issued_at timestamptz,
  hosted_invoice_url text,
  invoice_pdf_url text,
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS stripe_invoice_org_created_idx ON stripe_invoice_records(organization_id, issued_at DESC);
CREATE INDEX IF NOT EXISTS stripe_invoice_status_due_idx ON stripe_invoice_records(status, due_at) WHERE status IN ('open','past_due','uncollectible');
ALTER TABLE stripe_invoice_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE stripe_invoice_records FORCE ROW LEVEL SECURITY;
CREATE POLICY stripe_invoice_tenant_read ON stripe_invoice_records FOR SELECT
  USING (organization_id=NULLIF(current_setting('app.current_org_id',true),'')::uuid);
CREATE POLICY stripe_invoice_webhook_insert ON stripe_invoice_records FOR INSERT
  WITH CHECK (current_setting('app.stripe_webhook_verified',true)='verified');
CREATE POLICY stripe_invoice_webhook_update ON stripe_invoice_records FOR UPDATE
  USING (current_setting('app.stripe_webhook_verified',true)='verified')
  WITH CHECK (current_setting('app.stripe_webhook_verified',true)='verified');
GRANT SELECT, INSERT, UPDATE ON stripe_invoice_records TO cfdt_juris_app;

CREATE OR REPLACE FUNCTION platform_lookup_org_by_stripe_subscription(p_subscription_id text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp SET row_security=off AS $$
DECLARE found_org uuid;
BEGIN
 IF current_setting('app.stripe_webhook_verified',true) IS DISTINCT FROM 'verified' THEN
  RAISE EXCEPTION 'verified Stripe webhook context required' USING ERRCODE='42501';
 END IF;
 SELECT organization_id INTO found_org FROM subscriptions WHERE provider_subscription_id=p_subscription_id;
 RETURN found_org;
END; $$;

CREATE OR REPLACE FUNCTION platform_lookup_plan_by_stripe_subscription(p_subscription_id text)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp SET row_security=off AS $$
DECLARE found_plan text;
BEGIN
 IF current_setting('app.stripe_webhook_verified',true) IS DISTINCT FROM 'verified' THEN
  RAISE EXCEPTION 'verified Stripe webhook context required' USING ERRCODE='42501';
 END IF;
 SELECT plan_code INTO found_plan FROM subscriptions WHERE provider_subscription_id=p_subscription_id;
 RETURN found_plan;
END; $$;

CREATE OR REPLACE FUNCTION tenant_billing_invoice_history(p_organization_id uuid, p_limit integer DEFAULT 50)
RETURNS TABLE(stripe_invoice_id text, invoice_number text, status text, currency text,
 amount_due bigint, amount_paid bigint, amount_remaining bigint, issued_at timestamptz,
 due_at timestamptz, paid_at timestamptz, hosted_invoice_url text, invoice_pdf_url text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp SET row_security=off AS $$
BEGIN
 IF NULLIF(current_setting('app.current_org_id',true),'') IS NULL OR
    NULLIF(current_setting('app.current_org_id',true),'')::uuid <> p_organization_id THEN
   RAISE EXCEPTION 'tenant context required' USING ERRCODE='42501';
 END IF;
 RETURN QUERY SELECT i.stripe_invoice_id,i.invoice_number,i.status,i.currency,i.amount_due,
  i.amount_paid,i.amount_remaining,i.issued_at,i.due_at,i.paid_at,i.hosted_invoice_url,i.invoice_pdf_url
 FROM stripe_invoice_records i WHERE i.organization_id=p_organization_id
 ORDER BY i.issued_at DESC NULLS LAST LIMIT LEAST(GREATEST(p_limit,1),100);
END; $$;

CREATE OR REPLACE FUNCTION platform_admin_commercial_summary(p_user_id uuid, p_month date DEFAULT date_trunc('month',now())::date)
RETURNS TABLE(monthly_revenue_cents bigint, active_subscriptions bigint, past_due_subscriptions bigint,
 active_organizations bigint, free_allowlisted_emails bigint, active_free_members bigint,
 paid_seats_used bigint, paid_seat_capacity bigint, monthly_invoice_count bigint)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp SET row_security=off AS $$
BEGIN
 IF NOT EXISTS (SELECT 1 FROM platform_admins WHERE user_id=p_user_id) THEN
  RAISE EXCEPTION 'platform administrator required' USING ERRCODE='42501';
 END IF;
 RETURN QUERY SELECT
  COALESCE((SELECT sum(amount_paid) FROM stripe_invoice_records WHERE status='paid'
    AND paid_at >= p_month::timestamptz AND paid_at < (p_month + interval '1 month')::timestamptz),0)::bigint,
  (SELECT count(*) FROM subscriptions WHERE status IN ('ACTIVE','TRIAL')),
  (SELECT count(*) FROM subscriptions WHERE status='PAST_DUE'),
  (SELECT count(*) FROM organizations WHERE status='ACTIVE'),
  (SELECT count(*) FROM platform_free_email_access WHERE revoked_at IS NULL AND (expires_at IS NULL OR expires_at>now())),
  (SELECT count(*) FROM memberships m JOIN users u ON u.id=m.user_id JOIN platform_free_email_access f
    ON f.email_normalized=lower(u.email) AND f.revoked_at IS NULL AND (f.expires_at IS NULL OR f.expires_at>now())
    WHERE m.status='ACTIVE' AND u.status='ACTIVE'),
  (SELECT count(*) FROM memberships m JOIN users u ON u.id=m.user_id JOIN subscriptions s ON s.organization_id=m.organization_id
    WHERE m.status='ACTIVE' AND u.status='ACTIVE' AND s.status IN ('ACTIVE','TRIAL','PAST_DUE')
    AND s.plan_code IN ('INDIVIDUAL_1','SYNDICAT_10','SYNDICAT_50','LEGACY_ESSENTIAL_3','LEGACY_SYNDICAT_10')
    AND NOT EXISTS(SELECT 1 FROM platform_free_email_access f WHERE f.email_normalized=lower(u.email)
      AND f.revoked_at IS NULL AND (f.expires_at IS NULL OR f.expires_at>now()))),
  (SELECT COALESCE(sum(CASE plan_code WHEN 'INDIVIDUAL_1' THEN 1 WHEN 'SYNDICAT_10' THEN 10
    WHEN 'SYNDICAT_50' THEN 50 WHEN 'LEGACY_ESSENTIAL_3' THEN 3 WHEN 'LEGACY_SYNDICAT_10' THEN 10 ELSE 0 END),0)
    FROM subscriptions WHERE status IN ('ACTIVE','TRIAL','PAST_DUE')),
  (SELECT count(*) FROM stripe_invoice_records WHERE issued_at >= p_month::timestamptz
    AND issued_at < (p_month + interval '1 month')::timestamptz);
END; $$;

CREATE OR REPLACE FUNCTION platform_admin_organization_seat_counts(p_user_id uuid, p_organization_id uuid)
RETURNS TABLE(paid_active_users bigint, free_active_users bigint)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp SET row_security=off AS $$
BEGIN
 IF NOT EXISTS (SELECT 1 FROM platform_admins WHERE user_id=p_user_id) THEN
  RAISE EXCEPTION 'platform administrator required' USING ERRCODE='42501';
 END IF;
 RETURN QUERY SELECT
  (SELECT count(*) FROM memberships m JOIN users u ON u.id=m.user_id JOIN subscriptions s ON s.organization_id=m.organization_id
   WHERE m.organization_id=p_organization_id AND m.status='ACTIVE' AND u.status='ACTIVE'
   AND s.status IN ('ACTIVE','TRIAL','PAST_DUE') AND s.plan_code IN ('INDIVIDUAL_1','SYNDICAT_10','SYNDICAT_50','LEGACY_ESSENTIAL_3','LEGACY_SYNDICAT_10') AND NOT EXISTS(SELECT 1 FROM platform_free_email_access f
    WHERE f.email_normalized=lower(u.email) AND f.revoked_at IS NULL AND (f.expires_at IS NULL OR f.expires_at>now()))),
  (SELECT count(*) FROM memberships m JOIN users u ON u.id=m.user_id WHERE m.organization_id=p_organization_id
   AND m.status='ACTIVE' AND u.status='ACTIVE' AND EXISTS(SELECT 1 FROM platform_free_email_access f
    WHERE f.email_normalized=lower(u.email) AND f.revoked_at IS NULL AND (f.expires_at IS NULL OR f.expires_at>now())));
END; $$;

CREATE OR REPLACE FUNCTION platform_admin_commercial_invoices(p_user_id uuid, p_limit integer DEFAULT 100)
RETURNS TABLE(organization_id uuid, organization_name text, invoice_number text, stripe_invoice_id text,
 status text, currency text, amount_due bigint, amount_paid bigint, amount_remaining bigint,
 issued_at timestamptz, due_at timestamptz, paid_at timestamptz, hosted_invoice_url text, invoice_pdf_url text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp SET row_security=off AS $$
BEGIN
 IF NOT EXISTS (SELECT 1 FROM platform_admins WHERE user_id=p_user_id) THEN
  RAISE EXCEPTION 'platform administrator required' USING ERRCODE='42501';
 END IF;
 RETURN QUERY SELECT i.organization_id,o.display_name,i.invoice_number,i.stripe_invoice_id,i.status,i.currency,
  i.amount_due,i.amount_paid,i.amount_remaining,i.issued_at,i.due_at,i.paid_at,i.hosted_invoice_url,i.invoice_pdf_url
 FROM stripe_invoice_records i JOIN organizations o ON o.id=i.organization_id
 ORDER BY i.issued_at DESC NULLS LAST LIMIT LEAST(GREATEST(p_limit,1),200);
END; $$;
REVOKE ALL ON FUNCTION tenant_billing_invoice_history(uuid,integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_lookup_org_by_stripe_subscription(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_lookup_plan_by_stripe_subscription(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_admin_commercial_summary(uuid,date) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_admin_commercial_invoices(uuid,integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_admin_organization_seat_counts(uuid,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION tenant_billing_invoice_history(uuid,integer) TO cfdt_juris_app;
GRANT EXECUTE ON FUNCTION platform_lookup_org_by_stripe_subscription(text) TO cfdt_juris_app;
GRANT EXECUTE ON FUNCTION platform_lookup_plan_by_stripe_subscription(text) TO cfdt_juris_app;
GRANT EXECUTE ON FUNCTION platform_admin_commercial_summary(uuid,date) TO cfdt_juris_app;
GRANT EXECUTE ON FUNCTION platform_admin_commercial_invoices(uuid,integer) TO cfdt_juris_app;
GRANT EXECUTE ON FUNCTION platform_admin_organization_seat_counts(uuid,uuid) TO cfdt_juris_app;
COMMIT;
