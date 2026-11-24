-- V3.39: store one privacy-minimal metering row per AI operation, not per chat request.
-- Existing request-level rows are retained and classified as answer-generation events.
BEGIN;

ALTER TABLE ai_usage_events
    DROP CONSTRAINT ai_usage_events_pkey;

ALTER TABLE ai_usage_events
    ADD COLUMN event_id bigserial;

ALTER TABLE ai_usage_events
    ADD CONSTRAINT ai_usage_events_pkey PRIMARY KEY (event_id);

ALTER TABLE ai_usage_events
    ADD COLUMN operation varchar(40) NOT NULL DEFAULT 'answer_generation';

ALTER TABLE ai_usage_events
    ADD CONSTRAINT ai_usage_events_operation_check
    CHECK (operation IN ('research_planning','source_relevance','answer_generation','claim_entailment'));

ALTER TABLE ai_usage_events
    ADD COLUMN latency_ms integer;

ALTER TABLE ai_usage_events
    ADD CONSTRAINT ai_usage_events_latency_ms_check
    CHECK (latency_ms IS NULL OR latency_ms >= 0);

CREATE INDEX ai_usage_events_request_idx
    ON ai_usage_events(request_id, created_at, event_id);

ALTER TABLE ai_usage_events
    DROP CONSTRAINT IF EXISTS ai_usage_events_outcome_check;

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
        'REJECTED_AMBIGUOUS_SOURCE',
        'COMPLETED'
    ));

GRANT INSERT (request_id,organization_id,user_id,operation,provider,model,prompt_tokens,
              completion_tokens,total_tokens,latency_ms,outcome)
    ON ai_usage_events TO cfdt_juris_app;
GRANT USAGE, SELECT ON SEQUENCE ai_usage_events_event_id_seq TO cfdt_juris_app;

COMMIT;
