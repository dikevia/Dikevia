-- V3.21 — Référentiel juridique national partagé (sources publiques officielles).
-- Les tables de ce référentiel sont communes à tous les tenants ; les documents
-- propres aux collectivités restent dans les tables tenant-scoped existantes.
BEGIN;
CREATE TABLE IF NOT EXISTS legal_documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_type text NOT NULL CHECK (source_type IN ('LEGIFRANCE_LEGI','LEGIFRANCE_LODA','LEGIFRANCE_CETAT','DILA_CIRCULAIRES','LEGIFRANCE_JORF','OTHER_OFFICIAL')),
  source_id text NOT NULL,
  title text NOT NULL,
  document_kind text NOT NULL CHECK (document_kind IN ('CODE','LAW','ORDONNANCE','DECREE','ORDER','CIRCULAR','ADMIN_CASELAW','JOURNAL_OFFICIEL','OTHER')),
  official_number text,
  jurisdiction text,
  publisher text,
  official_url text,
  signature_date date,
  publication_date date,
  status text NOT NULL DEFAULT 'UNKNOWN' CHECK (status IN ('IN_FORCE','REPEALED','REPLACED','NOT_IN_FORCE','UNKNOWN','PARTIAL')),
  source_status text NOT NULL DEFAULT 'METADATA_ONLY' CHECK (source_status IN ('METADATA_ONLY','OFFICIAL_TEXT_RETRIEVED','OFFICIAL_TEXT_ID_VERIFIED','OFFICIAL_XML_IMPORTED','IMPORTED_UNVERIFIED','MANUALLY_VERIFIED')),
  raw_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  content_sha256 char(64),
  first_seen_at timestamptz NOT NULL DEFAULT now(),
  last_seen_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(source_type, source_id)
);
CREATE INDEX IF NOT EXISTS legal_documents_kind_status_idx ON legal_documents(document_kind,status);
CREATE INDEX IF NOT EXISTS legal_documents_number_idx ON legal_documents(official_number);

CREATE TABLE IF NOT EXISTS legal_document_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id uuid NOT NULL REFERENCES legal_documents(id) ON DELETE CASCADE,
  version_key text NOT NULL,
  source_version_id text,
  valid_from date,
  valid_to date,
  version_status text NOT NULL DEFAULT 'UNKNOWN' CHECK (version_status IN ('IN_FORCE','REPEALED','REPLACED','NOT_IN_FORCE','UNKNOWN')),
  full_text text NOT NULL DEFAULT '',
  text_sha256 char(64),
  raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  retrieved_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(document_id, version_key)
);
CREATE INDEX IF NOT EXISTS legal_versions_dates_idx ON legal_document_versions(valid_from,valid_to);
CREATE INDEX IF NOT EXISTS legal_versions_document_idx ON legal_document_versions(document_id,valid_from DESC);

CREATE TABLE IF NOT EXISTS legal_chunks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  version_id uuid NOT NULL REFERENCES legal_document_versions(id) ON DELETE CASCADE,
  ordinal integer NOT NULL CHECK (ordinal >= 0),
  anchor text,
  content_kind text NOT NULL DEFAULT 'FULL_TEXT' CHECK (content_kind IN ('FULL_TEXT','METADATA')),
  content text NOT NULL,
  search_vector tsvector NOT NULL DEFAULT ''::tsvector,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(version_id,ordinal)
);
CREATE OR REPLACE FUNCTION legal_chunks_set_search_vector() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN NEW.search_vector := to_tsvector('french',coalesce(NEW.anchor,'') || ' ' || coalesce(NEW.content,'')); RETURN NEW; END; $$;
DROP TRIGGER IF EXISTS legal_chunks_search_vector_trigger ON legal_chunks;
CREATE TRIGGER legal_chunks_search_vector_trigger BEFORE INSERT OR UPDATE OF anchor,content ON legal_chunks
 FOR EACH ROW EXECUTE FUNCTION legal_chunks_set_search_vector();
CREATE INDEX IF NOT EXISTS legal_chunks_search_vector_gin ON legal_chunks USING GIN(search_vector);

CREATE TABLE IF NOT EXISTS legal_document_relations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_document_id uuid NOT NULL REFERENCES legal_documents(id) ON DELETE CASCADE,
  target_document_id uuid NOT NULL REFERENCES legal_documents(id) ON DELETE CASCADE,
  relation_type text NOT NULL CHECK (relation_type IN ('AMENDS','AMENDED_BY','REPEALS','REPEALED_BY','REPLACES','REPLACED_BY','APPLIES','INTERPRETS','CITES','RELATED')),
  source_reference text,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(source_document_id,target_document_id,relation_type)
);

CREATE TABLE IF NOT EXISTS legal_ingestion_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_type text NOT NULL,
  run_mode text NOT NULL CHECK (run_mode IN ('SEARCH_IMPORT','BULK_XML_IMPORT','FULL_REFRESH','INCREMENTAL_REFRESH')),
  status text NOT NULL CHECK (status IN ('RUNNING','SUCCEEDED','PARTIAL','FAILED')),
  query_text text,
  records_seen integer NOT NULL DEFAULT 0,
  records_imported integer NOT NULL DEFAULT 0,
  records_rejected integer NOT NULL DEFAULT 0,
  error_summary text,
  started_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz
);
CREATE INDEX IF NOT EXISTS legal_ingestion_runs_started_idx ON legal_ingestion_runs(started_at DESC);

-- Référentiel public commun : lecture pour tous les utilisateurs authentifiés
-- (via l'API), écriture réservée aux opérations d'ingestion contrôlées.
GRANT SELECT ON legal_documents,legal_document_versions,legal_chunks,legal_document_relations,legal_ingestion_runs TO cfdt_juris_app;
-- Writes are isolated to a dedicated ingestion DB role. The ordinary API role is read-only.
GRANT SELECT ON legal_documents,legal_document_versions,legal_chunks,legal_document_relations,legal_ingestion_runs TO cfdt_juris_app;
GRANT SELECT,INSERT,UPDATE,DELETE ON legal_documents,legal_document_versions,legal_chunks,legal_document_relations,legal_ingestion_runs TO cfdt_juris_ingest;
COMMIT;
