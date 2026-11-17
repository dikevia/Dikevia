BEGIN;

ALTER TABLE documents
  ADD COLUMN IF NOT EXISTS scan_status text NOT NULL DEFAULT 'NOT_SCANNED'
    CHECK (scan_status IN ('NOT_SCANNED','CLEAN','INFECTED')),
  ADD COLUMN IF NOT EXISTS scan_engine text,
  ADD COLUMN IF NOT EXISTS scanned_at timestamptz;

ALTER TABLE document_versions
  ADD COLUMN IF NOT EXISTS scan_status text NOT NULL DEFAULT 'NOT_SCANNED'
    CHECK (scan_status IN ('NOT_SCANNED','CLEAN','INFECTED')),
  ADD COLUMN IF NOT EXISTS scan_engine text,
  ADD COLUMN IF NOT EXISTS scanned_at timestamptz;

CREATE TABLE IF NOT EXISTS document_text (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL,
  document_id uuid NOT NULL,
  version_number integer NOT NULL,
  sha256 char(64) NOT NULL,
  extracted_text text NOT NULL DEFAULT '',
  extraction_status text NOT NULL CHECK (extraction_status IN
    ('EXTRACTED','NO_TEXT','ENCRYPTED','TOO_LARGE_TO_EXTRACT','FAILED','UNSUPPORTED')),
  search_vector tsvector NOT NULL DEFAULT ''::tsvector,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, document_id, version_number),
  FOREIGN KEY (organization_id, document_id, version_number)
    REFERENCES document_versions(organization_id, document_id, version_number) ON DELETE CASCADE
);

CREATE OR REPLACE FUNCTION document_text_set_search_vector() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  NEW.search_vector := to_tsvector('french', coalesce(NEW.extracted_text, ''));
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS document_text_search_vector_trigger ON document_text;
CREATE TRIGGER document_text_search_vector_trigger
BEFORE INSERT OR UPDATE OF extracted_text ON document_text
FOR EACH ROW EXECUTE FUNCTION document_text_set_search_vector();

CREATE INDEX IF NOT EXISTS document_text_search_vector_gin
  ON document_text USING GIN(search_vector);
CREATE INDEX IF NOT EXISTS document_text_org_document_idx
  ON document_text(organization_id, document_id, version_number DESC);

ALTER TABLE document_text ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_text FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS document_text_tenant_isolation ON document_text;
CREATE POLICY document_text_tenant_isolation ON document_text
  USING (organization_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid)
  WITH CHECK (organization_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid);

COMMIT;
