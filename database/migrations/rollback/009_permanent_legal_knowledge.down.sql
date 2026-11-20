-- DESTRUCTIVE: removes the national legal corpus tables created by migration 009.
-- Run only after a verified backup and explicit --allow-data-loss confirmation.
DROP TABLE IF EXISTS legal_ingestion_runs;
DROP TABLE IF EXISTS legal_document_relations;
DROP TABLE IF EXISTS legal_chunks;
DROP TABLE IF EXISTS legal_document_versions;
DROP TABLE IF EXISTS legal_documents;
DROP FUNCTION IF EXISTS legal_chunks_set_search_vector();
