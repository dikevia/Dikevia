-- Rollback V3.31 chat throttling. This deletes counters only, never messages.
BEGIN;
DROP TABLE IF EXISTS chat_rate_limit_buckets;
COMMIT;
