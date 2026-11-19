-- Keep AI metering compatible with the security orchestrator's explicit
-- refusal/abstention outcomes. This stores status metadata only, never content.
BEGIN;

ALTER TABLE ai_usage_events
  DROP CONSTRAINT IF EXISTS ai_usage_events_outcome_check;

ALTER TABLE ai_usage_events
  ADD CONSTRAINT ai_usage_events_outcome_check
  CHECK (outcome IN (
    'ANSWERED',
    'REJECTED_UNGROUNDED',
    'PROVIDER_ERROR',
    'REJECTED_UNSUPPORTED_CLAIMS',
    'ABSTAINED_NO_SUPPORTED_CLAIMS',
    'REJECTED_UNSUPPORTED_ENTAILMENT',
    'ANSWERED_WITH_VERIFIED_QUOTES_AND_ENTAILMENT_CHECK',
    'REJECTED_AMBIGUOUS_SOURCE'
  ));

COMMIT;
