BEGIN;
ALTER TABLE subscriptions
  ADD COLUMN IF NOT EXISTS cancel_at_period_end boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS free_access_until timestamptz,
  ADD COLUMN IF NOT EXISTS admin_note text,
  ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

CREATE TABLE IF NOT EXISTS billing_webhook_events (
  provider_event_id text PRIMARY KEY,
  event_type text NOT NULL,
  processed_at timestamptz NOT NULL DEFAULT now()
);
-- Stripe webhooks are authenticated independently; the table stores event IDs only,
-- not card data or full webhook payloads.
GRANT SELECT, INSERT ON billing_webhook_events TO cfdt_juris_app;
GRANT INSERT (organization_id, provider, provider_customer_id, provider_subscription_id,
  plan_code, status, current_period_end, cancel_at_period_end, updated_at)
  ON subscriptions TO cfdt_juris_app;
GRANT UPDATE (provider, provider_customer_id, provider_subscription_id, plan_code,
  status, current_period_end, cancel_at_period_end, free_access_until, admin_note, updated_at)
  ON subscriptions TO cfdt_juris_app;
GRANT UPDATE (plan_code) ON organizations TO cfdt_juris_app;
GRANT SELECT ON subscriptions TO cfdt_juris_app;
COMMIT;
