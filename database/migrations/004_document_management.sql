BEGIN;

ALTER TABLE documents
  ADD COLUMN IF NOT EXISTS original_filename text,
  ADD COLUMN IF NOT EXISTS mime_type text,
  ADD COLUMN IF NOT EXISTS file_size_bytes bigint,
  ADD COLUMN IF NOT EXISTS uploaded_by uuid REFERENCES users(id),
  ADD COLUMN IF NOT EXISTS validation_note text;

ALTER TABLE document_versions
  ADD COLUMN IF NOT EXISTS original_filename text,
  ADD COLUMN IF NOT EXISTS mime_type text,
  ADD COLUMN IF NOT EXISTS file_size_bytes bigint,
  ADD COLUMN IF NOT EXISTS uploaded_by uuid REFERENCES users(id);

CREATE INDEX IF NOT EXISTS documents_org_collectivity_created_idx
  ON documents(organization_id, collectivity_id, created_at DESC);
CREATE INDEX IF NOT EXISTS document_versions_org_document_idx
  ON document_versions(organization_id, document_id, version_number DESC);

-- Runtime privileges are applied separately by the DBA using database/grant_runtime_permissions.sql.

COMMIT;
