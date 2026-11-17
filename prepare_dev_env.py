#!/usr/bin/env python3
"""Create a local .env (or .env.staging) with fresh random infrastructure secrets."""
from __future__ import annotations
import argparse
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staging", action="store_true", help="Prepare .env.staging from the staging template")
    args = parser.parse_args()
    template_name = ".env.staging.example" if args.staging else ".env.example"
    output_name = ".env.staging" if args.staging else ".env"
    template = (ROOT / "deploy" / template_name).read_text(encoding="utf-8")
    tokens = {
        "CHANGE_ME_MIGRATION": secrets.token_urlsafe(32),
        "CHANGE_ME_RUNTIME": secrets.token_urlsafe(32),
        "CHANGE_ME_INGEST": secrets.token_urlsafe(32),
        "CHANGE_ME_MONITOR": secrets.token_urlsafe(32),
        "CHANGE_ME_KEYCLOAK_DB": secrets.token_urlsafe(32),
        "CHANGE_ME_KEYCLOAK_ADMIN": secrets.token_urlsafe(32),
        "CHANGE_ME_GRAFANA_ADMIN": secrets.token_urlsafe(32),
    }
    for old, new in tokens.items():
        template = template.replace(old, new)
    output = ROOT / output_name
    if output.exists():
        raise SystemExit(f"{output_name} existe déjà ; refus de l'écraser.")
    output.write_text(template, encoding="utf-8")
    output.chmod(0o600)
    print(f"Fichier {output_name} créé avec des secrets aléatoires (droits 0600).")
    if args.staging:
        print("Remplacez les domaines example.org et renseignez les clés PISTE sandbox / Stripe test avant démarrage.")
    print("Ne versionnez pas ce fichier et ne transmettez jamais son contenu.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
