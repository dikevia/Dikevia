BEGIN;
DROP FUNCTION IF EXISTS wallet_apply_entry(uuid,bigint,text,text,text);
DROP TABLE IF EXISTS credit_ledger_entries;
DROP TABLE IF EXISTS credit_accounts;
COMMIT;
