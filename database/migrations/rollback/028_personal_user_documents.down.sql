BEGIN;

REVOKE ALL ON personal_documents FROM cfdt_juris_app;

DROP TABLE IF EXISTS personal_documents;
DROP FUNCTION IF EXISTS personal_documents_set_search_vector();

COMMIT;
