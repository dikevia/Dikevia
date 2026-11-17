#!/usr/bin/env python3
"""Safe, checksum-tracked PostgreSQL migration runner for CFDT JURIS.

The consolidated schema.sql is the installation baseline through migration 009.
Existing V3.20 databases are adopted at baseline 008 and then apply migration 009.
Migrations 001-008 are historical/non-reversible; migration 009 has an explicit,
destructive down SQL for V3.20 upgrades. Migrations 010 and 011 add the current subscription catalog, free-email allowlist and commercial invoice console. New migrations require a matching down
SQL file under database/migrations/rollback/ before they can be applied.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "database" / "migrations"
ROLLBACKS = MIGRATIONS / "rollback"
BASELINE_VERSION = 9
MINIMUM_BASELINE_VERSION = 8
LOCK_ID = 7312026
REQUIRED_V8_TABLES = {
    "organizations", "users", "platform_admins", "memberships", "collectivities",
    "documents", "document_versions", "document_relations", "invitations",
    "organization_settings", "subscriptions", "audit_events", "billing_webhook_events",
    "document_text",
}
LEGAL_CORPUS_TABLES = {
    "legal_documents", "legal_document_versions", "legal_chunks",
    "legal_document_relations", "legal_ingestion_runs",
}
MIGRATION_RE = re.compile(r"^(\d{3})_(.+)\.sql$")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def migration_files() -> list[tuple[int, Path]]:
    found = []
    for path in MIGRATIONS.glob("[0-9][0-9][0-9]_*.sql"):
        match = MIGRATION_RE.match(path.name)
        if match:
            found.append((int(match.group(1)), path))
    return sorted(found)


def down_path(up_path: Path) -> Path:
    return ROLLBACKS / f"{up_path.stem}.down.sql"


def strip_transaction_wrappers(sql: str) -> str:
    # Match standalone transaction-control lines even when SQL comments precede BEGIN.
    # PL/pgSQL function bodies use bare BEGIN (without a semicolon), so they are untouched.
    sql = re.sub(r"(?im)^\s*BEGIN\s*;\s*$", "", sql, count=1)
    sql = re.sub(r"(?im)^\s*COMMIT\s*;\s*$", "", sql, count=1)
    return sql


async def connect():
    try:
        import asyncpg
    except ImportError as exc:  # pragma: no cover - environment-specific
        raise RuntimeError("Dépendance absente : installer backend/requirements.txt (asyncpg).") from exc
    import os
    url = os.getenv("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL doit être défini dans l'environnement.")
    return await asyncpg.connect(url, command_timeout=120)


async def ensure_ledger(conn) -> None:
    await conn.execute("""
      CREATE TABLE IF NOT EXISTS schema_migrations (
        version integer PRIMARY KEY,
        name text NOT NULL,
        checksum char(64) NOT NULL,
        applied_at timestamptz NOT NULL DEFAULT now(),
        applied_by text NOT NULL DEFAULT current_user
      )
    """)
    await conn.execute("REVOKE ALL ON schema_migrations FROM PUBLIC")


async def baseline(conn) -> None:
    await ensure_ledger(conn)
    rows = await conn.fetch("""
      SELECT table_name FROM information_schema.tables
      WHERE table_schema='public' AND table_type='BASE TABLE'
    """)
    present = {r["table_name"] for r in rows}
    missing = sorted(REQUIRED_V8_TABLES - present)
    if missing:
        raise RuntimeError("Schéma antérieur à V3.20 ou incomplet ; tables absentes : " + ", ".join(missing))
    functions = await conn.fetchval("""
      SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
      WHERE n.nspname='public' AND p.proname IN ('platform_admin_list_organizations','platform_admin_set_organization_status')
    """)
    if functions != 2:
        raise RuntimeError("Fonctions d'administration plateforme absentes ; migration 008 non confirmée.")
    corpus_present = LEGAL_CORPUS_TABLES & present
    if corpus_present and corpus_present != LEGAL_CORPUS_TABLES:
        raise RuntimeError("Corpus juridique partiel détecté ; vérifier/restaurer la base avant baseline.")
    schema_file = ROOT / "database" / "schema.sql"
    if corpus_present:
        version, name, checksum = BASELINE_VERSION, "baseline_schema_v3_21", sha256(schema_file.read_bytes())
    else:
        version, name, checksum = 8, "baseline_schema_v3_20", sha256(b"CFDT_JURIS_BASELINE_V3_20_SCHEMA_008")
    existing_rows = await conn.fetch("SELECT version,name,checksum FROM schema_migrations ORDER BY version")
    if existing_rows:
        baseline_rows = [r for r in existing_rows if r["name"].startswith("baseline_schema_")]
        if len(baseline_rows) == 1 and baseline_rows[0]["version"] in {8, 9}:
            print(f"Baseline V{baseline_rows[0]['version']} déjà enregistrée ; aucune modification.")
            return
        raise RuntimeError("Le registre de migrations ne contient pas une baseline reconnue ; baseline refusée.")
    await conn.execute(
        "INSERT INTO schema_migrations(version,name,checksum) VALUES($1,$2,$3)",
        version, name, checksum,
    )
    print(f"Baseline V{version} enregistrée ({len(present)} tables publiques contrôlées).")


async def status(conn) -> None:
    exists = await conn.fetchval("SELECT to_regclass('public.schema_migrations') IS NOT NULL")
    if not exists:
        print("Registre absent. Après vérification du schéma consolidé, exécuter : baseline")
        return
    applied = await conn.fetch("SELECT version,name,checksum,applied_at FROM schema_migrations ORDER BY version")
    current = max((r["version"] for r in applied), default=0)
    print(f"Version DB : {current}")
    known = {r["version"]: r for r in applied}
    baseline_version = max((r["version"] for r in applied if r["name"].startswith("baseline_schema_")), default=0)
    for version, path in migration_files():
        if version <= baseline_version:
            state = f"INCLUS DANS LE BASELINE V{baseline_version}"
        elif version in known:
            expected = sha256(path.read_bytes())
            state = "APPLIQUÉ" if known[version]["checksum"].strip() == expected else "ALERTE: CHECKSUM MODIFIÉ"
        elif version > current:
            state = "EN ATTENTE" if down_path(path).is_file() else "EN ATTENTE — down.sql manquant, application bloquée"
        else:
            state = "NON RÉPERTORIÉ — vérifier manuellement"
        print(f"{version:03d} {path.name}: {state}")


async def upgrade(conn) -> None:
    await ensure_ledger(conn)
    current = await conn.fetchval("SELECT COALESCE(MAX(version),0) FROM schema_migrations")
    if current < MINIMUM_BASELINE_VERSION:
        raise RuntimeError("Baseline absente ou schéma trop ancien. Vérifier la base avant de migrer.")
    applied = {r["version"]: r for r in await conn.fetch("SELECT version,name,checksum FROM schema_migrations")}
    for version, path in migration_files():
        if version <= current:
            if version in applied and not applied[version]["name"].startswith("baseline_schema_"):
                if applied[version]["checksum"].strip() != sha256(path.read_bytes()):
                    raise RuntimeError(f"Checksum différent pour la migration déjà appliquée {path.name}.")
            continue
        if version != current + 1:
            raise RuntimeError(f"Séquence de migrations discontinue : attendu {current + 1:03d}, trouvé {version:03d}.")
        if not down_path(path).is_file():
            raise RuntimeError(f"Migration {path.name} refusée : fournir {down_path(path).relative_to(ROOT)} avant application.")
        sql = strip_transaction_wrappers(path.read_text(encoding="utf-8"))
        digest = sha256(path.read_bytes())
        print(f"Application {path.name}…")
        async with conn.transaction():
            await conn.execute(sql)
            await conn.execute(
                "INSERT INTO schema_migrations(version,name,checksum) VALUES($1,$2,$3)",
                version, path.stem, digest,
            )
        current = version
        print(f"Migration {version:03d} appliquée.")
    print(f"Base à jour : version {current}.")


async def rollback(conn, version: int, confirmation: str, allow_data_loss: bool) -> None:
    if confirmation != str(version) or not allow_data_loss:
        raise RuntimeError("Rollback refusé : fournir --confirm VERSION et --allow-data-loss explicitement.")
    await ensure_ledger(conn)
    latest = await conn.fetchrow("SELECT version,name,checksum FROM schema_migrations ORDER BY version DESC LIMIT 1")
    if not latest or latest["version"] != version:
        raise RuntimeError("Seule la dernière migration enregistrée peut être annulée.")
    if version < MINIMUM_BASELINE_VERSION:
        raise RuntimeError("Les versions 001-007 sont le socle historique : restauration d'une sauvegarde requise.")
    if version == BASELINE_VERSION and latest["name"] == "baseline_schema_v3_21":
        raise RuntimeError("La version 009 est incluse dans le baseline V3.21 : restauration d'une sauvegarde requise.")
    up = next((p for v, p in migration_files() if v == version), None)
    if up is None:
        raise RuntimeError("Fichier de migration d'origine introuvable.")
    down = down_path(up)
    if not down.is_file():
        raise RuntimeError(f"Rollback indisponible : fichier {down.relative_to(ROOT)} absent.")
    if latest["name"] != up.stem or latest["checksum"].strip() != sha256(up.read_bytes()):
        raise RuntimeError("Nom ou checksum de la migration appliquée différent du fichier présent ; rollback bloqué.")
    print(f"ATTENTION : exécution du rollback {down.name}.")
    async with conn.transaction():
        await conn.execute(strip_transaction_wrappers(down.read_text(encoding="utf-8")))
        await conn.execute("DELETE FROM schema_migrations WHERE version=$1", version)
    print(f"Migration {version:03d} annulée.")


async def run(args) -> None:
    conn = await connect()
    try:
        await conn.execute("SELECT pg_advisory_lock($1)", LOCK_ID)
        if args.command == "baseline":
            await baseline(conn)
        elif args.command == "status":
            await status(conn)
        elif args.command == "upgrade":
            await upgrade(conn)
        elif args.command == "rollback":
            await rollback(conn, args.version, args.confirm, args.allow_data_loss)
    finally:
        try:
            await conn.execute("SELECT pg_advisory_unlock($1)", LOCK_ID)
        finally:
            await conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Gestion sécurisée des migrations PostgreSQL CFDT JURIS")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("baseline", help="Enregistre le schéma existant comme baseline V8 ou V9 après contrôles")
    sub.add_parser("status", help="Affiche l'état et les checksums des migrations")
    sub.add_parser("upgrade", help="Applique les nouvelles migrations dans une transaction")
    rb = sub.add_parser("rollback", help="Annule uniquement la dernière migration réversible")
    rb.add_argument("--version", type=int, required=True)
    rb.add_argument("--confirm", required=True, help="Répéter exactement le numéro de version")
    rb.add_argument("--allow-data-loss", action="store_true", help="Confirmation explicite du risque de perte de données")
    args = parser.parse_args()
    try:
        asyncio.run(run(args))
    except Exception as exc:
        print(f"ERREUR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
