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



def test_personal_zip_import_streams_entries_and_scans_with_bounded_concurrency():
    from app.personal_documents import import_personal_documents_zip
    source = inspect.getsource(import_personal_documents_zip)
    assert "archive.open(info)" in source
    assert "asyncio.to_thread" in source
    assert "asyncio.Semaphore(8)" in source
    assert "MAX_ARCHIVE_DOCUMENTS = 50" in inspect.getsource(__import__("app.personal_documents", fromlist=["MAX_ARCHIVE_DOCUMENTS"]))



def test_personal_documents_are_retrieved_only_with_verified_owner_scope():
    from app.orchestrator import LegalOrchestrator
    from app.main import _ai_safe_conversation_history
    import inspect

    source = inspect.getsource(LegalOrchestrator.ask)
    assert "personal_user_id" in source
    assert "owner_user_id=$1::uuid" in source
    assert "PERSONAL_DOCUMENT" in source
    assert "claim_eligible" in source
    assert "sources.extend(personal_sources)" in source

    history = _ai_safe_conversation_history([{
        "role": "assistant",
        "content": "Private local document answer",
        "metadata": {
            "contains_local_documents": True,
            "sources": [{"source_type": "PERSONAL_DOCUMENT"}],
        },
    }])
    assert history == []


def test_chat_attachment_ids_are_bounded_and_require_per_request_transfer_consent():
    from uuid import uuid4
    import pytest
    from pydantic import ValidationError
    from app.schemas import AskRequest

    document_id = uuid4()
    with pytest.raises(ValidationError):
        AskRequest(question="Analyse ce document", personal_document_ids=[document_id])

    request = AskRequest(
        question="Analyse ce document",
        personal_document_ids=[document_id],
        confirm_personal_document_ai_transfer=True,
    )
    assert request.personal_document_ids == [document_id]

    with pytest.raises(ValidationError):
        AskRequest(
            question="Analyse ces documents",
            personal_document_ids=[uuid4() for _ in range(6)],
            confirm_personal_document_ai_transfer=True,
        )


def test_chat_personal_document_retrieval_is_limited_to_attached_ids_when_provided():
    from app.orchestrator import LegalOrchestrator
    source = inspect.getsource(LegalOrchestrator.ask)
    assert "id=ANY($2::uuid[])" in source
    assert "request.personal_document_ids" in source
    assert "owner_user_id=$1::uuid" in source


def test_personal_upload_offloads_antivirus_and_text_extraction_from_asgi_loop():
    source = inspect.getsource(upload_personal_document)
    assert "await asyncio.to_thread(" in source
    assert "scan_with_clamav" in source
    assert "extract_document_text" in source


def test_chat_attachment_analysis_fails_closed_when_feature_is_disabled():
    from app.main import ask
    source = inspect.getsource(ask)
    assert "payload.personal_document_ids" in source
    assert "settings.ai_local_documents_in_chat_enabled" in source
    assert "aucun document n'a été transmis" in source


def test_selected_attachments_are_loaded_by_owner_id_and_bounded_excerpt():
    from app.orchestrator import LegalOrchestrator
    source = inspect.getsource(LegalOrchestrator.ask)
    assert "id=ANY($2::uuid[])" in source
    assert "left(extracted_text,6000)" in source
    assert "request.personal_document_ids" in source
    assert "owner_user_id=$1::uuid" in source


def test_personal_attachment_consent_is_independent_from_employer_document_consent():
    from app.orchestrator import LegalOrchestrator
    source = inspect.getsource(LegalOrchestrator.ask)
    assert "if allow_personal_documents else \"NOT_TRANSMITTED\"" in source
    assert "if allow_personal_documents" in source
