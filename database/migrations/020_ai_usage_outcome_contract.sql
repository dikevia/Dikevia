-- V3.38.6: align AI usage outcome storage with all orchestrator states.
-- The application records intermediate, accepted, rejected and abstained outcomes.
-- Keep the vocabulary explicit so new states require an intentional migration.
BEGIN;

ALTER TABLE ai_usage_events
    ALTER COLUMN outcome TYPE varchar(80);

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
        'REJECTED_AMBIGUOUS_SOURCE'
    ));

COMMIT;
