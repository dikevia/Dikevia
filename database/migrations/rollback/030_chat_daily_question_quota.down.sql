-- Roll back the account-scoped daily chatbot question counter.
-- This removes quota history only; it does not affect conversations or legal corpus data.
BEGIN;
DROP TABLE IF EXISTS chat_daily_question_usage;
COMMIT;
