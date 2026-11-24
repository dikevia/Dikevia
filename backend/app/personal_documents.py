"""Strictly user-owned private document storage and search endpoints."""
from __future__ import annotations

import asyncio
import hashlib
import re
import zipfile
from io import BytesIO
import stat
from dataclasses import dataclass
from datetime import date
from pathlib import PurePath
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from .config import settings
from .db import get_pool
from .dependencies import get_principal
from .document_processing import (
    MalwareDetected, ScannerUnavailable, document_sha256_matches,
    extract_document_text, scan_with_clamav,
)
from .document_storage import (
    StorageError, StorageNotFound, delete_private_file, read_private_file,
    store_private_file,
)
from .security import Principal

router = APIRouter(prefix="/api/v1/personal-documents", tags=["personal-documents"])
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_ZIP_BYTES = 60 * 1024 * 1024
MAX_ARCHIVE_DOCUMENTS = 50
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 120 * 1024 * 1024
ALLOWED = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@dataclass
class PersonalUserContext:
    principal: Principal
    user_id: str
    conn: object


async def get_personal_user_context(principal: Principal = Depends(get_principal)):
    """Resolve the owner by verified OIDC issuer+subject; never by email or organisation name."""
    async with get_pool().acquire() as conn:
        try:
            await conn.execute(
                """SELECT set_config('app.oidc_issuer',$1,false),
                          set_config('app.oidc_subject',$2,false),
                          set_config('app.current_user_id','',false)""",
                principal.issuer, principal.subject,
            )
            async with conn.transaction():
                row = await conn.fetchrow(
                    """SELECT id FROM users
                       WHERE oidc_issuer=$1 AND oidc_subject=$2 AND status='ACTIVE'""",
                    principal.issuer, principal.subject,
                )
            if not row:
                raise HTTPException(403, "Compte Dikévia actif introuvable pour cette identité.")
            user_id = str(row["id"])
            await conn.execute("SELECT set_config('app.current_user_id',$1,false)", user_id)
            yield PersonalUserContext(principal, user_id, conn)
        finally:
            try:
                await conn.execute(
                    """SELECT set_config('app.oidc_issuer','',false),
                              set_config('app.oidc_subject','',false),
                              set_config('app.current_user_id','',false)"""
                )
            except Exception:
                terminate = getattr(conn, "terminate", None)
                if callable(terminate):
                    terminate()


def _validate_upload(filename: str, mime_type: str, data: bytes) -> tuple[str, str]:
    suffix = PurePath(filename or "").suffix.lower()
    expected = ALLOWED.get(suffix)
    if not expected or mime_type not in {expected, "application/octet-stream"}:
        raise HTTPException(415, "Seuls les fichiers PDF et DOCX sont acceptés.")
    if suffix == ".pdf" and not data.startswith(b"%PDF-"):
        raise HTTPException(415, "Le contenu du fichier ne correspond pas à un PDF.")
    if suffix == ".docx":
        import zipfile
        from io import BytesIO
        try:
            with zipfile.ZipFile(BytesIO(data)) as archive:
                if "word/document.xml" not in archive.namelist():
                    raise ValueError("Missing document body")
        except Exception as exc:
            raise HTTPException(415, "Le fichier DOCX est invalide.") from exc
    return suffix, expected


@router.post("", status_code=201)
async def upload_personal_document(
    file: UploadFile = File(...),
    title: str | None = Form(default=None, max_length=300),
    document_type: str = Form(default="PERSONAL_REFERENCE", max_length=80),
    collectivity_scope: str = Form(default="VILLE_SAINT_ETIENNE"),
    effective_from: date | None = Form(default=None),
    effective_to: date | None = Form(default=None),
    ctx: PersonalUserContext = Depends(get_personal_user_context),
):
    if effective_from and effective_to and effective_to < effective_from:
        raise HTTPException(422, "La date de fin précède la date de début.")
    if collectivity_scope not in {
        "VILLE_SAINT_ETIENNE", "SAINT_ETIENNE_METROPOLE",
        "MIXED_LOCAL_SCOPE", "UNCLASSIFIED",
    }:
        raise HTTPException(422, "Périmètre local invalide.")
    data = await file.read(MAX_FILE_BYTES + 1)
    if not data:
        raise HTTPException(422, "Le fichier est vide.")
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(413, "La taille maximale d'un document est de 20 Mo.")
    suffix, mime_type = _validate_upload(file.filename or "", file.content_type or "", data)
    try:
        scan = scan_with_clamav(data, settings.clamav_host, settings.clamav_port, settings.clamav_timeout_seconds)
    except MalwareDetected as exc:
        raise HTTPException(422, "Le document a été rejeté par le contrôle antivirus.") from exc
    except ScannerUnavailable as exc:
        raise HTTPException(503, "Le contrôle antivirus est indisponible ; aucun document n'a été enregistré.") from exc

    extracted_text, extraction_status = extract_document_text(data, mime_type)
    digest = hashlib.sha256(data).hexdigest()
    document_id = uuid4()
    storage_key = None
    try:
        storage_key = store_private_file(
            ctx.user_id, str(document_id), 1, data, suffix, mime_type,
        )
        row = await ctx.conn.fetchrow(
            """INSERT INTO personal_documents(
                id,owner_user_id,title,document_type,original_filename,mime_type,
                file_size_bytes,storage_key,sha256,scan_status,scan_engine,scanned_at,
                extraction_status,extracted_text,collectivity_scope,effective_from,effective_to
            ) VALUES(
                $1::uuid,$2::uuid,$3,$4,$5,$6,$7,$8,$9,'CLEAN',$10,now(),
                $11,$12,$13,$14,$15
            ) RETURNING id,title,document_type,original_filename,file_size_bytes,
                sha256,scan_status,extraction_status,collectivity_scope,created_at""",
            str(document_id), ctx.user_id,
            (title or PurePath(file.filename or "Document personnel").stem).strip()[:300],
            (document_type or "PERSONAL_REFERENCE").strip()[:80],
            (file.filename or "document")[:250], mime_type, len(data), storage_key, digest,
            scan.engine, extraction_status, extracted_text, collectivity_scope,
            effective_from, effective_to,
        )
    except Exception:
        if storage_key:
            try:
                delete_private_file(storage_key)
            except StorageError:
                pass
        raise
    return {**dict(row), "id": str(row["id"]), "created_at": row["created_at"].isoformat()}



@router.post("/import-zip", status_code=201)
async def import_personal_documents_zip(
    file: UploadFile = File(...),
    ctx: PersonalUserContext = Depends(get_personal_user_context),
):
    """Import a bounded ZIP archive into the authenticated user's private corpus."""
    archive_bytes = await file.read(MAX_ZIP_BYTES + 1)
    if not archive_bytes or len(archive_bytes) > MAX_ZIP_BYTES:
        raise HTTPException(413, "Archive vide ou supérieure à 60 Mo.")
    try:
        archive = zipfile.ZipFile(BytesIO(archive_bytes))
    except (zipfile.BadZipFile, OSError) as exc:
        raise HTTPException(415, "Archive ZIP invalide.") from exc

    prepared = []
    seen_names = set()
    total_uncompressed = 0
    try:
        with archive:
            infos = [info for info in archive.infolist() if not info.is_dir()]
            if not infos or len(infos) > MAX_ARCHIVE_DOCUMENTS:
                raise HTTPException(422, "L'archive doit contenir entre 1 et 100 documents.")
            for info in infos:
                raw_name = info.filename.replace("\\", "/")
                path = PurePath(raw_name)
                if (
                    path.is_absolute()
                    or len(path.parts) != 1
                    or any(part in {"", ".", ".."} for part in path.parts)
                    or "\x00" in raw_name
                    or stat.S_ISLNK(info.external_attr >> 16)
                    or info.flag_bits & 0x1
                ):
                    raise HTTPException(422, "L'archive contient un chemin ou un fichier interdit.")
                filename = path.name
                suffix = PurePath(filename).suffix.lower()
                if suffix not in ALLOWED:
                    raise HTTPException(415, "L'archive ne doit contenir que des PDF ou DOCX.")
                if filename.casefold() in seen_names:
                    raise HTTPException(422, "L'archive contient des noms de fichiers en doublon.")
                seen_names.add(filename.casefold())
                if (
                    info.file_size <= 0
                    or info.file_size > MAX_FILE_BYTES
                    or info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
                    or (info.compress_size == 0 and info.file_size > 0)
                    or (info.compress_size and info.file_size / info.compress_size > 100)
                ):
                    raise HTTPException(413, "Un document dépasse les limites de taille ou de compression.")
                total_uncompressed += info.file_size
                if total_uncompressed > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                    raise HTTPException(413, "Le volume total décompressé dépasse 120 Mo.")
                try:
                    chunks = []
                    extracted_size = 0
                    with archive.open(info) as entry:
                        while True:
                            chunk = entry.read(min(1024 * 1024, MAX_FILE_BYTES + 1 - extracted_size))
                            if not chunk:
                                break
                            extracted_size += len(chunk)
                            if extracted_size > info.file_size or extracted_size > MAX_FILE_BYTES:
                                raise HTTPException(413, "Un document dépasse sa taille déclarée.")
                            chunks.append(chunk)
                    data = b"".join(chunks)
                except HTTPException:
                    raise
                except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
                    raise HTTPException(415, "Un document de l'archive est illisible.") from exc
                if len(data) != info.file_size:
                    raise HTTPException(415, "La taille d'un document extrait est incohérente.")
                mime_type = ALLOWED[suffix]
                _validate_upload(filename, mime_type, data)
                extracted_text, extraction_status = extract_document_text(data, mime_type)
                prepared.append({
                    "id": uuid4(),
                    "filename": filename,
                    "title": PurePath(filename).stem[:300],
                    "mime_type": mime_type,
                    "data": data,
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "extracted_text": extracted_text,
                    "extraction_status": extraction_status,
                })
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(415, "L'archive n'a pas pu être contrôlée.") from exc

    # Run bounded concurrent scans so a 49-document archive does not incur
    # one network round-trip per file serially. Any scanner failure rejects all.
    scan_semaphore = asyncio.Semaphore(8)

    async def scan_one(item):
        async with scan_semaphore:
            return await asyncio.to_thread(
                scan_with_clamav, item["data"], settings.clamav_host,
                settings.clamav_port, settings.clamav_timeout_seconds,
            )

    scan_results = await asyncio.gather(
        *(scan_one(item) for item in prepared), return_exceptions=True,
    )
    for result in scan_results:
        if isinstance(result, MalwareDetected):
            raise HTTPException(422, "Un document a été rejeté par le contrôle antivirus.")
        if isinstance(result, ScannerUnavailable):
            raise HTTPException(503, "Le contrôle antivirus est indisponible ; aucun document n'a été importé.")
        if isinstance(result, BaseException):
            raise HTTPException(503, "Le contrôle antivirus n'a pas pu terminer l'analyse.")
    for item, scan in zip(prepared, scan_results):
        item["scan_engine"] = scan.engine

    stored_keys = []
    documents = []
    try:
        async with ctx.conn.transaction():
            for item in prepared:
                storage_key = store_private_file(
                    ctx.user_id, str(item["id"]), 1, item["data"],
                    PurePath(item["filename"]).suffix.lower(), item["mime_type"],
                )
                stored_keys.append(storage_key)
                row = await ctx.conn.fetchrow(
                    """INSERT INTO personal_documents(
                        id,owner_user_id,title,document_type,original_filename,mime_type,
                        file_size_bytes,storage_key,sha256,scan_status,scan_engine,scanned_at,
                        extraction_status,extracted_text,collectivity_scope
                    ) VALUES(
                        $1::uuid,$2::uuid,$3,'PERSONAL_REFERENCE',$4,$5,$6,$7,$8,
                        'CLEAN',$9,now(),$10,$11,'UNCLASSIFIED'
                    ) RETURNING id,title,original_filename,file_size_bytes,scan_status,
                        extraction_status,collectivity_scope,created_at""",
                    str(item["id"]), ctx.user_id, item["title"], item["filename"],
                    item["mime_type"], len(item["data"]), storage_key, item["sha256"],
                    item["scan_engine"], item["extraction_status"], item["extracted_text"],
                )
                documents.append({
                    **dict(row), "id": str(row["id"]),
                    "created_at": row["created_at"].isoformat(),
                })
    except Exception:
        for storage_key in stored_keys:
            try:
                delete_private_file(storage_key)
            except StorageError:
                pass
        raise
    return {"imported_count": len(documents), "documents": documents}


@router.get("")
async def list_personal_documents(ctx: PersonalUserContext = Depends(get_personal_user_context)):
    rows = await ctx.conn.fetch(
        """SELECT id,title,document_type,original_filename,file_size_bytes,sha256,
                  scan_status,extraction_status,collectivity_scope,effective_from,
                  effective_to,validation_status,created_at
           FROM personal_documents
           WHERE owner_user_id=$1::uuid
           ORDER BY created_at DESC LIMIT 500""",
        ctx.user_id,
    )
    return [{
        **dict(row), "id": str(row["id"]),
        "effective_from": row["effective_from"].isoformat() if row["effective_from"] else None,
        "effective_to": row["effective_to"].isoformat() if row["effective_to"] else None,
        "created_at": row["created_at"].isoformat(),
    } for row in rows]


@router.get("/search")
async def search_personal_documents(
    q: str, limit: int = 8,
    ctx: PersonalUserContext = Depends(get_personal_user_context),
):
    if len(q.strip()) < 2 or len(q) > 500 or not 1 <= limit <= 20:
        raise HTTPException(422, "Recherche invalide.")
    rows = await ctx.conn.fetch(
        """SELECT id,title,document_type,collectivity_scope,validation_status,
                  effective_from,effective_to,extraction_status,
                  ts_rank(search_vector,plainto_tsquery('french',$2)) relevance,
                  ts_headline('french',extracted_text,plainto_tsquery('french',$2),
                    'MaxWords=90,MinWords=20,ShortWord=2,HighlightAll=false') excerpt
           FROM personal_documents
           WHERE owner_user_id=$1::uuid AND scan_status='CLEAN'
             AND extraction_status='EXTRACTED'
             AND search_vector @@ plainto_tsquery('french',$2)
           ORDER BY relevance DESC,created_at DESC LIMIT $3""",
        ctx.user_id, q.strip()[:500], limit,
    )
    return [{
        "id": str(row["id"]), "title": row["title"],
        "document_type": row["document_type"],
        "collectivity_scope": row["collectivity_scope"],
        "validation_status": row["validation_status"],
        "effective_from": row["effective_from"].isoformat() if row["effective_from"] else None,
        "effective_to": row["effective_to"].isoformat() if row["effective_to"] else None,
        "relevance": float(row["relevance"]),
        "excerpt": re.sub(r"</?b>", "", row["excerpt"] or "", flags=re.IGNORECASE),
    } for row in rows]


@router.get("/{document_id}/download")
async def download_personal_document(
    document_id: str, ctx: PersonalUserContext = Depends(get_personal_user_context),
):
    try:
        UUID(document_id)
    except ValueError as exc:
        raise HTTPException(400, "Identifiant de document invalide.") from exc
    row = await ctx.conn.fetchrow(
        """SELECT storage_key,original_filename,mime_type,sha256,scan_status
           FROM personal_documents WHERE id=$1::uuid AND owner_user_id=$2::uuid""",
        document_id, ctx.user_id,
    )
    if not row:
        raise HTTPException(404, "Document personnel introuvable.")
    if row["scan_status"] != "CLEAN":
        raise HTTPException(423, "Document non validé par le contrôle antivirus.")
    try:
        data = read_private_file(row["storage_key"])
    except StorageNotFound as exc:
        raise HTTPException(404, "Fichier personnel introuvable dans le stockage privé.") from exc
    except StorageError as exc:
        raise HTTPException(503, "Stockage privé indisponible.") from exc
    if not document_sha256_matches(data, row["sha256"]):
        raise HTTPException(409, "L'intégrité du document personnel ne peut pas être vérifiée.")
    from urllib.parse import quote
    filename = row["original_filename"] or "document"
    return Response(content=data, media_type=row["mime_type"], headers={
        "Content-Disposition": f'attachment; filename="document"; filename*=UTF-8\'\'{quote(filename)}',
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
    })


@router.delete("/{document_id}", status_code=204)
async def delete_personal_document(
    document_id: str, ctx: PersonalUserContext = Depends(get_personal_user_context),
):
    try:
        UUID(document_id)
    except ValueError as exc:
        raise HTTPException(400, "Identifiant de document invalide.") from exc
    row = await ctx.conn.fetchrow(
        """DELETE FROM personal_documents
           WHERE id=$1::uuid AND owner_user_id=$2::uuid
           RETURNING storage_key""",
        document_id, ctx.user_id,
    )
    if not row:
        raise HTTPException(404, "Document personnel introuvable.")
    try:
        delete_private_file(row["storage_key"])
    except StorageError as exc:
        # The database row is already gone, so the object is unreachable via the API.
        raise HTTPException(503, "Le document est supprimé de l'index mais son objet privé doit être purgé.") from exc
    return Response(status_code=204)
