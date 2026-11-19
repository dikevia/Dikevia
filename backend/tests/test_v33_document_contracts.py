from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_v33_document_routes_are_tenant_scoped_and_role_protected():
    main = (ROOT / "backend/app/main.py").read_text()
    assert '@app.post("/api/v1/documents",status_code=201)' in main
    assert 'ctx: TenantContext = Depends(require_legal_editor_for_external)' in main
    dependencies = (ROOT / "backend/app/dependencies.py").read_text()
    assert "async def require_legal_editor_for_external(" in dependencies
    assert 'if ctx.role not in ("ORG_ADMIN", "LEGAL_EDITOR")' in dependencies
    assert 'Depends(get_tenant_context_for_chat)' in main
    assert '@app.post("/api/v1/documents/{document_id}/versions",status_code=201)' in main
    assert '@app.get("/api/v1/documents/{document_id}/download")' in main
    assert 'WHERE id=$1::uuid AND organization_id=$2::uuid' in main
    assert "load_private_document(row[\"storage_key\"]" in main
    assert "read_private_file, store_private_file" in main


def test_v33_rejects_unexpected_formats_and_limits_upload_size():
    main = (ROOT / "backend/app/main.py").read_text()
    assert 'ext not in (".pdf", ".docx")' in main
    assert 'data.startswith(b"%PDF-")' in main
    assert '"word/document.xml"' in main
    assert 'MAX_DOCUMENT_BYTES' in main
    assert 'hashlib.sha256(data).hexdigest()' in main


def test_v33_validation_is_not_automatic_on_upload():
    main = (ROOT / "backend/app/main.py").read_text()
    assert "'COLLECTED_UNVERIFIED'" in main
    assert "Une justification est obligatoire pour une validation juridique." in main
    assert "validated_by=$5::uuid" in main


def test_v33_migration_adds_metadata_and_minimal_runtime_grants():
    sql = (ROOT / "database/migrations/004_document_management.sql").read_text()
    for column in ("original_filename", "mime_type", "file_size_bytes", "uploaded_by", "validation_note"):
        assert column in sql
    grants = (ROOT / "database/grant_runtime_permissions.sql").read_text()
    assert "GRANT INSERT" in grants
    assert "GRANT UPDATE" in grants


def test_v33_docker_uses_a_separate_persistent_private_volume():
    compose = (ROOT / "deploy/docker-compose.yml").read_text()
    assert "document_data:/var/lib/cfdt-juris/documents" in compose
    assert "  document_data:" in compose


def test_v33_migration_does_not_assume_runtime_role_exists():
    sql = (ROOT / "database/migrations/004_document_management.sql").read_text()
    assert "GRANT " not in sql
    assert "privileges are applied separately" in sql
