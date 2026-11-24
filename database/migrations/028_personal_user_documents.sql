BEGIN;

CREATE TABLE IF NOT EXISTS personal_documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title text NOT NULL,
  document_type text NOT NULL DEFAULT 'PERSONAL_REFERENCE',
  original_filename text NOT NULL,
  mime_type text NOT NULL,
  file_size_bytes bigint NOT NULL CHECK (file_size_bytes > 0 AND file_size_bytes <= 20971520),
  storage_key text NOT NULL UNIQUE,
  sha256 char(64) NOT NULL,
  scan_status text NOT NULL CHECK (scan_status IN ('CLEAN','INFECTED')),
  scan_engine text NOT NULL,
  scanned_at timestamptz NOT NULL,
  extraction_status text NOT NULL CHECK (extraction_status IN
    ('EXTRACTED','NO_TEXT','ENCRYPTED','TOO_LARGE_TO_EXTRACT','FAILED','UNSUPPORTED')),
  extracted_text text NOT NULL DEFAULT '',
  search_vector tsvector NOT NULL DEFAULT ''::tsvector,
  collectivity_scope text NOT NULL DEFAULT 'VILLE_SAINT_ETIENNE'
    CHECK (collectivity_scope IN ('VILLE_SAINT_ETIENNE','SAINT_ETIENNE_METROPOLE','MIXED_LOCAL_SCOPE','UNCLASSIFIED')),
  effective_from date,
  effective_to date,
  validation_status text NOT NULL DEFAULT 'COLLECTED_UNVERIFIED'
    CHECK (validation_status IN ('COLLECTED_UNVERIFIED','VERIFIED_APPLICABLE','VERIFIED_HISTORICAL','INCOMPLETE','REPEALED','REPLACED')),
  validation_note text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from)
);

CREATE OR REPLACE FUNCTION personal_documents_set_search_vector() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  NEW.search_vector := to_tsvector('french', coalesce(NEW.title, '') || ' ' || coalesce(NEW.extracted_text, ''));
  NEW.updated_at := now();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS personal_documents_search_vector_trigger ON personal_documents;
CREATE TRIGGER personal_documents_search_vector_trigger
BEFORE INSERT OR UPDATE OF title, extracted_text ON personal_documents
FOR EACH ROW EXECUTE FUNCTION personal_documents_set_search_vector();

CREATE INDEX IF NOT EXISTS personal_documents_owner_created_idx
  ON personal_documents(owner_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS personal_documents_search_vector_gin
  ON personal_documents USING GIN(search_vector);

ALTER TABLE personal_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE personal_documents FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS personal_documents_owner_isolation ON personal_documents;
CREATE POLICY personal_documents_owner_isolation ON personal_documents
  FOR ALL
  USING (owner_user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid)
  WITH CHECK (owner_user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid);

COMMIT;
