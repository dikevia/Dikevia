-- Remove the temporary beta account-capacity guard.
BEGIN;
DROP FUNCTION IF EXISTS beta_user_slot_available(text,integer);
COMMIT;
