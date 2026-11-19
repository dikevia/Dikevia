-- Restore the original AI outcome allowlist only when no newer outcome is stored.
BEGIN;
DO $rollback$
BEGIN
  IF EXISTS (
    SELECT 1 FROM ai_usage_events
    WHERE outcome NOT IN ('ANSWERED','REJECTED_UNGROUNDED','PROVIDER_ERROR') OR length(outcome)>40
  ) THEN
    RAISE EXCEPTION 'Rollback 020 refused: newer AI outcomes are already stored';
  END IF;
END;
$rollback$;

ALTER TABLE ai_usage_events
  DROP CONSTRAINT IF EXISTS ai_usage_events_outcome_check;
ALTER TABLE ai_usage_events
  ALTER COLUMN outcome TYPE varchar(40);
ALTER TABLE ai_usage_events
  ADD CONSTRAINT ai_usage_events_outcome_check
  CHECK (outcome IN ('ANSWERED','REJECTED_UNGROUNDED','PROVIDER_ERROR'));
COMMIT;
