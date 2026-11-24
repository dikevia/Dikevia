#!/usr/bin/env python3
"""Read-only audit of non-normative guidance actually stored in Neon staging."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from collections import Counter
from urllib.parse import urlparse

from app.legal_assurance import classify_legal_source

STAGING_MARKER = "br-billowing-haze-bd5a1cns"
GUIDANCE_SOURCE_TYPES = ("SERVICE_PUBLIC_PART", "INSTITUTIONAL_GUIDANCE")


def _json_object(value: object) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except ValueError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _audit_row(row) -> tuple[list[str], dict]:
    source = dict(row)
    metadata = _json_object(source.get("raw_metadata"))
    source["raw_metadata"] = metadata
    source_id = str(source.get("source_id") or "<missing>")
    errors: list[str] = []

    if source.get("source_status") != "IMPORTED_UNVERIFIED":
        errors.append("source_status_not_imported_unverified")
    if source.get("status") != "UNKNOWN":
        errors.append("document_status_not_unknown")
    if source.get("version_status") != "UNKNOWN":
        errors.append("version_status_not_unknown")
    if source.get("valid_from") is not None or source.get("valid_to") is not None:
        errors.append("unverified_effective_dates_present")

    full_text = source.get("full_text")
    stored_hash = str(source.get("text_sha256") or "").strip()
    if not isinstance(full_text, str) or not full_text.strip():
        errors.append("full_text_missing")
    elif not stored_hash or hashlib.sha256(full_text.encode("utf-8")).hexdigest() != stored_hash:
        errors.append("full_text_hash_mismatch")
    if int(source.get("chunk_count") or 0) < 1:
        errors.append("document_has_no_chunks")

    assurance = classify_legal_source(source)
    if assurance.get("normative") is not False:
        errors.append("guidance_marked_normative")
    if assurance.get("claim_eligible") is not False:
        errors.append("guidance_claim_eligible")
    if assurance.get("usable_for_conclusion") is not False:
        errors.append("guidance_usable_for_conclusion")
    if assurance.get("usable_for_facts_date_conclusion") is not False:
        errors.append("guidance_usable_for_facts_date_conclusion")
    if assurance.get("reference_role") != "NON_NORMATIVE_CONTEXT_ONLY":
        errors.append("guidance_reference_role_invalid")
    if assurance.get("usable_for_interpretation") is not True:
        errors.append("guidance_context_interpretation_unavailable")

    source_type = source.get("source_type")
    if source_type == "SERVICE_PUBLIC_PART":
        if assurance.get("authority_level") != "OFFICIAL_ADMIN_GUIDANCE":
            errors.append("service_public_authority_misclassified")
        if assurance.get("publisher_type") != "PUBLIC_ADMINISTRATION":
            errors.append("service_public_publisher_misclassified")
    elif source_type == "INSTITUTIONAL_GUIDANCE":
        if metadata.get("source_registry_status") != "REUSE_APPROVED":
            errors.append("institutional_source_registry_not_approved")
        if metadata.get("reuse_status") != "REUSE_APPROVED":
            errors.append("institutional_reuse_not_approved")
        if metadata.get("legal_validation_status") != "NOT_VERIFIED":
            errors.append("institutional_legal_validation_status_changed")
        declared_authority = metadata.get("authority_level")
        expected = {
            "TRADE_UNION_POSITION": ("TRADE_UNION", "PROFESSIONAL_GUIDANCE"),
            "OFFICIAL_ADMIN_GUIDANCE": ("PUBLIC_ADMINISTRATION", "OFFICIAL_ADMIN_GUIDANCE"),
            "PROFESSIONAL_GUIDANCE": ("PROFESSIONAL_BODY", "PROFESSIONAL_GUIDANCE"),
        }.get(declared_authority)
        if expected is None:
            errors.append("institutional_declared_authority_unknown")
        elif (
            assurance.get("publisher_type") != expected[0]
            or assurance.get("authority_level") != expected[1]
        ):
            errors.append("institutional_publisher_authority_misclassified")
        if (
            declared_authority == "TRADE_UNION_POSITION"
            and assurance.get("source_family_label") != "Doctrine syndicale — non normative"
        ):
            errors.append("trade_union_label_missing")
    else:
        errors.append("unexpected_guidance_source_type")

    summary = {
        "source_type": source_type,
        "authority_level": assurance.get("authority_level"),
        "publisher_type": assurance.get("publisher_type"),
        "chunks": int(source.get("chunk_count") or 0),
    }
    return ([f"{source_id}:{error}" for error in errors], summary)


async def main() -> int:
    database_url = os.environ.get("LEGAL_CORPUS_INGEST_DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("LEGAL_CORPUS_INGEST_DATABASE_URL is required.")
    if urlparse(database_url).username != "cfdt_juris_ingest":
        raise RuntimeError("This read-only audit requires the dedicated staging ingestion role.")

    import asyncpg

    conn = await asyncpg.connect(database_url, command_timeout=120)
    try:
        async with conn.transaction(readonly=True):
            identity = await conn.fetchval("SELECT current_user")
            marker = await conn.fetchval(
                "SELECT marker FROM public.dikevia_staging_guard WHERE marker=$1",
                STAGING_MARKER,
            )
            if identity != "cfdt_juris_ingest" or marker != STAGING_MARKER:
                raise RuntimeError("Database identity or staging marker mismatch.")

            rows = await conn.fetch(
                """
                SELECT d.source_type, d.source_id, d.title, d.document_kind,
                       d.publisher, d.status, d.source_status, d.raw_metadata,
                       v.version_status, v.valid_from, v.valid_to,
                       v.full_text, v.text_sha256, count(c.id)::int AS chunk_count
                FROM legal_documents d
                JOIN legal_document_versions v ON v.document_id = d.id
                LEFT JOIN legal_chunks c ON c.version_id = v.id
                WHERE d.source_type = ANY($1::text[])
                GROUP BY d.id, v.id
                ORDER BY d.source_type, d.source_id, v.version_key
                """,
                list(GUIDANCE_SOURCE_TYPES),
            )
            if not rows:
                raise RuntimeError("No Service-Public or institutional guidance records found in staging.")

            errors: list[str] = []
            counts: Counter = Counter()
            chunks = 0
            for row in rows:
                row_errors, summary = _audit_row(row)
                errors.extend(row_errors)
                counts[(summary["source_type"], summary["authority_level"], summary["publisher_type"])] += 1
                chunks += summary["chunks"]

        if errors:
            for error in errors:
                print(f"GUIDANCE_AUDIT_ERROR {error}")
            return 1

        summary = {
            "status": "PASS",
            "documents": len(rows),
            "chunks": chunks,
            "classification_counts": [
                {
                    "source_type": key[0],
                    "authority_level": key[1],
                    "publisher_type": key[2],
                    "documents": value,
                }
                for key, value in sorted(counts.items())
            ],
            "claim_eligible_guidance": 0,
            "normative_guidance": 0,
            "write_operations": 0,
        }
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
