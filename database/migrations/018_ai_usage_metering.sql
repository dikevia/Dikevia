-- V3.32: privacy-minimal AI token metering, scoped to organization and user.
-- No prompt, response, conversation or document content is stored.
BEGIN;
CREATE TABLE ai_usage_events (
    request_id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider varchar(40) NOT NULL CHECK (length(provider) BETWEEN 1 AND 40),
    model varchar(160) NOT NULL CHECK (length(model) BETWEEN 1 AND 160),
    prompt_tokens integer CHECK (prompt_tokens IS NULL OR prompt_tokens >= 0),
    completion_tokens integer CHECK (completion_tokens IS NULL OR completion_tokens >= 0),
    total_tokens integer CHECK (total_tokens IS NULL OR total_tokens >= 0),
    outcome varchar(40) NOT NULL CHECK (outcome IN ('ANSWERED','REJECTED_UNGROUNDED')),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ai_usage_events_org_created_idx
    ON ai_usage_events(organization_id,created_at DESC);
ALTER TABLE ai_usage_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_usage_events FORCE ROW LEVEL SECURITY;
CREATE POLICY ai_usage_events_tenant_insert ON ai_usage_events
    FOR INSERT
    WITH CHECK (
      organization_id=NULLIF(current_setting('app.current_org_id',true),'')::uuid
      AND user_id=NULLIF(current_setting('app.current_user_id',true),'')::uuid
    );
-- Runtime can append events only. Reading/reporting requires a separate audited
-- administrative path; ordinary users cannot inspect usage ledgers.
GRANT INSERT (request_id,organization_id,user_id,provider,model,prompt_tokens,
              completion_tokens,total_tokens,outcome)
    ON ai_usage_events TO cfdt_juris_app;
COMMIT;
