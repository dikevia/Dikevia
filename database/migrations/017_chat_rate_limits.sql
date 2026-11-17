-- V3.31: database-backed per-user chat request throttling.
-- Buckets contain counters only; no question text or personal content is stored.
BEGIN;
CREATE TABLE chat_rate_limit_buckets (
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    window_start timestamptz NOT NULL,
    request_count integer NOT NULL CHECK (request_count >= 1),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (organization_id,user_id,window_start)
);
CREATE INDEX chat_rate_limit_retention_idx
    ON chat_rate_limit_buckets(organization_id,user_id,window_start);

ALTER TABLE chat_rate_limit_buckets ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_rate_limit_buckets FORCE ROW LEVEL SECURITY;
CREATE POLICY chat_rate_limit_tenant_owner ON chat_rate_limit_buckets
    USING (
      organization_id=NULLIF(current_setting('app.current_org_id',true),'')::uuid
      AND user_id=NULLIF(current_setting('app.current_user_id',true),'')::uuid
    )
    WITH CHECK (
      organization_id=NULLIF(current_setting('app.current_org_id',true),'')::uuid
      AND user_id=NULLIF(current_setting('app.current_user_id',true),'')::uuid
    );

GRANT SELECT (organization_id,user_id,request_count,window_start) ON chat_rate_limit_buckets TO cfdt_juris_app;
GRANT INSERT (organization_id,user_id,window_start,request_count) ON chat_rate_limit_buckets TO cfdt_juris_app;
GRANT UPDATE (request_count) ON chat_rate_limit_buckets TO cfdt_juris_app;
GRANT DELETE ON chat_rate_limit_buckets TO cfdt_juris_app;
COMMIT;
