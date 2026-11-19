#!/usr/bin/env python3
"""Render the Keycloak realm import and browser OIDC config from deployment URLs."""
import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "deploy/keycloak/realm-cfdt.template.json"
IMPORT_DIR = ROOT / "deploy/keycloak/import"
FRONTEND_CONFIG = ROOT / "frontend/auth-config.js"


def origin(value: str, name: str) -> str:
    parsed = urlparse(value)
    local_http = parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}
    if not parsed.hostname or parsed.username or parsed.password or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise SystemExit(f"{name} doit être une URL d'origine sans chemin, query ni fragment.")
    if parsed.scheme != "https" and not local_http:
        raise SystemExit(f"{name} doit utiliser HTTPS (HTTP est autorisé uniquement en local).")
    return value.rstrip("/")


def main() -> None:
    idp = origin(os.getenv("KEYCLOAK_PUBLIC_URL", "http://localhost:8081"), "KEYCLOAK_PUBLIC_URL")
    app = origin(os.getenv("PUBLIC_APP_URL", "http://localhost:8000"), "PUBLIC_APP_URL")
    realm = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    client = next(c for c in realm["clients"] if c["clientId"] == "cfdt-juris-web")
    client["redirectUris"] = [app + "/*"]
    client["webOrigins"] = [app]
    client["attributes"]["post.logout.redirect.uris"] = app + "/*"
    IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    (IMPORT_DIR / "realm-cfdt.json").write_text(json.dumps(realm, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    config = {
        "issuer": idp + "/realms/cfdt",
        "client_id": "cfdt-juris-web",
        "redirect_uri": app + "/",
        "scopes": "openid profile email"
    }
    FRONTEND_CONFIG.write_text("// Généré par scripts/render_keycloak_config.py — ne pas ajouter de secret ici.\n"
        "window.DIKEVIA_OIDC = " + json.dumps(config, ensure_ascii=False, indent=2) + ";\n", encoding="utf-8")
    print(f"Configuration générée : issuer={config['issuer']} ; application={app}")
    print("Aucun secret client n'est nécessaire pour cette application navigateur publique.")


if __name__ == "__main__":
    main()
