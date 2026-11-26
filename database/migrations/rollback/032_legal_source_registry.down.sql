BEGIN;
DROP TRIGGER IF EXISTS legal_ingestion_runs_assign_source_key_trigger ON legal_ingestion_runs;
DROP FUNCTION IF EXISTS legal_ingestion_runs_assign_source_key();
DROP INDEX IF EXISTS legal_ingestion_runs_source_key_idx;
DROP INDEX IF EXISTS legal_documents_source_key_idx;
ALTER TABLE legal_ingestion_runs DROP COLUMN IF EXISTS source_key;
ALTER TABLE legal_documents DROP COLUMN IF EXISTS source_key;
DROP TABLE IF EXISTS legal_source_registry;
COMMIT;
