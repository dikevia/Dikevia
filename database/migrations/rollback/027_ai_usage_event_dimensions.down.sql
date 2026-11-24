-- Roll back per-operation AI metering.
-- Additional rows per request are collapsed to the latest event before restoring
-- the original request_id primary key; this necessarily discards per-operation detail.
BEGIN;

DELETE FROM ai_usage_events older
USING ai_usage_events newer
WHERE older.request_id = newer.request_id
  AND older.event_id < newer.event_id;

ALTER TABLE ai_usage_events
    DROP CONSTRAINT ai_usage_events_pkey;
ALTER TABLE ai_usage_events
    DROP CONSTRAINT IF EXISTS ai_usage_events_operation_check;
ALTER TABLE ai_usage_events
    DROP CONSTRAINT IF EXISTS ai_usage_events_latency_ms_check;
ALTER TABLE ai_usage_events
    DROP CONSTRAINT IF EXISTS ai_usage_events_outcome_check;

ALTER TABLE ai_usage_events
    DROP COLUMN event_id,
    DROP COLUMN operation,
    DROP COLUMN latency_ms;

ALTER TABLE ai_usage_events
    ADD CONSTRAINT ai_usage_events_pkey PRIMARY KEY (request_id);

-- Preserve the V3.38 outcome contract when returning to one row per request.
-- COMPLETED belongs to the newer per-operation contract; after collapsing events,
-- retain it as the closest V3.38 state for a successfully parsed provider response.
UPDATE ai_usage_events
SET outcome = 'STRUCTURED_OUTPUT_RECEIVED'
WHERE outcome = 'COMPLETED';

ALTER TABLE ai_usage_events
    ADD CONSTRAINT ai_usage_events_outcome_check
    CHECK (outcome IN (
        'ANSWERED',
        'REJECTED_UNGROUNDED',
        'PROVIDER_ERROR',
        'STRUCTURED_OUTPUT_RECEIVED',
        'REJECTED_UNSUPPORTED_CLAIMS',
        'ABSTAINED_NO_SUPPORTED_CLAIMS',
        'REJECTED_UNSUPPORTED_ENTAILMENT',
        'ANSWERED_WITH_PARTIAL_VERIFIED_CLAIMS',
        'ANSWERED_WITH_VERIFIED_QUOTES_AND_ENTAILMENT_CHECK',
        'REJECTED_AMBIGUOUS_SOURCE'
    ));

COMMIT;
