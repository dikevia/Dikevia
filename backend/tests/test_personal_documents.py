import inspect

from app.main import app
from app.personal_documents import (
    get_personal_user_context,
    list_personal_documents,
    search_personal_documents,
    upload_personal_document,
)


def test_personal_document_routes_are_registered():
    paths = set(app.openapi()["paths"])
    assert "/api/v1/personal-documents" in paths
    assert "/api/v1/personal-documents/search" in paths
    assert "/api/v1/personal-documents/import-zip" in paths
    assert "/api/v1/personal-documents/{document_id}/download" in paths
    assert "/api/v1/personal-documents/{document_id}" in paths


def test_personal_document_identity_is_resolved_from_oidc_not_email_or_tenant():
    source = inspect.getsource(get_personal_user_context)
    assert "principal.issuer" in source
    assert "principal.subject" in source
    assert "WHERE oidc_issuer=$1 AND oidc_subject=$2" in source
    assert "email" not in source.lower().split("where oidc_issuer", 1)[-1]
    assert "app.current_user_id" in source


def test_personal_document_queries_always_filter_by_owner():
    sources = [
        inspect.getsource(list_personal_documents),
        inspect.getsource(search_personal_documents),
        inspect.getsource(upload_personal_document),
    ]
    combined = "\n".join(sources)
    assert "owner_user_id=$1::uuid" in combined
    assert "ctx.user_id" in combined
    assert "scan_status='CLEAN'" in combined
    assert "extraction_status='EXTRACTED'" in combined


def test_personal_document_migration_has_forced_owner_rls_and_no_org_scope():
    from pathlib import Path

    migration = (
        Path(__file__).resolve().parents[2]
        / "database"
        / "migrations"
        / "028_personal_user_documents.sql"
    ).read_text(encoding="utf-8")
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "owner_user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid" in migration
    assert "GRANT SELECT, INSERT, DELETE ON personal_documents TO cfdt_juris_app" in migration
    assert "organization_id" not in migration



def test_personal_zip_import_is_bounded_and_rejects_unsafe_archive_entries():
    from app.personal_documents import import_personal_documents_zip
    source = inspect.getsource(import_personal_documents_zip)
    assert "MAX_ZIP_BYTES" in source
    assert "MAX_ARCHIVE_DOCUMENTS" in source
    assert "MAX_ARCHIVE_UNCOMPRESSED_BYTES" in source
    assert "path.is_absolute()" in source
    assert "part in {\"\", \".\", \"..\"}" in source
    assert "scan_with_clamav" in source
    assert "owner_user_id" in source
