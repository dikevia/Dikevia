#!/usr/bin/env python3
"""Read-only audit of Service-Public legal-reference identifier provenance in Neon staging."""
from __future__ import annotations

import asyncio
import json
import os
import re
from collections import Counter
from urllib.parse import urlparse

STAGING_MARKER = "br-billowing-haze-bd5a1cns"
LEGIFRANCE_ID = re.compile(
    r"^(?:LEGIARTI|LEGITEXT|JORFTEXT|JORFARTI|CETATEXT)\d{8,}$",
    re.IGNORECASE,
)


def _json_array(value: object) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except ValueError:
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def audit_references(source_id: str, value: object) -> dict:
    """Return counts and explicit provenance errors without modifying source data."""
    references = _json_array(value)
    result = {
        "source_id": source_id,
        "references": len(references),
        "missing_source_reference_id": 0,
        "mislabelled_legifrance_id": 0,
        "malformed_reference": 0,
        "errors": [],
    }
    for index, reference in enumerate(references):
        if not isinstance(reference, dict):
            result["malformed_reference"] += 1
            result["errors"].append(f"{source_id}[{index}]:reference_not_object")
            continue
        source_reference_id = str(reference.get("source_reference_id") or "").strip()
        legifrance_id = str(reference.get("id_legifrance") or "").strip()
        if not source_reference_id:
            result["missing_source_reference_id"] += 1
            result["errors"].append(f"{source_id}[{index}]:source_reference_id_missing")
        if legifrance_id and not LEGIFRANCE_ID.fullmatch(legifrance_id):
            result["mislabelled_legifrance_id"] += 1
            result["errors"].append(f"{source_id}[{index}]:id_legifrance_not_recognized")
        if legifrance_id and source_reference_id and legifrance_id.casefold() != source_reference_id.casefold():
            result["errors"].append(f"{source_id}[{index}]:identifier_provenance_mismatch")
    return result


async def main() -> int:
    database_url = os.environ.get("LEGAL_CORPUS_INGEST_DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("LEGAL_CORPUS_INGEST_DATABASE_URL is required.")
    parsed = urlparse(database_url)
    if parsed.scheme not in {"postgres", "postgresql"} or parsed.username != "cfdt_juris_ingest":
        raise RuntimeError("Read-only staging audit requires the dedicated cfdt_juris_ingest role.")

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
                SELECT source_id, raw_metadata->'references_juridiques' AS refs_json
                FROM legal_documents
                WHERE source_type='SERVICE_PUBLIC_PART'
                ORDER BY source_id
                """
            )
            if not rows:
                raise RuntimeError("No Service-Public documents found in staging.")

        totals: Counter = Counter()
        document_errors = []
        for row in rows:
            result = audit_references(str(row["source_id"]), row["refs_json"])
            for key in ("references", "missing_source_reference_id",
                        "mislabelled_legifrance_id", "malformed_reference"):
                totals[key] += result[key]
            if result["errors"]:
                document_errors.append({
                    "source_id": result["source_id"],
                    "errors": result["errors"],
                })

        report = {
            "status": "PASS" if not document_errors else "FAIL",
            "documents": len(rows),
            **dict(totals),
            "documents_with_errors": len(document_errors),
            "write_operations": 0,
        }
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        for item in document_errors:
            print("REFERENCE_PROVENANCE_ERROR " + json.dumps(item, ensure_ascii=False))
        return 0 if not document_errors else 1
    finally:
        await conn.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
