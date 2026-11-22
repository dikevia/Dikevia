#!/usr/bin/env python3
"""Operator-run, dry-run-first purge for expired private conversations.

The cutoff is supplied explicitly by the operator after approval of the
retention policy. This script intentionally has no default retention period
and is not scheduled or invoked by the API.
"""
import argparse
import asyncio
from collections import Counter
from datetime import datetime
import json
import os
import sys


def parse_cutoff(value: str) -> datetime:
    """Parse an explicit ISO-8601 timestamp and require a timezone."""
    try:
        cutoff = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Date ISO-8601 invalide.") from exc
    if cutoff.tzinfo is None or cutoff.utcoffset() is None:
        raise argparse.ArgumentTypeError("Le seuil doit inclure un fuseau horaire (ex. Z).")
    return cutoff


def validate_confirmation(execute: bool, confirm_delete: bool) -> None:
    if confirm_delete and not execute:
        raise ValueError("--confirm-delete nécessite aussi --execute.")
    if execute and not confirm_delete:
        raise ValueError("--execute exige --confirm-delete.")


async def run_purge(database_url: str, cutoff: datetime, execute: bool) -> dict:
    try:
        import asyncpg
    except ImportError as exc:
        raise RuntimeError("Le pilote asyncpg est requis.") from exc

    conn = await asyncpg.connect(database_url, command_timeout=30)
    try:
        role = await conn.fetchrow(
            """SELECT r.rolsuper, r.rolbypassrls
               FROM pg_roles r WHERE r.rolname = current_user"""
        )
        if not role or not (role["rolsuper"] or role["rolbypassrls"]):
            raise RuntimeError(
                "Le compte de purge doit être explicitement autorisé à contourner RLS."
            )

        async with conn.transaction():
            if not execute:
                rows = await conn.fetch(
                    """SELECT organization_id, count(*) AS conversations
                       FROM chat_conversations
                       WHERE updated_at < $1
                       GROUP BY organization_id
                       ORDER BY organization_id""",
                    cutoff,
                )
                counts = {str(row["organization_id"]): row["conversations"] for row in rows}
                return {"mode": "dry_run", "cutoff": cutoff.isoformat(),
                        "conversations": sum(counts.values()), "by_organization": counts}

            deleted = await conn.fetch(
                """DELETE FROM chat_conversations
                   WHERE updated_at < $1
                   RETURNING organization_id""",
                cutoff,
            )
            counts = Counter(str(row["organization_id"]) for row in deleted)
            return {"mode": "execute", "cutoff": cutoff.isoformat(),
                    "conversations": len(deleted), "by_organization": dict(sorted(counts.items()))}
    finally:
        await conn.close()


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cutoff", required=True, type=parse_cutoff,
        help="Seuil absolu ISO-8601 avec fuseau, à définir selon la politique approuvée.",
    )
    parser.add_argument("--execute", action="store_true", help="Effectue réellement la suppression.")
    parser.add_argument("--confirm-delete", action="store_true",
                        help="Confirmation obligatoire en complément de --execute.")
    args = parser.parse_args(argv)
    try:
        validate_confirmation(args.execute, args.confirm_delete)
    except ValueError as exc:
        parser.error(str(exc))
    return args


def main(argv=None) -> int:
    args = parse_args(argv)
    database_url = os.environ.get("RETENTION_DATABASE_URL", "")
    if not database_url:
        print("RETENTION_DATABASE_URL doit être configurée explicitement.", file=sys.stderr)
        return 2
    try:
        result = asyncio.run(run_purge(database_url, args.cutoff, args.execute))
    except Exception as exc:
        print(f"Échec de la purge : {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
