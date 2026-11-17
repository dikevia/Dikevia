-- Rollback V3.32 AI token usage metering. Removes usage counters only.
BEGIN;
DROP TABLE IF EXISTS ai_usage_events;
COMMIT;
