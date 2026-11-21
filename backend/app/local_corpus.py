"""Recherche tenant-scoped dans les documents locaux validés.

Les documents locaux sont des pièces propres à une organisation. Ils ne sont
jamais mélangés au corpus national et ne sont transmis à l'IA que si leur
extraction, leur intégrité, leur validation humaine et leur période d'effet
sont toutes contrôlées.
"""
from __future__ import annotations

from datetime import date
from typing import Any


def local_document_temporal_status(
    effective_from: date | str | None,
    effective_to: date | str | None,
    validation_status: str,
    requested_date: date,
) -> str:
    def as_date(value: date | str | None) -> date | None:
        if isinstance(value, date):
            return value
        try:
            return date.fromisoformat(str(value)[:10]) if value else None
        except (TypeError, ValueError):
            return None

    start, end = as_date(effective_from), as_date(effective_to)
    if start is None:
        return "TEMPORAL_SCOPE_INCOMPLETE"
    if requested_date < start or (end is not None and requested_date > end):
        return "NOT_APPLICABLE_ON_REQUESTED_DATE"
    if validation_status in {"VERIFIED_APPLICABLE", "VERIFIED_HISTORICAL"}:
        return "VERIFIED_APPLICABLE"
    return "LOCAL_VALIDATION_INCOMPLETE"


COLLECTIVITY_FILTERS = {
    "VILLE_SAINT_ETIENNE": {
        "codes": ("VILLE_SAINT_ETIENNE", "VILLE_ST_ETIENNE", "VILLE_DE_SAINT_ETIENNE"),
        "names": ("ville de saint-étienne", "ville de saint-etienne", "saint-étienne", "saint-etienne"),
    },
    "SAINT_ETIENNE_METROPOLE": {
        "codes": ("SAINT_ETIENNE_METROPOLE", "ST_ETIENNE_METROPOLE", "STE_METROPOLE"),
        "names": ("saint-étienne métropole", "saint-etienne métropole"),
    },
}


async def search_local_documents(
    conn: Any,
    organization_id: str,
    employer: str,
    query: str,
    effective_date: date,
    limit: int = 5,
) -> list[dict]:
    """Search only clean, extracted documents belonging to the current tenant."""
    if employer == "NATIONAL":
        return []
    if employer not in COLLECTIVITY_FILTERS:
        raise ValueError("Employeur local non pris en charge.")
    query = query.strip()
    if len(query) < 3:
        return []
    if len(query) > 500:
        query = query[:500]
    if not 1 <= limit <= 10:
        raise ValueError("La limite de recherche locale doit être comprise entre 1 et 10.")

    aliases = COLLECTIVITY_FILTERS[employer]
    rows = await conn.fetch(
        """
        SELECT d.id, d.title, d.document_type, d.official_number, d.official_url,
               d.adopted_at, d.published_at, d.effective_from, d.effective_to,
               d.validation_status, d.sha256,
               dt.sha256 AS extracted_sha256, dt.extraction_status,
               c.name AS collectivity_name, c.code AS collectivity_code,
               ts_rank(dt.search_vector, plainto_tsquery('french', $4)) AS relevance,
               ts_headline('french', dt.extracted_text, plainto_tsquery('french', $4),
                 'MaxWords=45,MinWords=12,ShortWord=2,HighlightAll=false') AS excerpt
        FROM document_text dt
        JOIN documents d
          ON d.organization_id=dt.organization_id
         AND d.id=dt.document_id
         AND d.sha256=dt.sha256
        JOIN document_versions dv
          ON dv.organization_id=dt.organization_id
         AND dv.document_id=dt.document_id
         AND dv.version_number=dt.version_number
         AND dv.sha256=dt.sha256
        JOIN collectivities c
          ON c.organization_id=d.organization_id
         AND c.id=d.collectivity_id
        WHERE dt.organization_id=$1::uuid
          AND dt.search_vector @@ plainto_tsquery('french', $4)
          AND dt.extraction_status='EXTRACTED'
          AND d.scan_status='CLEAN'
          AND dv.scan_status='CLEAN'
          AND (
            upper(c.code) = ANY($2::text[])
            OR lower(c.name) = ANY($3::text[])
          )
        ORDER BY relevance DESC, d.published_at DESC NULLS LAST
        LIMIT $5
        """,
        organization_id,
        list(aliases["codes"]),
        list(aliases["names"]),
        query,
        limit,
    )

    results: list[dict] = []
    for row in rows:
        effective_from = row["effective_from"]
        effective_to = row["effective_to"]
        validation_status = str(row["validation_status"] or "COLLECTED_UNVERIFIED")
        temporal_status = local_document_temporal_status(
            effective_from, effective_to, validation_status, effective_date,
        )

        hash_matches = bool(row["sha256"] and row["extracted_sha256"] and
                            str(row["sha256"]).strip() == str(row["extracted_sha256"]).strip())
        results.append({
            "source_type": "LOCAL_DOCUMENT",
            "source_id": f"LOCAL-DOC:{row['id']}",
            "title": row["title"],
            "document_kind": "LOCAL_DOCUMENT",
            "local_document_type": row["document_type"],
            "official_number": row["official_number"],
            "official_url": row["official_url"],
            "signature_date": row["adopted_at"].isoformat() if row["adopted_at"] else None,
            "publication_date": row["published_at"].isoformat() if row["published_at"] else None,
            "effective_from": effective_from.isoformat() if effective_from else None,
            "effective_to": effective_to.isoformat() if effective_to else None,
            "validation_status": validation_status,
            "temporal_status": temporal_status,
            "collectivity": row["collectivity_name"],
            "collectivity_code": row["collectivity_code"],
            "source_status": "TENANT_DOCUMENT_TEXT_EXTRACTED",
            "content_kind": "FULL_TEXT",
            "excerpt": row["excerpt"] or "",
            "text": row["excerpt"] or "",
            "relevance": float(row["relevance"]),
            "citation_integrity": {
                "valid": hash_matches and row["extraction_status"] == "EXTRACTED",
                "verification_scope": "TENANT_DOCUMENT_SHA256_AND_CLEAN_SCAN",
                "document_hash_matches_text_record": hash_matches,
            },
        })
    return results
