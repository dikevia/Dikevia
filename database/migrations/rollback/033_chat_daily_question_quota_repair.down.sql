-- Roll back migration 033: removes only the daily question counter and its
-- quota history. It does not touch users, subscriptions, messages or legal data.
BEGIN;
DROP TABLE IF EXISTS chat_daily_question_usage;
COMMIT;
