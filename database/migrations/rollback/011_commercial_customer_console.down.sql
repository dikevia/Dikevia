BEGIN;
DROP FUNCTION IF EXISTS platform_admin_commercial_invoices(uuid,integer);
DROP FUNCTION IF EXISTS platform_admin_organization_seat_counts(uuid,uuid);
DROP FUNCTION IF EXISTS platform_admin_commercial_summary(uuid,date);
DROP FUNCTION IF EXISTS tenant_billing_invoice_history(uuid,integer);
DROP FUNCTION IF EXISTS platform_lookup_org_by_stripe_subscription(text);
DROP FUNCTION IF EXISTS platform_lookup_plan_by_stripe_subscription(text);
DROP TABLE IF EXISTS stripe_invoice_records;
COMMIT;
