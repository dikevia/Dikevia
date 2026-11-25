#!/usr/bin/env python3
"""Importe les fiches Fonction publique de Service-Public dans le corpus national.

Aucune écriture n'est effectuée sans --apply. Les fiches sont des ressources
administratives d'information : elles restent IMPORTED_UNVERIFIED et ne sont
jamais promues au rang de texte juridique officiel.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from app.legal_corpus import clean_text, sha256_text, upsert_legal_document  # noqa: E402
from import_service_public_fonction_publique import (  # noqa: E402
    extraire_fiches_fonctionnaires,
    telecharger_archive_sp,
)


def validate_ingest_dsn(dsn: str) -> None:
    parsed = urlparse(dsn)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ValueError("Le DSN d'import doit être une URL PostgreSQL.")
    if parsed.username != "cfdt_juris_ingest":
        raise ValueError("Refus d'import : utiliser exclusivement le rôle dédié cfdt_juris_ingest.")


def to_corpus_item(fiche: dict, provenance: dict) -> dict:
    fiche_id = str(fiche.get("fiche_id") or "").strip().upper()
    title = str(fiche.get("titre_courant") or "").strip()
    full_text = clean_text(str(fiche.get("contenu") or ""))
    if not re.fullmatch(r"F\d+", fiche_id) or not title or len(full_text) < 80:
        raise ValueError("Fiche Service-Public incomplète : identifiant F valide, titre et contenu substantiel requis.")
    digest = sha256_text(full_text)
    return {
        "source_type": "SERVICE_PUBLIC_PART",
        "source_id": fiche_id,
        "title": title[:1000],
        "document_kind": "ADMIN_GUIDANCE",
        "publisher": "Service-Public.gouv.fr / DILA",
        "official_url": f"https://www.service-public.gouv.fr/particuliers/vosdroits/{fiche_id}",
        "status": "UNKNOWN",
        "source_status": "IMPORTED_UNVERIFIED",
        "full_text": full_text,
        "version_key": f"{fiche_id}:{digest}",
        "version_status": "UNKNOWN",
        "valid_from": None,
        "valid_to": None,
        "raw_metadata": {
            "dataset_api_url": provenance.get("dataset_api_url"),
            "dataset_id": provenance.get("dataset_id"),
            "dataset_title": provenance.get("dataset_title"),
            "dataset_last_update": provenance.get("dataset_last_update"),
            "resource_id": provenance.get("resource_id"),
            "resource_title": provenance.get("resource_title"),
            "download_url": provenance.get("download_url"),
            "filename": provenance.get("filename"),
            "file_date": provenance.get("file_date"),
            "resource_last_modified": provenance.get("resource_last_modified"),
            "resource_checksum": provenance.get("resource_checksum"),
            "downloaded_at": provenance.get("downloaded_at"),
            "license": provenance.get("license"),
            "attribution": provenance.get("attribution") or "Service-Public.gouv.fr / DILA",
            "fiche_id": fiche_id,
            "theme_ids": fiche.get("theme_ids") or [],
            "versants_detectes": fiche.get("versants_detectes") or [],
            "references_juridiques": fiche.get("references_juridiques") or [],
            "statut_validation_juridique": "NON_VERIFIE",
            "owner_trust_status": "TRUSTED_BY_PROJECT_OWNER",
            "owner_trust_confirmed_at": "2026-11-25",
            "corpus_role": "ADMINISTRATIVE_GUIDANCE_NOT_PRIMARY_LEGAL_AUTHORITY",
        },
        "raw_version_payload": {
            "content_sha256": digest,
            "source_dataset": "DILA_SERVICE_PUBLIC_PARTICULIERS_XML_3_5",
        },
    }


async def import_items(items: list[dict], dsn: str) -> dict:
    try:
        import asyncpg
    except ImportError as exc:
        raise RuntimeError("Dépendance asyncpg absente. Installer backend/requirements.txt.") from exc
    validate_ingest_dsn(dsn)
    conn = await asyncpg.connect(dsn, command_timeout=180)
    imported = 0
    chunks = 0
    try:
        async with conn.transaction():
            for item in items:
                result = await upsert_legal_document(conn, item)
                imported += 1
                chunks += int(result["chunks"])
    finally:
        await conn.close()
    return {"documents_imported": imported, "chunks_indexed": chunks}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Écrit dans le corpus avec le rôle d'ingestion dédié.")
    parser.add_argument("--limit", type=int, default=0, help="Limite facultative pour un import pilote.")
    parser.add_argument("--export-json", type=Path, help="Exporte les documents préparés dans un fichier JSON.")
    args = parser.parse_args()
    if args.limit < 0:
        parser.error("--limit doit être positif ou nul.")
    dsn = os.environ.get("LEGAL_CORPUS_INGEST_DATABASE_URL", "")
    if args.apply:
        validate_ingest_dsn(dsn)
    archive, provenance = telecharger_archive_sp()
    try:
        fiches = extraire_fiches_fonctionnaires(archive)
    finally:
        archive.close()
    if not fiches:
        raise RuntimeError("Aucune fiche Fonction publique trouvée : aucune écriture effectuée.")
    if args.limit:
        fiches = fiches[:args.limit]
    items = [to_corpus_item(fiche, provenance) for fiche in fiches]
    if args.export_json:
        args.export_json.parent.mkdir(parents=True, exist_ok=True)
        args.export_json.write_text(
            json.dumps({"source": provenance, "documents": items}, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        print(f"Export documentaire préparé : {len(items)} fiches vers {args.export_json}")
    print(json.dumps({
        "mode": "APPLY" if args.apply else "DRY_RUN",
        "documents_detected": len(items),
        "sample": [{"source_id": item["source_id"], "title": item["title"],
                    "source_status": item["source_status"], "characters": len(item["full_text"])}
                   for item in items[:5]],
        "attribution": provenance.get("attribution"),
        "license": provenance.get("license"),
        "download_url": provenance.get("download_url"),
    }, ensure_ascii=False, indent=2))
    if not args.apply:
        print("DRY RUN : aucune donnée n'a été écrite. Relancer avec --apply après validation.")
        return 0
    result = asyncio.run(import_items(items, dsn))
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERREUR import corpus Service-Public : {exc}", file=sys.stderr)
        raise SystemExit(1)
