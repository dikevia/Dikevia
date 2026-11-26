-- Migration 028: include current agent/union plan codes in admin seat reporting.
BEGIN;
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
    AND s.plan_code IN ('AGENT_5_QUESTIONS','SYNDICAT_5_ACCES','SYNDICAT_10_ACCES','SYNDICAT_15_ACCES',
      'ESSENTIEL','PRO','EQUIPE_INSTANCES','COLLECTIVITE_SYNDICATS',
      'INDIVIDUAL_1','SYNDICAT_10','SYNDICAT_50','LEGACY_ESSENTIAL_3','LEGACY_SYNDICAT_10')
    AND NOT EXISTS(SELECT 1 FROM platform_free_email_access f WHERE f.email_normalized=lower(u.email)
      AND f.revoked_at IS NULL AND (f.expires_at IS NULL OR f.expires_at>now()))),
  (SELECT COALESCE(sum(CASE plan_code
    WHEN 'AGENT_5_QUESTIONS' THEN 1 WHEN 'SYNDICAT_5_ACCES' THEN 5
    WHEN 'SYNDICAT_10_ACCES' THEN 10 WHEN 'SYNDICAT_15_ACCES' THEN 15
    WHEN 'ESSENTIEL' THEN 1 WHEN 'PRO' THEN 1
    WHEN 'EQUIPE_INSTANCES' THEN 5 WHEN 'COLLECTIVITE_SYNDICATS' THEN 15
    WHEN 'INDIVIDUAL_1' THEN 1 WHEN 'SYNDICAT_10' THEN 10
    WHEN 'SYNDICAT_50' THEN 50 WHEN 'LEGACY_ESSENTIAL_3' THEN 3
    WHEN 'LEGACY_SYNDICAT_10' THEN 10 ELSE 0 END),0)
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
   AND s.status IN ('ACTIVE','TRIAL','PAST_DUE')
   AND s.plan_code IN ('AGENT_5_QUESTIONS','SYNDICAT_5_ACCES','SYNDICAT_10_ACCES','SYNDICAT_15_ACCES',
      'ESSENTIEL','PRO','EQUIPE_INSTANCES','COLLECTIVITE_SYNDICATS',
     'INDIVIDUAL_1','SYNDICAT_10','SYNDICAT_50','LEGACY_ESSENTIAL_3','LEGACY_SYNDICAT_10')
   AND NOT EXISTS(SELECT 1 FROM platform_free_email_access f
    WHERE f.email_normalized=lower(u.email) AND f.revoked_at IS NULL AND (f.expires_at IS NULL OR f.expires_at>now()))),
  (SELECT count(*) FROM memberships m JOIN users u ON u.id=m.user_id WHERE m.organization_id=p_organization_id
   AND m.status='ACTIVE' AND u.status='ACTIVE' AND EXISTS(SELECT 1 FROM platform_free_email_access f
    WHERE f.email_normalized=lower(u.email) AND f.revoked_at IS NULL AND (f.expires_at IS NULL OR f.expires_at>now())));
END; $$;


REVOKE ALL ON FUNCTION platform_admin_commercial_summary(uuid,date) FROM PUBLIC;
REVOKE ALL ON FUNCTION platform_admin_organization_seat_counts(uuid,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION platform_admin_commercial_summary(uuid,date) TO cfdt_juris_app;
GRANT EXECUTE ON FUNCTION platform_admin_organization_seat_counts(uuid,uuid) TO cfdt_juris_app;
COMMIT;
