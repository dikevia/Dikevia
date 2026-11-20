#!/usr/bin/env python3
"""Build a clean, reproducible developer ZIP without local secrets or caches."""
from __future__ import annotations

import argparse
import hashlib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {
    ".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".tox", "node_modules", "dist", "build", "coverage",
    ".idea", ".DS_Store",
}
ALLOWED_ENV_EXAMPLES = {".env.example", ".env.staging.example"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".pem", ".p12", ".pfx", ".zip", ".sqlite", ".db", ".log"}
EXCLUDED_NAMES = {".env", ".env.runtime", ".env.staging.runtime", ".DS_Store", "id_rsa", "id_ed25519"}


def include_file(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    if any(part in EXCLUDED_DIRS for part in relative.parts):
        return False
    name = path.name
    if name in EXCLUDED_NAMES or name.endswith(".key") or path.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    if name.startswith(".env.") and name not in ALLOWED_ENV_EXAMPLES:
        return False
    if path.is_symlink() or not path.is_file():
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="dist/CFDT_JURIS_V3_38_Kit_Developpeur.zip")
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    files = sorted(
        (p for p in ROOT.rglob("*") if include_file(p) and p.resolve() != output),
        key=lambda p: p.relative_to(ROOT).as_posix(),
    )
    if not files:
        raise SystemExit("Aucun fichier source trouvé : archive annulée.")

    manifest_lines = []
    for path in files:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest_lines.append(f"{digest}  {path.relative_to(ROOT).as_posix()}")

    root_name = "CFDT_JURIS_V3_38_Kit_Developpeur"
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            archive.write(path, f"{root_name}/{path.relative_to(ROOT).as_posix()}")
        archive.writestr(
            f"{root_name}/SHA256SUMS_KIT.txt",
            "\n".join(manifest_lines) + "\n",
        )

    print(f"Archive créée : {output}")
    print(f"Fichiers inclus : {len(files)}")
    print(f"Taille : {output.stat().st_size} octets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
