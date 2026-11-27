#!/usr/bin/env python3
"""Render a least-privilege API env file from the protected deployment env file."""
from __future__ import annotations
import argparse
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def settings_keys() -> set[str]:
    tree = ast.parse((ROOT / "backend/app/config.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "Settings":
            return {item.target.id.upper() for item in node.body
                    if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)}
    raise RuntimeError("Classe Settings introuvable")


def parse_assignments(path: Path) -> dict[str, str]:
    values = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if value[:1] in {"'", '"'} and value[-1:] == value[:1]:
            value = value[1:-1]
        if re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
            values[key] = value
    return values


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    output = args.output.resolve()
    if not source.is_file():
        raise SystemExit(f"Fichier source absent : {source}")
    values = parse_assignments(source)
    placeholders = sorted(key for key, value in values.items() if "CHANGE_ME_" in value)
    if placeholders:
        raise SystemExit("Valeurs secrètes modèle non remplacées : " + ", ".join(placeholders) + ". Exécuter scripts/upgrade_env_file.py.")
    allowed = settings_keys()
    lines = [f"{key}={values[key]}" for key in sorted(allowed) if key in values]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    output.chmod(0o600)
    print(f"Fichier runtime généré : {output.name} ({len(lines)} variables applicatives).")
    print("Les mots de passe DBA, Keycloak DB, Grafana et supervision ne sont pas transmis au conteneur API.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
