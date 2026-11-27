#!/usr/bin/env python3
"""Import monthly CE/CAA/TA open-data archives into the FPT legal corpus.

The source is the official, open-licensed administrative-justice dataset.
The default mode is a dry run. Writes require --apply and the dedicated
cfdt_juris_ingest PostgreSQL role. Only FPT and explicitly common decisions
are retained; FPE, FPH and unqualified public-service decisions are excluded.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.legal_corpus import upsert_legal_document  # noqa: E402
from app.legal_ingestion import (  # noqa: E402
    administrative_open_data_archive_url,
    filter_administrative_open_data_items,
    parse_administrative_open_data_zip,
)

MAX_ARCHIVE_BYTES = 100 * 1024 * 1024
OFFICIAL_HOST = "opendata.justice-administrative.fr"


def parse_month(value: str) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", value):
        raise ValueError("Mois attendu au format AAAA-MM.")
    year, month = (int(part) for part in value.split("-"))
    return date(year, month, 1)


def month_range(start: date, end: date):
    if start.day != 1 or end.day != 1 or start > end:
        raise ValueError("La période doit être ordonnée et exprimée en mois AAAA-MM.")
    current = start
    while current <= end:
        yield current
        current = date(current.year + (current.month == 12), 1 if current.month == 12 else current.month + 1, 1)


def validate_ingest_dsn(dsn: str) -> None:
    parsed = urlparse(dsn)
    if parsed.scheme not in {"postgres", "postgresql"} or parsed.username != "cfdt_juris_ingest":
        raise ValueError("Import refusé : utiliser exclusivement le rôle dédié cfdt_juris_ingest.")
    if parsed.hostname and "-pooler" in parsed.hostname:
        raise ValueError("Import volumineux refusé sur une URL pooler ; utiliser l'URL PostgreSQL directe.")


def download_archive(client: httpx.Client, url: str) -> bytes | None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != OFFICIAL_HOST or parsed.port not in {None, 443}:
        raise ValueError("Téléchargement refusé : hôte officiel HTTPS attendu.")
    chunks: list[bytes] = []
    total = 0
    with client.stream("GET", url) as response:
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise RuntimeError(f"Archive officielle indisponible : HTTP {response.status_code}.")
        content_length = response.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > MAX_ARCHIVE_BYTES:
                    raise ValueError("Archive supérieure à la limite de 100 Mo.")
            except ValueError as exc:
                if "supérieure" in str(exc):
                    raise
        for chunk in response.iter_bytes():
            total += len(chunk)
            if total > MAX_ARCHIVE_BYTES:
                raise ValueError("Archive supérieure à la limite de 100 Mo.")
            chunks.append(chunk)
    raw = b"".join(chunks)
    if not raw.startswith(b"PK\x03\x04"):
        raise ValueError("La ressource téléchargée n'est pas une archive ZIP reconnue.")
    return raw


async def archive_already_imported(conn, archive_name: str) -> bool:
    """Avoid downloading and reprocessing an archive already imported successfully."""
    return bool(await conn.fetchval(
        """SELECT EXISTS(
             SELECT 1 FROM legal_ingestion_runs
             WHERE source_type='OTHER_OFFICIAL'
               AND run_mode='BULK_XML_IMPORT'
               AND query_text=$1
               AND status='SUCCEEDED'
           )""",
        archive_name[:250],
    ))


async def import_archive(
    conn,
    court: str,
    archive_month: date,
    archive_name: str,
    raw: bytes,
    *,
    parsed_items: list[dict] | None = None,
    replace_existing: bool = False,
) -> dict:
    parsed = parsed_items if parsed_items is not None else parse_administrative_open_data_zip(raw, archive_name)
    selected = filter_administrative_open_data_items(parsed, versant="FPT")
    if not selected and not replace_existing:
        return {
            "archive": archive_name,
            "status": "NO_FPT_DECISIONS",
            "records_parsed": len(parsed),
            "records_selected": 0,
            "records_imported": 0,
            "records_rejected": 0,
        }

    run = await conn.fetchrow(
        """INSERT INTO legal_ingestion_runs(source_type,source_key,run_mode,status,query_text)
           VALUES('OTHER_OFFICIAL','JUSTICE_ADMIN_OPEN_DATA','BULK_XML_IMPORT','RUNNING',$1)
           RETURNING id""",
        archive_name[:250],
    )
    imported = rejected = deleted = 0
    try:
        async with conn.transaction():
            if replace_existing:
                deleted = await conn.fetchval(
                    """WITH removed AS (
                         DELETE FROM legal_documents
                         WHERE source_key='JUSTICE_ADMIN_OPEN_DATA'
                           AND raw_metadata->>'source_archive'=$1
                         RETURNING 1
                       )
                       SELECT count(*) FROM removed""",
                    archive_name[:250],
                )
            for item in selected:
                try:
                    async with conn.transaction():
                        await upsert_legal_document(conn, item)
                    imported += 1
                except (ValueError, TypeError):
                    rejected += 1
            status = "SUCCEEDED" if not rejected else "PARTIAL" if imported else "FAILED"
            error_summary = (
                f"{rejected} enregistrement(s) rejeté(s) par les contrôles de provenance ou de métadonnées."
                if rejected else None
            )
            await conn.execute(
                """UPDATE legal_ingestion_runs
                   SET status=$2,records_seen=$3,records_imported=$4,records_rejected=$5,
                       error_summary=$6,finished_at=now()
                   WHERE id=$1""",
                run["id"], status, len(parsed), imported, rejected, error_summary,
            )
        return {
            "archive": archive_name,
            "status": status,
            "records_parsed": len(parsed),
            "records_selected": len(selected),
            "records_imported": imported,
            "records_rejected": rejected,
            **({"records_replaced": deleted} if replace_existing else {}),
        }
    except Exception as exc:
        await conn.execute(
            "UPDATE legal_ingestion_runs SET status='FAILED',error_summary=$2,finished_at=now() WHERE id=$1",
            run["id"], type(exc).__name__,
        )
        raise

async def run(args) -> dict:
    start, end = parse_month(args.from_month), parse_month(args.to_month)
    months = list(month_range(start, end))
    courts = args.court or ["CE", "CAA", "TA"]
    if len(courts) != len(set(courts)):
        raise ValueError("Une juridiction ne doit être indiquée qu'une seule fois.")
    planned = []
    for court in courts:
        for month in months:
            try:
                url = administrative_open_data_archive_url(court, month.year, month.month)
            except ValueError:
                continue
            planned.append((court, month, url))
    if len(planned) > args.max_archives:
        raise ValueError(
            f"{len(planned)} archives sont prévues, au-delà de --max-archives={args.max_archives}. "
            "Réduire la période ou augmenter explicitement cette limite."
        )

    dsn = os.environ.get("LEGAL_CORPUS_INGEST_DATABASE_URL", "")
    conn = None
    if args.apply:
        validate_ingest_dsn(dsn)
        try:
            import asyncpg
        except ImportError as exc:
            raise RuntimeError("Dépendance asyncpg absente ; installer backend/requirements.txt.") from exc
        conn = await asyncpg.connect(dsn, command_timeout=180)

    results = []
    timeout = httpx.Timeout(90.0, connect=10.0)
    try:
        with httpx.Client(timeout=timeout, follow_redirects=False) as client:
            for index, (court, month, url) in enumerate(planned):
                archive_name = url.rsplit("/", 1)[-1]
                if conn is not None and not args.reimport_existing and not args.replace_archives:
                    if await archive_already_imported(conn, archive_name):
                        results.append({"archive": archive_name, "status": "ALREADY_IMPORTED"})
                        continue
                raw = download_archive(client, url)
                if raw is None:
                    results.append({"archive": archive_name, "status": "NOT_PUBLISHED"})
                else:
                    parsed = parse_administrative_open_data_zip(raw, archive_name)
                    selected = filter_administrative_open_data_items(parsed, versant="FPT")
                    if conn is None:
                        results.append({
                            "archive": archive_name,
                            "status": "DRY_RUN",
                            "records_parsed": len(parsed),
                            "records_selected": len(selected),
                        })
                    else:
                        results.append(await import_archive(
                            conn, court, month, archive_name, raw, parsed_items=parsed,
                            replace_existing=args.replace_archives,
                        ))
                if args.delay_seconds and index + 1 < len(planned):
                    time.sleep(args.delay_seconds)
    finally:
        if conn is not None:
            await conn.close()

    summary = {
        "mode": "APPLY" if args.apply else "DRY_RUN",
        "archives_planned": len(planned),
        "archives_processed": len(results),
        "records_selected": sum(int(row.get("records_selected", 0)) for row in results),
        "records_imported": sum(int(row.get("records_imported", 0)) for row in results),
        "records_rejected": sum(int(row.get("records_rejected", 0)) for row in results),
        "results": results,
    }
    if args.export_json:
        args.export_json.parent.mkdir(parents=True, exist_ok=True)
        args.export_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--court", action="append", choices=("CE", "CAA", "TA"), help="Juridiction (répétable ; défaut : CE, CAA, TA).")
    parser.add_argument("--from-month", required=True, help="Premier mois AAAA-MM.")
    parser.add_argument("--to-month", default=date.today().strftime("%Y-%m"), help="Dernier mois AAAA-MM (défaut : mois courant).")
    parser.add_argument("--max-archives", type=int, default=36, help="Garde-fou sur le nombre d'archives téléchargées.")
    parser.add_argument("--delay-seconds", type=float, default=1.0, help="Pause entre deux archives.")
    parser.add_argument("--apply", action="store_true", help="Écrit dans le corpus ; sans cette option, exécution en dry-run.")
    parser.add_argument("--reimport-existing", action="store_true", help="Force la réimportation des archives déjà réussies.")
    parser.add_argument(
        "--replace-archives", action="store_true",
        help="Remplace atomiquement les documents des seules archives demandées sur la base cible.",
    )
    parser.add_argument("--export-json", type=Path, help="Exporte le bilan JSON.")
    args = parser.parse_args()
    if args.max_archives < 1 or args.delay_seconds < 0 or args.delay_seconds > 30:
        parser.error("--max-archives doit être positif et --delay-seconds compris entre 0 et 30.")
    if args.replace_archives and not args.apply:
        parser.error("--replace-archives exige --apply.")
    try:
        summary = asyncio.run(run(args))
    except Exception as exc:
        print(f"ERREUR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({key: value for key, value in summary.items() if key != "results"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
