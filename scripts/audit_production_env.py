#!/usr/bin/env python3
"""Fail-closed preflight for production/staging environment files."""
from __future__ import annotations
import argparse
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_SECRET_KEYS = (
    "POSTGRES_MIGRATION_PASSWORD", "POSTGRES_APP_PASSWORD", "POSTGRES_INGEST_PASSWORD",
    "POSTGRES_MONITOR_PASSWORD",
)
URL_PASSWORDS = {"DATABASE_URL": "cfdt_juris_app", "LEGAL_CORPUS_INGEST_DATABASE_URL": "cfdt_juris_ingest"}
PLACEHOLDERS = ("CHANGE_ME_", "your-secret", "replace-me", "example-password")


def read_env(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if re.fullmatch(r"[A-Z][A-Z0-9_]*", key.strip()):
            result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def audit(path: Path) -> list[str]:
    values = read_env(path)
    errors: list[str] = []
    if values.get("APP_ENV") != "production":
        errors.append("APP_ENV doit être production.")
    if values.get("DEBUG", "").lower() not in {"false", "0", "no", "off"}:
        errors.append("DEBUG doit être explicitement défini à false.")
    template_path = ROOT / "deploy" / (".env.staging.example" if "staging" in path.name else ".env.example")
    template = read_env(template_path)
    secret_values: dict[str, str] = {}
    for key in REQUIRED_SECRET_KEYS:
        value = values.get(key, "")
        if len(value) < 32 or any(marker.lower() in value.lower() for marker in PLACEHOLDERS):
            errors.append(f"{key} absent, valeur de démonstration ou longueur inférieure à 32 caractères.")
        elif value in secret_values.values():
            other = next(k for k, v in secret_values.items() if v == value)
            errors.append(f"Secrets réutilisés : {other} et {key}.")
        else:
            secret_values[key] = value
        if key in template and value == template[key]:
            errors.append(f"{key} reprend la valeur du fichier .env.example.")

    for key, value in values.items():
        if key in REQUIRED_SECRET_KEYS or not value:
            continue
        if key.endswith(("_PASSWORD", "_SECRET", "_API_KEY")) or key == "STRIPE_SECRET_KEY":
            if len(value) < 32 or any(marker.lower() in value.lower() for marker in PLACEHOLDERS):
                errors.append(f"{key} configuré mais trop court ou de démonstration (32 caractères minimum).")
            elif value in secret_values.values():
                other = next(k for k, v in secret_values.items() if v == value)
                errors.append(f"Secrets réutilisés : {other} et {key}.")
            else:
                secret_values[key] = value

    for url_key, expected_user in URL_PASSWORDS.items():
        raw = values.get(url_key, "")
        parsed = urlparse(raw)
        password = unquote(parsed.password or "")
        if parsed.scheme not in {"postgres", "postgresql"} or parsed.username != expected_user:
            errors.append(f"{url_key} doit utiliser PostgreSQL et le rôle {expected_user}.")
        elif len(password) < 32 or any(marker.lower() in password.lower() for marker in PLACEHOLDERS):
            errors.append(f"Mot de passe intégré à {url_key} trop court ou de démonstration.")
        elif password != values.get("POSTGRES_APP_PASSWORD" if expected_user == "cfdt_juris_app" else "POSTGRES_INGEST_PASSWORD"):
            errors.append(f"Mot de passe de {url_key} incohérent avec le secret PostgreSQL dédié.")

    for key in ("PUBLIC_APP_URL", "OIDC_ISSUER", "OIDC_JWKS_URL", "OIDC_IDENTITY_COMPAT_ISSUER"):
        parsed = urlparse(values.get(key, ""))
        if parsed.scheme != "https" or not parsed.hostname:
            errors.append(f"{key} doit être une URL HTTPS réelle en production.")
    if values.get("OIDC_PROVIDER") != "auth0":
        errors.append("OIDC_PROVIDER doit être auth0.")
    if not values.get("OIDC_CLIENT_ID"):
        errors.append("OIDC_CLIENT_ID doit être renseigné pour Auth0.")
    if not values.get("OIDC_AUDIENCE") or values.get("OIDC_AUTHORIZATION_AUDIENCE") != values.get("OIDC_AUDIENCE"):
        errors.append("OIDC_AUTHORIZATION_AUDIENCE doit être renseignée et identique à OIDC_AUDIENCE.")
    if values.get("OIDC_IDENTITY_SUBJECT_PREFIX") != "auth0|":
        errors.append("OIDC_IDENTITY_SUBJECT_PREFIX doit conserver le préfixe Auth0 historique auth0|.")
    if values.get("OIDC_ALGORITHMS", "") not in {"RS256", "ES256"}:
        errors.append("OIDC_ALGORITHMS doit être RS256 ou ES256 uniquement.")
    origins = [x.strip() for x in values.get("CORS_ORIGINS", "").split(",") if x.strip()]
    if not origins or "*" in origins or any(urlparse(x).scheme != "https" for x in origins):
        errors.append("CORS_ORIGINS doit contenir uniquement des origines HTTPS explicites.")
    if not values.get("BACKUP_AGE_RECIPIENT", "").startswith("age1"):
        errors.append("BACKUP_AGE_RECIPIENT doit être une clé publique age1... (sauvegarde chiffrée obligatoire).")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, required=True)
    args = parser.parse_args()
    path = args.env_file if args.env_file.is_absolute() else ROOT / args.env_file
    if not path.is_file():
        raise SystemExit(f"Fichier absent : {path}")
    errors = audit(path)
    if errors:
        print(f"ÉCHEC préproduction : {len(errors)} contrôle(s) bloquant(s)")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"OK : contrôles secrets, HTTPS, OIDC, CORS, DEBUG et chiffrement validés pour {path.name}.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
