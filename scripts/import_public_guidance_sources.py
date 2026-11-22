#!/usr/bin/env python3
"""Collecte les PDF/HTML publics enregistrés dans le registre du corpus Dikévia.

Le mode par défaut est un dry-run. L'import PostgreSQL est réservé aux
ressources explicitement approuvées (source et réutilisation), via le rôle
cfdt_juris_ingest. Les contenus restent des guides non normatifs.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

import httpx
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.legal_corpus import clean_text, sha256_text, upsert_legal_document  # noqa: E402

REGISTRY_PATH = ROOT / "corpus_national" / "sources" / "registry.json"
MAX_DOWNLOAD_BYTES = 30 * 1024 * 1024
MAX_PDF_PAGES = 500


class VisibleTextParser(HTMLParser):
    """Extract readable HTML text while ignoring executable and hidden blocks."""
    BLOCKED = {"script", "style", "noscript", "svg", "nav", "footer", "header"}
    BLOCKS = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "tr", "section"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.blocked = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self.BLOCKED:
            self.blocked += 1
        elif not self.blocked and tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.BLOCKED and self.blocked:
            self.blocked -= 1
        elif not self.blocked and tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.blocked and data.strip():
            self.parts.append(data.strip())

    def text(self) -> str:
        return clean_text("\n".join(self.parts))


def load_registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def source_for(seed: dict, registry: dict) -> dict:
    sources = {item["id"]: item for item in registry.get("sources", [])}
    source = sources.get(seed.get("source_id"))
    if not source:
        raise ValueError(f"Source inconnue pour {seed.get('id')}")
    return source


def validate_public_url(url: str, source: dict) -> None:
    parsed = urlparse(url)
    allowed = {str(host).casefold() for host in source.get("domains", [])}
    if parsed.scheme != "https" or not parsed.hostname or parsed.hostname.casefold() not in allowed:
        raise ValueError("URL HTTPS hors liste de domaines autorisés du registre.")


def extract_pdf(content: bytes) -> tuple[str, dict]:
    import io
    reader = PdfReader(io.BytesIO(content), strict=True)
    if reader.is_encrypted:
        raise ValueError("PDF chiffré : extraction automatique refusée.")
    if len(reader.pages) == 0 or len(reader.pages) > MAX_PDF_PAGES:
        raise ValueError("Nombre de pages PDF nul ou supérieur à la limite.")
    pages = []
    for number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            pages.append(f"[Page {number}]\n{text}")
    full_text = clean_text("\n\n".join(pages))
    if len(full_text) < 500:
        raise ValueError("PDF sans couche texte exploitable ou contenu trop court.")
    meta = reader.metadata
    return full_text, {
        "page_count": len(reader.pages),
        "pdf_title": str(meta.title) if meta and meta.title else None,
        "pdf_author": str(meta.author) if meta and meta.author else None,
        "pdf_creation_date": str(meta.creation_date) if meta and meta.creation_date else None,
    }


def extract_html(content: bytes) -> tuple[str, dict]:
    decoded = content.decode("utf-8", errors="replace")
    parser = VisibleTextParser()
    parser.feed(decoded)
    text = parser.text()
    if len(text) < 500:
        raise ValueError("Page HTML sans contenu textuel substantiel.")
    title_match = re.search(r"<title[^>]*>(.*?)</title>", decoded, flags=re.I | re.S)
    title = clean_text(title_match.group(1)) if title_match else None
    return text, {"html_title": title}


def fetch_seed(client: httpx.Client, seed: dict, source: dict) -> dict:
    url = seed["url"]
    validate_public_url(url, source)
    with client.stream("GET", url, timeout=60.0) as response:
        response.raise_for_status()
        final_url = str(response.url)
        validate_public_url(final_url, source)
        chunks, size = [], 0
        for chunk in response.iter_bytes():
            size += len(chunk)
            if size > MAX_DOWNLOAD_BYTES:
                raise ValueError("Document supérieur à 30 Mo.")
            chunks.append(chunk)
        content = b"".join(chunks)
        content_type = response.headers.get("content-type", "").split(";", 1)[0].casefold()
        last_modified = response.headers.get("last-modified")
    if not content:
        raise ValueError("Réponse vide.")
    if content.startswith(b"%PDF-") or content_type == "application/pdf" or seed.get("format") == "PDF":
        if not content.startswith(b"%PDF-"):
            raise ValueError("Le serveur n'a pas renvoyé un PDF valide.")
        text, details = extract_pdf(content)
        detected_format = "PDF"
    else:
        text, details = extract_html(content)
        detected_format = "HTML"
    digest = hashlib.sha256(content).hexdigest()
    return {
        "text": text,
        "sha256": digest,
        "byte_count": len(content),
        "format": detected_format,
        "last_modified": last_modified,
        "details": details,
        "final_url": final_url,
    }


def to_corpus_item(seed: dict, source: dict, fetched: dict) -> dict:
    digest = sha256_text(fetched["text"])
    publication_date = seed.get("publication_date")
    pub_date = date.fromisoformat(publication_date) if publication_date and re.fullmatch(r"\d{4}-\d{2}-\d{2}", publication_date) else None
    return {
        "source_type": "INSTITUTIONAL_GUIDANCE",
        "source_id": seed["id"],
        "title": seed["title"][:1000],
        "document_kind": "PROFESSIONAL_GUIDANCE" if source.get("authority_level") == "PROFESSIONAL_GUIDANCE" else "ADMIN_GUIDANCE",
        "publisher": source.get("publisher") or source.get("name"),
        "official_url": fetched["final_url"],
        "publication_date": pub_date,
        "status": "UNKNOWN",
        "source_status": "IMPORTED_UNVERIFIED",
        "full_text": fetched["text"],
        "version_key": f"{seed['id']}:{digest}",
        "version_status": "UNKNOWN",
        "valid_from": None,
        "valid_to": None,
        "raw_metadata": {
            "seed_id": seed["id"],
            "source_id": source["id"],
            "source_name": source.get("name"),
            "authority_level": source.get("authority_level"),
            "scope_candidate": seed.get("scope", []),
            "topics_candidate": seed.get("topics", []),
            "source_url": seed["url"],
            "final_url": fetched["final_url"],
            "format": fetched["format"],
            "download_sha256": fetched["sha256"],
            "download_bytes": fetched["byte_count"],
            "last_modified": fetched["last_modified"],
            "document_details": fetched["details"],
            "reuse_status": seed.get("reuse_status"),
            "source_registry_status": source.get("status"),
            "corpus_role": "ADMINISTRATIVE_GUIDANCE_NOT_PRIMARY_LEGAL_AUTHORITY",
            "legal_validation_status": "NOT_VERIFIED",
        },
        "raw_version_payload": {
            "content_sha256": digest,
            "download_sha256": fetched["sha256"],
            "source_url": seed["url"],
        },
    }


async def import_items(items: list[dict], dsn: str) -> dict:
    import asyncpg
    parsed = urlparse(dsn)
    if parsed.scheme not in {"postgres", "postgresql"} or parsed.username != "cfdt_juris_ingest":
        raise ValueError("Import refusé : URL PostgreSQL et rôle cfdt_juris_ingest obligatoires.")
    conn = await asyncpg.connect(dsn, command_timeout=180)
    documents = chunks = 0
    try:
        async with conn.transaction():
            for item in items:
                result = await upsert_legal_document(conn, item)
                documents += 1
                chunks += int(result["chunks"])
    finally:
        await conn.close()
    return {"documents_imported": documents, "chunks_indexed": chunks}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--id", action="append", default=[], help="Identifiant de seed (répétable).")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--apply", action="store_true", help="Importe uniquement les ressources approuvées.")
    parser.add_argument("--export-json", type=Path, help="Exporte les documents téléchargés et extraits pour audit.")
    args = parser.parse_args()
    if args.limit < 0:
        parser.error("--limit doit être positif ou nul.")
    registry = load_registry()
    seeds = registry.get("document_seeds", [])
    if args.id:
        wanted = set(args.id)
        seeds = [seed for seed in seeds if seed.get("id") in wanted]
        missing = wanted - {seed.get("id") for seed in seeds}
        if missing:
            raise ValueError("Seeds inconnues : " + ", ".join(sorted(missing)))
    if args.limit:
        seeds = seeds[:args.limit]
    if not seeds:
        raise ValueError("Aucune ressource sélectionnée.")
    dsn = os.environ.get("LEGAL_CORPUS_INGEST_DATABASE_URL", "")
    client = httpx.Client(follow_redirects=True, headers={"User-Agent": "Dikevia-CorpusImporter/1.0"})
    items, rejected = [], []
    try:
        for seed in seeds:
            source = source_for(seed, registry)
            validate_public_url(seed["url"], source)
            approved_source_statuses = {"REUSE_APPROVED", "APPROVED"}
            approved_reuse_statuses = {"REUSE_APPROVED", "APPROVED"}
            if args.apply and (
                source.get("status") not in approved_source_statuses
                or seed.get("reuse_status") not in approved_reuse_statuses
            ):
                rejected.append({"id": seed["id"], "reason": "source_or_reuse_not_approved"})
                continue
            fetched = fetch_seed(client, seed, source)
            items.append(to_corpus_item(seed, source, fetched))
    finally:
        client.close()
    if args.export_json:
        args.export_json.parent.mkdir(parents=True, exist_ok=True)
        args.export_json.write_text(
            json.dumps({"documents": items, "rejected": rejected}, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        print(f"Export PDF/HTML préparé : {len(items)} documents vers {args.export_json}")
    print(json.dumps({
        "mode": "APPLY" if args.apply else "DRY_RUN",
        "downloaded": len(items),
        "rejected": rejected,
        "documents": [{
            "id": item["source_id"], "title": item["title"],
            "format": item["raw_metadata"]["format"],
            "characters": len(item["full_text"]),
            "sha256": item["raw_metadata"]["download_sha256"],
        } for item in items],
    }, ensure_ascii=False, indent=2))
    if not args.apply:
        print("DRY RUN : aucun enregistrement PostgreSQL n'a été créé.")
        return 0
    if rejected:
        raise RuntimeError("Import partiel refusé : toutes les ressources sélectionnées doivent être approuvées.")
    result = asyncio.run(import_items(items, dsn))
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERREUR import guides publics : {exc}", file=sys.stderr)
        raise SystemExit(1)
