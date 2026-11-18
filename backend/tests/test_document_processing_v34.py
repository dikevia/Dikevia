from io import BytesIO
import socket
import struct
import threading
import zipfile

import pytest

from app.document_processing import (
    MalwareDetected,
    ScannerUnavailable,
    document_sha256_matches,
    extract_document_text,
    scan_with_clamav,
)

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def make_docx(text: str) -> bytes:
    document_xml = (
        "<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>"
        f"<w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>"
    )
    return make_docx_xml(document_xml)


def make_docx_xml(document_xml: str) -> bytes:
    out = BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'/>")
        archive.writestr("word/document.xml", document_xml)
    return out.getvalue()


def fake_clamd(response: bytes):
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]

    def serve():
        conn, _ = listener.accept()
        with conn:
            command = conn.recv(10)
            assert command == b"zINSTREAM\0"
            while True:
                header = conn.recv(4)
                if len(header) != 4:
                    break
                size = struct.unpack("!I", header)[0]
                if size == 0:
                    break
                remaining = size
                while remaining:
                    chunk = conn.recv(min(remaining, 65536))
                    if not chunk:
                        return
                    remaining -= len(chunk)
            conn.sendall(response)
        listener.close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    return port, thread


def test_docx_text_is_extracted():
    text, status = extract_document_text(make_docx("Code général des collectivités territoriales"), DOCX_MIME)
    assert status == "EXTRACTED"
    assert "collectivités" in text


def test_docx_without_text_is_marked_no_text():
    text, status = extract_document_text(make_docx(""), DOCX_MIME)
    assert text == ""
    assert status == "NO_TEXT"


def test_docx_internal_entity_is_rejected():
    xml = """<!DOCTYPE w:document [<!ENTITY injected "must not be extracted">]>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body><w:p><w:r><w:t>&injected;</w:t></w:r></w:p></w:body>
    </w:document>"""
    text, status = extract_document_text(make_docx_xml(xml), DOCX_MIME)
    assert text == ""
    assert status == "FAILED"


def test_clamav_clean_response():
    port, thread = fake_clamd(b"stream: OK\0")
    result = scan_with_clamav(b"sample", "127.0.0.1", port, 2)
    thread.join(timeout=2)
    assert result.status == "CLEAN"
    assert result.engine == "ClamAV"


def test_clamav_infected_response_fails_upload():
    port, thread = fake_clamd(b"stream: Eicar-Test-Signature FOUND\0")
    with pytest.raises(MalwareDetected):
        scan_with_clamav(b"sample", "127.0.0.1", port, 2)
    thread.join(timeout=2)


def test_missing_clamav_configuration_fails_closed():
    with pytest.raises(ScannerUnavailable):
        scan_with_clamav(b"sample", "", 3310, 1)


def test_v34_database_migration_enables_tenant_rls_and_full_text_index():
    from pathlib import Path
    root = Path(__file__).parents[2]
    sql = (root / "database/migrations/005_document_scanning_and_search.sql").read_text()
    assert "ALTER TABLE document_text FORCE ROW LEVEL SECURITY" in sql
    assert "USING (organization_id = NULLIF(current_setting('app.current_org_id'" in sql
    assert "USING GIN(search_vector)" in sql


def test_search_route_is_registered_before_dynamic_document_id_route():
    from pathlib import Path
    main = (Path(__file__).parents[1] / "app/main.py").read_text()
    assert main.index('@app.get("/api/v1/documents/search")') < main.index('@app.get("/api/v1/documents/{document_id}")')
    assert "scan_uploaded_bytes(data)" in main
    assert "Le contrôle antivirus est indisponible" in main
    assert '@app.post("/api/v1/documents/{document_id}/rescan")' in main
    assert '@app.post("/api/v1/documents/{document_id}/reindex")' in main


def test_v34_runtime_grants_cover_scan_and_reindex_operations():
    from pathlib import Path
    root = Path(__file__).parents[2]
    grants = (root / "database/grant_runtime_permissions.sql").read_text()
    assert "GRANT UPDATE (scan_status, scan_engine, scanned_at) ON document_versions" in grants
    assert "GRANT UPDATE (sha256, extracted_text, extraction_status) ON document_text" in grants


def test_postgres_rls_integration_covers_extracted_text_isolation():
    from pathlib import Path
    test_file = (Path(__file__).parent / "test_postgres_rls_integration.py").read_text()
    assert "SELECT document_id,extracted_text FROM document_text" in test_file
    assert "organisation B" in test_file


def test_document_integrity_matches_original_sha256():
    import hashlib

    data = b"original legal document"
    digest = hashlib.sha256(data).hexdigest()
    assert document_sha256_matches(data, digest)
    assert not document_sha256_matches(data + b" altered", digest)
    assert not document_sha256_matches(data, None)
    assert not document_sha256_matches(data, "invalid")


def test_document_routes_check_storage_digest_before_use():
    from pathlib import Path

    main = (Path(__file__).parents[1] / "app/main.py").read_text()
    assert "document_sha256_matches(data, row[\"sha256\"])" in main
    assert "Le fichier a été modifié ou corrompu dans le stockage privé" in main
    assert "Une version a été modifiée ou corrompue dans le stockage privé" in main
    assert '"scan_engine":"INTEGRITY_CHECK"' in main


def test_private_storage_uses_restrictive_unix_permissions():
    from pathlib import Path

    storage = (Path(__file__).parents[1] / "app/document_storage.py").read_text()
    assert "os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600" in storage
    assert "os.chmod(document_dir, 0o700)" in storage
    assert "os.chmod(path, 0o600)" in storage
    assert "os.fsync(stream.fileno())" in storage


def test_document_download_returns_the_verified_bytes_not_a_second_file_read():
    from pathlib import Path

    main = (Path(__file__).parents[1] / "app/main.py").read_text()
    assert "return Response(content=data,media_type=row[\"mime_type\"]" in main
    assert "filename*=UTF-8''{quote(filename)}" in main
    assert "return FileResponse(path" not in main


def test_document_rescan_preserves_integrity_failure_engine():
    from pathlib import Path

    main = (Path(__file__).parents[1] / "app/main.py").read_text()
    assert 'current_engine=current_item["scan_engine"]' in main
    assert "scan_engine=$4,scanned_at=now()" in main



def test_document_version_number_is_allocated_under_document_row_lock():
    from pathlib import Path

    main = (Path(__file__).parents[1] / "app/main.py").read_text()
    route = main.split('@app.post("/api/v1/documents/{document_id}/versions"', 1)[1].split(
        '@app.get("/api/v1/documents/{document_id}/versions"', 1
    )[0]
    transaction_start = route.index("async with ctx.conn.transaction():")
    lock_position = route.index("FOR UPDATE")
    version_position = route.index("COALESCE(max(version_number),0)+1")
    file_position = route.index("store_private_file,")
    insert_position = route.index("INSERT INTO document_versions")
    assert transaction_start < lock_position < version_position < file_position < insert_position
    assert "storage_key=None" in route
    assert "if storage_key:" in route
