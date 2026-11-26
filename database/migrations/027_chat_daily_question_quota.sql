-- Migration 027: daily agent chatbot question quota, account-scoped across organizations.
-- Counters contain no question text or conversation content and are user-isolated with RLS.
BEGIN;

CREATE TABLE chat_daily_question_usage (
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    usage_date date NOT NULL,
    question_count integer NOT NULL CHECK (question_count BETWEEN 1 AND 5),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, usage_date)
);

CREATE INDEX chat_daily_question_usage_retention_idx
    ON chat_daily_question_usage(usage_date);

ALTER TABLE chat_daily_question_usage ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_daily_question_usage FORCE ROW LEVEL SECURITY;

CREATE POLICY chat_daily_question_usage_user_owner
    ON chat_daily_question_usage
    USING (
        user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
    )
    WITH CHECK (
        user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
    );

GRANT SELECT (user_id, usage_date, question_count)
    ON chat_daily_question_usage TO cfdt_juris_app;
GRANT INSERT (user_id, usage_date, question_count)
    ON chat_daily_question_usage TO cfdt_juris_app;
GRANT UPDATE (question_count, updated_at)
    ON chat_daily_question_usage TO cfdt_juris_app;
GRANT DELETE ON chat_daily_question_usage TO cfdt_juris_app;

COMMIT;
