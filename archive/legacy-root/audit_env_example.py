#!/usr/bin/env python3
"""Check that every Pydantic Settings field is documented in deploy/.env.example."""
from __future__ import annotations
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "backend" / "app" / "config.py"
ENV_EXAMPLE = ROOT / "deploy" / ".env.example"


def settings_fields() -> set[str]:
    tree = ast.parse(CONFIG.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "Settings":
            return {
                item.target.id.upper()
                for item in node.body
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)
            }
    raise RuntimeError("Classe Settings introuvable dans backend/app/config.py")


def documented_env_keys() -> set[str]:
    # Commented assignments count as documented optional variables.
    pattern = re.compile(r"^\s*#?\s*([A-Z][A-Z0-9_]*)\s*=", re.MULTILINE)
    return set(pattern.findall(ENV_EXAMPLE.read_text(encoding="utf-8")))


def missing_keys() -> set[str]:
    return settings_fields() - documented_env_keys()


def main() -> int:
    missing = sorted(missing_keys())
    if missing:
        print("Variables Settings absentes de deploy/.env.example :", file=sys.stderr)
        for key in missing:
            print(f"  - {key}", file=sys.stderr)
        return 1
    print(f"OK : {len(settings_fields())} variables Settings documentées dans deploy/.env.example.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
