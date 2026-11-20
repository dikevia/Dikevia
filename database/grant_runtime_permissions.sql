-- Execute as the migration/DBA role AFTER all migrations.
-- The API role must not own tables and must have no schema/role-management rights.
-- Prefer column grants: the runtime cannot rewrite identity keys, tenant keys, or audit history.
GRANT SELECT ON organizations TO cfdt_juris_app;
GRANT INSERT (id, slug, legal_name, display_name, plan_code) ON organizations TO cfdt_juris_app;

GRANT SELECT (id, oidc_issuer, oidc_subject, email, display_name, status) ON users TO cfdt_juris_app;
GRANT INSERT (oidc_issuer, oidc_subject, email, display_name, status) ON users TO cfdt_juris_app;
GRANT UPDATE (email) ON users TO cfdt_juris_app;

GRANT SELECT ON platform_admins TO cfdt_juris_app;

GRANT SELECT ON memberships TO cfdt_juris_app;
GRANT INSERT (organization_id, user_id, role, status) ON memberships TO cfdt_juris_app;
GRANT UPDATE (role, status) ON memberships TO cfdt_juris_app;

GRANT SELECT ON collectivities, documents, document_versions, document_relations TO cfdt_juris_app;

GRANT SELECT ON invitations TO cfdt_juris_app;
GRANT INSERT (organization_id, email_normalized, role, invited_by, status, token_hash, expires_at) ON invitations TO cfdt_juris_app;
GRANT UPDATE (status) ON invitations TO cfdt_juris_app;

GRANT SELECT ON organization_settings TO cfdt_juris_app;
GRANT INSERT (organization_id) ON organization_settings TO cfdt_juris_app;
GRANT SELECT ON subscriptions TO cfdt_juris_app;
GRANT INSERT (organization_id, plan_code, status, provider, provider_customer_id, provider_subscription_id,
  current_period_end, cancel_at_period_end, admin_note, updated_at) ON subscriptions TO cfdt_juris_app;
GRANT UPDATE (provider, provider_customer_id, provider_subscription_id, plan_code, status,
  current_period_end, cancel_at_period_end, free_access_until, admin_note, updated_at) ON subscriptions TO cfdt_juris_app;
GRANT UPDATE (plan_code) ON organizations TO cfdt_juris_app;
GRANT SELECT, INSERT ON billing_webhook_events TO cfdt_juris_app;

GRANT INSERT (organization_id, actor_user_id, event_type, target_type, target_id, metadata) ON audit_events TO cfdt_juris_app;

-- V3.3 document management and collectivity administration
GRANT INSERT (organization_id, collectivity_id, title, document_type, official_number, adopted_at, published_at, effective_from, effective_to, official_url, storage_key, sha256, validation_status, annexes_complete, uploaded_by, original_filename, mime_type, file_size_bytes) ON documents TO cfdt_juris_app;
GRANT UPDATE (title, document_type, official_number, adopted_at, published_at, effective_from, effective_to, official_url, validation_status, validated_by, validated_at, validation_note, storage_key, sha256, annexes_complete, original_filename, mime_type, file_size_bytes) ON documents TO cfdt_juris_app;
GRANT INSERT (organization_id, document_id, version_number, storage_key, sha256, source_url, effective_from, effective_to, original_filename, mime_type, file_size_bytes, uploaded_by) ON document_versions TO cfdt_juris_app;
GRANT INSERT (organization_id, code, name) ON collectivities TO cfdt_juris_app;
GRANT UPDATE (name) ON collectivities TO cfdt_juris_app;

-- V3.4 malware scan metadata and tenant-scoped extracted text index
GRANT SELECT (scan_status, scan_engine, scanned_at) ON documents TO cfdt_juris_app;
GRANT INSERT (organization_id, id, collectivity_id, title, document_type, official_number, adopted_at, published_at, effective_from, effective_to, official_url, storage_key, sha256, validation_status, uploaded_by, original_filename, mime_type, file_size_bytes, scan_status, scan_engine, scanned_at) ON documents TO cfdt_juris_app;
GRANT UPDATE (scan_status, scan_engine, scanned_at) ON documents TO cfdt_juris_app;
GRANT INSERT (organization_id, document_id, version_number, storage_key, sha256, source_url, effective_from, effective_to, original_filename, mime_type, file_size_bytes, uploaded_by, scan_status, scan_engine, scanned_at) ON document_versions TO cfdt_juris_app;
GRANT SELECT, INSERT ON document_text TO cfdt_juris_app;
GRANT UPDATE (sha256, extracted_text, extraction_status) ON document_text TO cfdt_juris_app;
GRANT UPDATE (scan_status, scan_engine, scanned_at) ON document_versions TO cfdt_juris_app;

-- V3.21 national legal knowledge base is shared/read-only for the runtime API role.
GRANT SELECT ON legal_documents,legal_document_versions,legal_chunks,legal_document_relations,legal_ingestion_runs TO cfdt_juris_app;

-- The application runtime must never read or modify the migration ledger.
REVOKE ALL ON schema_migrations FROM cfdt_juris_app;

-- Dedicated ingestion role: write access only to the shared official legal corpus.
GRANT SELECT, INSERT, UPDATE, DELETE
  ON legal_documents, legal_document_versions, legal_chunks, legal_document_relations, legal_ingestion_runs
  TO cfdt_juris_ingest;

