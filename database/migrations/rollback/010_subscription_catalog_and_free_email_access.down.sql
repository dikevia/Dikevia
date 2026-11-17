BEGIN;
DROP FUNCTION IF EXISTS tenant_billing_seat_counts(uuid);
DROP TABLE IF EXISTS platform_audit_events;
DROP TABLE IF EXISTS platform_free_email_access;
UPDATE subscriptions SET plan_code='ESSENTIAL_3' WHERE plan_code='LEGACY_ESSENTIAL_3';
UPDATE organizations SET plan_code='ESSENTIAL_3' WHERE plan_code='LEGACY_ESSENTIAL_3';
UPDATE subscriptions SET plan_code='SYNDICAT_10' WHERE plan_code='LEGACY_SYNDICAT_10';
UPDATE organizations SET plan_code='SYNDICAT_10' WHERE plan_code='LEGACY_SYNDICAT_10';
COMMIT;
