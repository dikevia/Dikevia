#!/usr/bin/env python3
"""Append new variables and rotate only known template placeholders in an env file."""
from __future__ import annotations
import argparse
import secrets
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]


def active_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if re.fullmatch(r"[A-Z][A-Z0-9_]*", key.strip()):
            values[key.strip()] = value.strip()
    return values


def build_generated_secrets(current: dict[str, str]) -> dict[str, str]:
    def secret_for(key: str) -> str:
        value = current.get(key, "")
        if value and "CHANGE_ME_" not in value:
            return value
        source_url = current.get("DATABASE_URL", "") if key == "POSTGRES_APP_PASSWORD" else current.get("LEGAL_CORPUS_INGEST_DATABASE_URL", "") if key == "POSTGRES_INGEST_PASSWORD" else current.get("PLATFORM_ADMIN_DATABASE_URL", "") if key == "POSTGRES_PLATFORM_ADMIN_PASSWORD" else ""
        parsed_password = urlparse(source_url).password if source_url else None
        if parsed_password and "CHANGE_ME_" not in parsed_password:
            return unquote(parsed_password)
        return secrets.token_urlsafe(32)
    return {
        "CHANGE_ME_MIGRATION": secret_for("POSTGRES_MIGRATION_PASSWORD"),
        "CHANGE_ME_RUNTIME": secret_for("POSTGRES_APP_PASSWORD"),
        "CHANGE_ME_INGEST": secret_for("POSTGRES_INGEST_PASSWORD"),
        "CHANGE_ME_MONITOR": secret_for("POSTGRES_MONITOR_PASSWORD"),
        "CHANGE_ME_PLATFORM_ADMIN": secret_for("POSTGRES_PLATFORM_ADMIN_PASSWORD"),
        "CHANGE_ME_KEYCLOAK_DB": secret_for("KEYCLOAK_DB_PASSWORD"),
        "CHANGE_ME_KEYCLOAK_ADMIN": secret_for("KEYCLOAK_ADMIN_PASSWORD"),
        "CHANGE_ME_GRAFANA_ADMIN": secret_for("GRAFANA_ADMIN_PASSWORD"),
    }


def merge_env_content(content: str, current: dict[str, str], defaults: dict[str, str]) -> tuple[str, int]:
    generated = build_generated_secrets(current)
    for token, secret in generated.items():
        content = content.replace(token, secret)
    resolved_defaults = {}
    for key, value in defaults.items():
        for token, secret in generated.items():
            value = value.replace(token, secret)
        resolved_defaults[key] = value

    updated = 0
    output_lines = []
    seen = set()
    for line in content.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key, value = stripped.split("=", 1)
            key = key.strip()
            if key in resolved_defaults:
                seen.add(key)
                old_value = current.get(key, value.strip())
                if not old_value or "CHANGE_ME_" in old_value:
                    line = f"{key}={resolved_defaults[key]}"
                    updated += 1
        output_lines.append(line)

    additions = [f"{key}={value}" for key, value in resolved_defaults.items() if key not in seen]
    if additions:
        output_lines.extend(["", "# Variables ajoutées lors de la mise à niveau CFDT JURIS V3.22", *additions])
    return "\n".join(output_lines) + "\n", updated + len(additions)


def validate_database_passwords(content: str) -> None:
    values = {}
    for raw in content.splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    pairs = (("DATABASE_URL", "POSTGRES_APP_PASSWORD", "cfdt_juris_app"),
             ("LEGAL_CORPUS_INGEST_DATABASE_URL", "POSTGRES_INGEST_PASSWORD", "cfdt_juris_ingest"),
             ("PLATFORM_ADMIN_DATABASE_URL", "POSTGRES_PLATFORM_ADMIN_PASSWORD", "cfdt_juris_platform_admin"))
    for url_key, password_key, expected_user in pairs:
        if not values.get(url_key) or not values.get(password_key):
            continue
        parsed = urlparse(values[url_key])
        if parsed.username == expected_user and unquote(parsed.password or "") != values[password_key]:
            raise SystemExit(f"Incohérence entre {url_key} et {password_key} : harmonisez le mot de passe avant déploiement.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staging", action="store_true")
    args = parser.parse_args()
    target = ROOT / (".env.staging" if args.staging else ".env")
    template = ROOT / "deploy" / (".env.staging.example" if args.staging else ".env.example")
    if not target.is_file():
        raise SystemExit(f"{target.name} absent ; créez-le avec scripts/prepare_dev_env.py.")
    current = active_values(target)
    defaults = active_values(template)
    if "COMPOSE_PROJECT_NAME" not in current:
        raise SystemExit(
            f"{target.name} ne définit pas COMPOSE_PROJECT_NAME. Pour une base existante, "
            "identifiez le nom du projet Compose actuellement utilisé (docker compose ls / labels des volumes) "
            "et ajoutez COMPOSE_PROJECT_NAME=... avant de continuer ; ne choisissez pas un nom au hasard, "
            "cela pourrait créer un nouveau volume PostgreSQL vide."
        )
    content, added_count = merge_env_content(target.read_text(encoding="utf-8"), current, defaults)
    validate_database_passwords(content)
    target.write_text(content, encoding="utf-8")
    target.chmod(0o600)
    print(f"{target.name}: {added_count} variable(s) ajoutée(s) ou complétée(s), valeurs existantes conservées hors placeholders.")
    if args.staging:
        print("Vérifiez les domaines HTTPS et renseignez les clés PISTE sandbox / Stripe test avant recette.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
