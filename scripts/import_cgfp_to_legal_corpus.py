#!/usr/bin/env python3
"""Importe l'index article par article du snapshot CGFP dans le corpus national.

Par défaut, le script valide le fichier et affiche un aperçu sans écrire.
L'écriture nécessite --apply et LEGAL_CORPUS_INGEST_DATABASE_URL. Les articles sont volontairement
importés avec un statut temporel UNKNOWN : un snapshot consolidé ne prouve pas
la version applicable à une date historique.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse
from typing import Any

ARTICLE_RE = re.compile(r"^[LDR]\d+(?:-\d+)*$")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.cgfp import clean_cgfp_article_text  # noqa: E402
DEFAULT_INDEX = ROOT / "corpus_national/index/CGFP_articles_2026-10-31.json"


def validate_ingest_dsn(dsn: str) -> None:
    """Refuse toute écriture avec le rôle applicatif ou un compte DBA."""
    parsed = urlparse(dsn)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ValueError("Le DSN d'import doit être une URL PostgreSQL.")
    if parsed.username != "cfdt_juris_ingest":
        raise ValueError(
            "Refus d'import : utiliser exclusivement le rôle dédié cfdt_juris_ingest."
        )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def split_text(text: str, size: int = 4200, overlap: int = 300) -> list[str]:
    text = text.strip()
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            boundary = text.rfind("\n", start + size // 2, end)
            if boundary > start:
                end = boundary
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return chunks


def load_snapshot(index_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    data = json.loads(index_path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not isinstance(data.get("articles"), list):
        raise ValueError("Schéma de l'index CGFP absent ou non pris en charge.")
    if not data.get("source_id") or not data.get("source_sha256"):
        raise ValueError("Provenance ou empreinte du snapshot absente.")
    source_file = data.get("source_file")
    if (
        not isinstance(source_file, str)
        or not source_file.lower().endswith(".pdf")
        or Path(source_file).name != source_file
    ):
        raise ValueError("Nom de PDF source invalide dans les métadonnées de l'index.")
    pdf_path = index_path.parent.parent / "legislation" / source_file
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF source introuvable : {pdf_path}")
    actual_pdf_hash = sha256_file(pdf_path)
    if actual_pdf_hash != data["source_sha256"]:
        raise ValueError("L'empreinte SHA-256 du PDF ne correspond pas aux métadonnées de l'index.")
    try:
        from pypdf import PdfReader
        pdf_page_count = len(PdfReader(str(pdf_path)).pages)
    except Exception as exc:
        raise ValueError("Le PDF source ne peut pas être lu pour vérifier sa pagination.") from exc
    articles = data["articles"]
    if data.get("article_count") != len(articles):
        raise ValueError("Le nombre d'articles ne correspond pas au compteur déclaré dans l'index.")
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for row in articles:
        ref = re.sub(r"\s+", "", str(row.get("article", ""))).upper()
        text = str(row.get("text") or "").strip()
        try:
            page_start, page_end = int(row["page_start"]), int(row["page_end"])
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"Pagination invalide pour l'article {ref or '(inconnu)'}.")
        if not ARTICLE_RE.fullmatch(ref):
            raise ValueError(f"Référence d'article invalide : {ref!r}")
        if ref in seen:
            raise ValueError(f"Référence d'article en doublon : {ref}")
        if not text:
            raise ValueError(f"Texte vide pour l'article {ref}.")
        if page_start < 1 or page_end < page_start or page_end > pdf_page_count:
            raise ValueError(f"Pagination incohérente ou hors PDF pour l'article {ref}.")
        seen.add(ref)
        normalized.append({
            "article": ref, "text": text,
            "page_start": page_start, "page_end": page_end,
        })
    if not normalized:
        raise ValueError("L'index CGFP ne contient aucun article importable.")
    return data, normalized


async def import_snapshot(dsn: str, metadata: dict[str, Any], articles: list[dict[str, Any]]) -> dict[str, int]:
    try:
        import asyncpg
    except ImportError as exc:
        raise RuntimeError("Dépendance asyncpg absente. Installer backend/requirements.txt.") from exc

    conn = await asyncpg.connect(dsn, command_timeout=120)
    inserted_versions = 0
    inserted_chunks = 0
    chunk_rows: list[tuple[Any, int, str, str]] = []
    try:
        async with conn.transaction():
            source_policy = await conn.fetchrow("""
                SELECT metadata_ingestion_allowed,full_text_ingestion_allowed
                FROM legal_source_registry WHERE source_key='CGFP_SNAPSHOT'
            """)
            if not source_policy or not source_policy["metadata_ingestion_allowed"] or not source_policy["full_text_ingestion_allowed"]:
                raise ValueError(
                    "Import CGFP bloqué : la provenance/licence de l'instantané doit être validée dans le registre des sources."
                )
            for article in articles:
                ref = article["article"]
                source_id = f'{metadata["source_id"]}:{ref}'
                title = f"Code général de la fonction publique — article {ref}"
                text = clean_cgfp_article_text(article["text"])
                if not text:
                    raise ValueError("Texte vide après nettoyage pour l'article " + ref + ".")
                text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
                version_key = f'{metadata["source_id"]}:{metadata["source_sha256"][:16]}:{ref}'
                # Official CGFP code landing page; the exact article reference is stored separately in official_number.
                official_url = "https://www.legifrance.gouv.fr/codes/texte_lc/LEGITEXT000044416551/"
                raw_metadata = {
                    "source_id": metadata["source_id"],
                    "source_file": metadata["source_file"],
                    "snapshot_modified_at": metadata.get("snapshot_modified_at"),
                    "generated_at": metadata.get("generated_at"),
                    "snapshot_sha256": metadata["source_sha256"],
                    "article": ref,
                    "page_start": article["page_start"],
                    "page_end": article["page_end"],
                    "verification_status": "SNAPSHOT_NOT_LIVE_VERIFIED",
                    "temporal_scope": "CURRENT_CODE_SNAPSHOT",
                    "snapshot_scope_note": "Snapshot du CGFP ; aucune version historique n'est certifiée par cet import.",
                }
                version = await conn.fetchrow("""
                    WITH upserted_document AS (
                      INSERT INTO legal_documents(
                        source_type,source_id,source_key,title,document_kind,publisher,official_url,official_number,
                        status,source_status,raw_metadata,content_sha256,last_seen_at
                      )
                      VALUES('CGFP_SNAPSHOT',$1,'CGFP_SNAPSHOT',$2,'CODE','Légifrance',
                        $8,$9,'UNKNOWN','IMPORTED_UNVERIFIED',$3::jsonb,$4,now())
                      ON CONFLICT(source_type,source_id) DO UPDATE SET
                        source_key=EXCLUDED.source_key,
                        title=EXCLUDED.title,
                        publisher=EXCLUDED.publisher,
                        official_url=EXCLUDED.official_url,
                        official_number=EXCLUDED.official_number,
                        status='UNKNOWN',
                        source_status='IMPORTED_UNVERIFIED',
                        raw_metadata=legal_documents.raw_metadata || EXCLUDED.raw_metadata,
                        content_sha256=EXCLUDED.content_sha256,
                        last_seen_at=now()
                      RETURNING id
                    ),
                    upserted_version AS (
                      INSERT INTO legal_document_versions(
                        document_id,version_key,valid_from,valid_to,version_status,
                        full_text,text_sha256,raw_payload
                      )
                      SELECT id,$5,NULL,NULL,'UNKNOWN',$6,$4,$7::jsonb
                      FROM upserted_document
                      ON CONFLICT(document_id,version_key) DO UPDATE SET
                        full_text=EXCLUDED.full_text,
                        text_sha256=EXCLUDED.text_sha256,
                        version_status='UNKNOWN',
                        raw_payload=legal_document_versions.raw_payload || EXCLUDED.raw_payload,
                        retrieved_at=now()
                      RETURNING id
                    ),
                    deleted_chunks AS (
                      DELETE FROM legal_chunks
                      WHERE version_id IN (SELECT id FROM upserted_version)
                      RETURNING id
                    )
                    SELECT version.id
                    FROM upserted_version AS version
                    WHERE (SELECT count(*) FROM deleted_chunks) >= 0
                """, source_id, title, json.dumps(raw_metadata, ensure_ascii=False),
                    text_hash, version_key, text,
                    json.dumps(raw_metadata, ensure_ascii=False), official_url, ref)
                if not version:
                    raise RuntimeError(f"Échec de l'upsert de l'article {ref}.")
                chunks = split_text(text)
                for ordinal, chunk in enumerate(chunks):
                    chunk_rows.append((version["id"], ordinal, ref, chunk))
                inserted_versions += 1
                inserted_chunks += len(chunks)

            if chunk_rows:
                await conn.executemany("""
                    INSERT INTO legal_chunks(version_id,ordinal,anchor,content_kind,content)
                    VALUES($1,$2,$3,'FULL_TEXT',$4)
                """, chunk_rows)

            verification = await conn.fetchrow("""
                SELECT
                  (SELECT count(*)::int FROM legal_documents
                    WHERE source_type='CGFP_SNAPSHOT' AND source_id LIKE $1) AS documents,
                  (SELECT count(*)::int FROM legal_document_versions v
                    JOIN legal_documents d ON d.id=v.document_id
                    WHERE d.source_type='CGFP_SNAPSHOT' AND d.source_id LIKE $1
                      AND v.version_key LIKE $2) AS versions,
                  (SELECT count(*)::int FROM legal_chunks c
                    JOIN legal_document_versions v ON v.id=c.version_id
                    JOIN legal_documents d ON d.id=v.document_id
                    WHERE d.source_type='CGFP_SNAPSHOT' AND d.source_id LIKE $1
                      AND v.version_key LIKE $2) AS chunks,
                  (SELECT count(*)::int FROM legal_documents
                    WHERE source_type='CGFP_SNAPSHOT' AND source_id LIKE $1
                      AND (source_status<>'IMPORTED_UNVERIFIED' OR status<>'UNKNOWN')) AS bad_document_status,
                  (SELECT count(*)::int FROM legal_document_versions v
                    JOIN legal_documents d ON d.id=v.document_id
                    WHERE d.source_type='CGFP_SNAPSHOT' AND d.source_id LIKE $1
                      AND v.version_key LIKE $2
                      AND (v.version_status<>'UNKNOWN' OR v.valid_from IS NOT NULL OR v.valid_to IS NOT NULL)) AS bad_temporal_status
            """, f'{metadata["source_id"]}:%',
                f'{metadata["source_id"]}:{metadata["source_sha256"][:16]}:%')
            expected = {
                "documents": len(articles),
                "versions": len(articles),
                "chunks": inserted_chunks,
                "bad_document_status": 0,
                "bad_temporal_status": 0,
            }
            actual = {key: verification[key] for key in expected}
            if actual != expected:
                raise RuntimeError(
                    "Contrôle après import CGFP en échec : "
                    + json.dumps({"expected": expected, "actual": actual}, ensure_ascii=False)
                )
    finally:
        await conn.close()
    return {"articles": len(articles), "versions": inserted_versions, "chunks": inserted_chunks}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--apply", action="store_true",
                        help="exécute réellement l'import (sinon contrôle à blanc)")
    parser.add_argument("--dsn", default=os.getenv("LEGAL_CORPUS_INGEST_DATABASE_URL"),
                        help="DSN PostgreSQL ; par défaut variable LEGAL_CORPUS_INGEST_DATABASE_URL")
    args = parser.parse_args()
    try:
        metadata, articles = load_snapshot(args.index)
        print(f"Contrôle OK : {len(articles)} articles ; source={metadata['source_id']}")
        print(f"PDF SHA-256 vérifié : {metadata['source_sha256']}")
        print("Import prévu : CGFP_SNAPSHOT / CODE / IMPORTED_UNVERIFIED / dates d'effet UNKNOWN.")
        if not args.apply:
            print("Mode contrôle à blanc : aucune écriture en base. Ajouter --apply pour importer.")
            return 0
        if not args.dsn:
            raise ValueError(
                "LEGAL_CORPUS_INGEST_DATABASE_URL ou --dsn est requis avec --apply."
            )
        validate_ingest_dsn(args.dsn)
        result = asyncio.run(import_snapshot(args.dsn, metadata, articles))
        print("Import terminé :", json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(f"ERREUR : {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
