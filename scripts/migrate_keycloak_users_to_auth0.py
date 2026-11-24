"""Import existing Keycloak identities into Auth0 while preserving Dikévia subjects.

Dry-run by default. Writes to Auth0 only with --apply; full migration additionally
requires --confirm-full-migration. PostgreSQL is queried read-only.
"""
import argparse
import asyncio
import os
import secrets
import string
from urllib.parse import quote, urlparse

import asyncpg
import httpx

from app.mailer import send_auth0_migration_email


def normalize_domain(value: str) -> str:
    raw = value.strip()
    parsed = urlparse(raw if "://" in raw else "https://" + raw)
    if not parsed.hostname or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ValueError("AUTH0_DOMAIN doit être un domaine ou une origine HTTPS sans chemin.")
    if parsed.scheme != "https":
        raise ValueError("AUTH0_DOMAIN doit utiliser HTTPS.")
    return parsed.hostname


def make_temporary_password(length: int = 48) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%_-"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Variable requise absente : {name}")
    return value


async def keycloak_service_token(client: httpx.AsyncClient, base_url: str,
                                 realm: str, client_id: str, client_secret: str) -> str:
    response = await client.post(
        f"{base_url.rstrip('/')}/realms/{realm}/protocol/openid-connect/token",
        data={"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret},
    )
    response.raise_for_status()
    token = response.json().get("access_token")
    if not token:
        raise RuntimeError("Jeton de service Keycloak absent.")
    return token


async def keycloak_user_by_email(client: httpx.AsyncClient, base_url: str, realm: str,
                                 token: str, email: str) -> dict:
    response = await client.get(
        f"{base_url.rstrip('/')}/admin/realms/{realm}/users",
        headers={"Authorization": f"Bearer {token}"},
        params={"email": email, "exact": "true"},
    )
    response.raise_for_status()
    matches = response.json()
    if len(matches) != 1:
        raise RuntimeError("Compte source Keycloak absent ou ambigu ; migration interrompue.")
    user = matches[0]
    if user.get("enabled") is not True or user.get("email") != email:
        raise RuntimeError("Compte source Keycloak désactivé ou adresse incohérente.")
    return user


async def auth0_management_token(client: httpx.AsyncClient, domain: str,
                                 client_id: str, client_secret: str) -> str:
    response = await client.post(
        f"https://{domain}/oauth/token",
        json={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "audience": f"https://{domain}/api/v2/",
        },
    )
    response.raise_for_status()
    token = response.json().get("access_token")
    if not token:
        raise RuntimeError("Jeton Management API Auth0 absent.")
    return token


async def auth0_get_user(client: httpx.AsyncClient, domain: str, token: str, user_id: str) -> dict | None:
    response = await client.get(
        f"https://{domain}/api/v2/users/{quote(user_id, safe='')}",
        headers={"Authorization": f"Bearer {token}"},
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


async def auth0_users_by_email(client: httpx.AsyncClient, domain: str, token: str, email: str) -> list[dict]:
    response = await client.get(
        f"https://{domain}/api/v2/users-by-email",
        headers={"Authorization": f"Bearer {token}"},
        params={"email": email},
    )
    response.raise_for_status()
    return response.json()


def validate_existing_auth0_user(existing: dict | None, expected_id: str, email: str) -> None:
    """Fail closed if a pre-existing Auth0 subject is not the expected account."""
    if existing is None:
        return
    if existing.get("user_id") != expected_id:
        raise RuntimeError("Identifiant Auth0 existant incohérent ; arrêt de sécurité.")
    if str(existing.get("email") or "").strip().lower() != email.strip().lower():
        raise RuntimeError("Identifiant Auth0 déjà utilisé par une autre adresse ; arrêt de sécurité.")


async def create_auth0_user(client: httpx.AsyncClient, domain: str, token: str,
                            connection: str, source: dict, email: str) -> dict:
    expected_id = "auth0|" + source["id"]
    existing = await auth0_get_user(client, domain, token, expected_id)
    validate_existing_auth0_user(existing, expected_id, email)
    if existing:
        return existing

    by_email = await auth0_users_by_email(client, domain, token, email)
    if by_email:
        raise RuntimeError("Un compte Auth0 existe déjà pour cette adresse avec un autre identifiant.")

    payload = {
        "connection": connection,
        "user_id": source["id"],
        "email": email,
        "email_verified": source.get("emailVerified") is True,
        "password": make_temporary_password(),
        "verify_email": False,
    }
    if source.get("firstName") or source.get("lastName"):
        payload["name"] = " ".join(
            part for part in (source.get("firstName"), source.get("lastName")) if part
        )
    response = await client.post(
        f"https://{domain}/api/v2/users",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    if response.status_code == 409:
        existing = await auth0_get_user(client, domain, token, expected_id)
        if existing:
            validate_existing_auth0_user(existing, expected_id, email)
            return existing
    response.raise_for_status()
    created = response.json()
    if created.get("user_id") != expected_id:
        raise RuntimeError("Auth0 n'a pas conservé l'identifiant historique attendu.")
    return created


async def create_user_ticket(client: httpx.AsyncClient, domain: str, token: str,
                             user_id: str, client_id: str, verified: bool) -> str:
    endpoint = "email-verification" if not verified else "password-change"
    payload = {"user_id": user_id, "client_id": client_id, "ttl_sec": 86400}
    response = await client.post(
        f"https://{domain}/api/v2/tickets/{endpoint}",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    response.raise_for_status()
    ticket = response.json().get("ticket")
    if not isinstance(ticket, str) or not ticket.startswith("https://"):
        raise RuntimeError("Auth0 n'a pas retourné de ticket HTTPS valide.")
    return ticket


async def load_source_users(database_url: str, legacy_issuer: str) -> list[dict]:
    connection = await asyncpg.connect(database_url, command_timeout=20)
    try:
        async with connection.transaction(readonly=True):
            rows = await connection.fetch(
                """SELECT oidc_subject, email, display_name
                   FROM users
                   WHERE oidc_issuer=$1 AND status='ACTIVE'
                   ORDER BY created_at, oidc_subject""",
                legacy_issuer,
            )
            return [dict(row) for row in rows]
    finally:
        await connection.close()


async def migrate(args: argparse.Namespace) -> None:
    legacy_issuer = required_env("OIDC_IDENTITY_COMPAT_ISSUER")
    users = await load_source_users(required_env("PLATFORM_ADMIN_DATABASE_URL"), legacy_issuer)
    if args.subject:
        users = [user for user in users if user["oidc_subject"] == args.subject]
        if len(users) != 1:
            raise RuntimeError("Le sujet pilote n'existe pas ou n'est pas unique.")
    if args.limit:
        users = users[:args.limit]
    if not users:
        raise RuntimeError("Aucun compte actif à migrer.")
    emails = [str(user["email"] or "").strip().lower() for user in users]
    if any(not email for email in emails):
        raise RuntimeError("Au moins un compte actif ne possède pas d'adresse e-mail ; migration interrompue.")
    if len(set(emails)) != len(emails):
        raise RuntimeError("Adresses e-mail en doublon dans le registre Dikévia ; migration interrompue.")

    if not args.apply:
        print(f"DRY RUN : {len(users)} comptes actifs à contrôler/importer. Aucune écriture effectuée.")
        return
    if not args.subject and not args.limit and not args.confirm_full_migration:
        raise RuntimeError("Pour un import global, ajouter --confirm-full-migration. Tester d'abord un compte pilote.")
    if not args.subject and args.limit and args.limit > 10:
        raise RuntimeError("Le pilote est limité à 10 comptes maximum.")

    domain = normalize_domain(required_env("AUTH0_DOMAIN"))
    auth0_client_id = required_env("AUTH0_MGMT_CLIENT_ID")
    auth0_client_secret = required_env("AUTH0_MGMT_CLIENT_SECRET")
    auth0_spa_client_id = required_env("OIDC_CLIENT_ID")
    connection_name = os.getenv("AUTH0_DATABASE_CONNECTION", "Username-Password-Authentication")
    keycloak_url = required_env("KEYCLOAK_ADMIN_BASE_URL")
    keycloak_realm = os.getenv("KEYCLOAK_ADMIN_REALM", "cfdt")
    keycloak_client_id = required_env("KEYCLOAK_ADMIN_CLIENT_ID")
    keycloak_client_secret = required_env("KEYCLOAK_ADMIN_CLIENT_SECRET")
    smtp_host = required_env("SMTP_HOST")
    smtp_from = required_env("SMTP_FROM")
    app_url = required_env("INVITATION_BASE_URL").rstrip("/") + "/"
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_username = os.getenv("SMTP_USERNAME", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")

    timeout = httpx.Timeout(20)
    async with httpx.AsyncClient(timeout=timeout) as client:
        kc_token = await keycloak_service_token(
            client, keycloak_url, keycloak_realm, keycloak_client_id, keycloak_client_secret
        )
        auth0_token = await auth0_management_token(
            client, domain, auth0_client_id, auth0_client_secret
        )

        # Preflight all source accounts before the first Auth0 write.
        sources = []
        for user in users:
            email = str(user["email"]).strip().lower()
            source = await keycloak_user_by_email(client, keycloak_url, keycloak_realm, kc_token, email)
            if source.get("id") != user["oidc_subject"]:
                raise RuntimeError("L'identifiant Keycloak ne correspond pas au sujet PostgreSQL ; arrêt de sécurité.")
            expected_id = "auth0|" + source["id"]
            existing = await auth0_get_user(client, domain, auth0_token, expected_id)
            validate_existing_auth0_user(existing, expected_id, email)
            if not existing and await auth0_users_by_email(client, domain, auth0_token, email):
                raise RuntimeError("Un compte Auth0 existant utilise déjà une adresse à migrer.")
            sources.append((user, source, existing))

        completed = 0
        for user, source, existing in sources:
            email = str(user["email"]).strip().lower()
            auth0_user = existing or await create_auth0_user(
                client, domain, auth0_token, connection_name, source, email
            )
            verified = auth0_user.get("email_verified") is True
            ticket = await create_user_ticket(
                client, domain, auth0_token, auth0_user["user_id"], auth0_spa_client_id, verified
            )
            await asyncio.to_thread(
                send_auth0_migration_email,
                smtp_host, smtp_port, smtp_username, smtp_password, smtp_from,
                email, ticket, "password" if verified else "verification", True,
            )
            completed += 1
            print(f"Compte migré et e-mail de sécurisation envoyé : {completed}/{len(sources)}")
    print(f"Import terminé : {completed} compte(s). Les comptes PostgreSQL et leurs appartenances n'ont pas été modifiés.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Effectuer les créations Auth0 et envoyer les tickets.")
    parser.add_argument("--subject", help="Migrer un seul sujet OIDC historique pour le pilote.")
    parser.add_argument("--limit", type=int, help="Limiter le pilote à N comptes (maximum 10 sans sujet explicite).")
    parser.add_argument("--confirm-full-migration", action="store_true",
                        help="Confirmer explicitement l'import global après validation du pilote.")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit doit être supérieur ou égal à 1.")
    if args.subject and args.limit:
        parser.error("--subject et --limit ne peuvent pas être combinés.")
    return args


if __name__ == "__main__":
    asyncio.run(migrate(parse_args()))
