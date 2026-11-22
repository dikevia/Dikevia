#!/usr/bin/env python3
"""Importe les fiches Service-Public Particuliers relatives à la fonction publique.

Source : data.gouv.fr / DILA, flux XML 3.5.
Le résultat est un référentiel lexical et documentaire exploratoire, jamais une
validation juridique des références extraites.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from defusedxml import ElementTree as ET

DATASET_API_URL = (
    "https://www.data.gouv.fr/api/1/datasets/"
    "fiches-pratiques-et-ressources-de-service-public-gouv-fr-particuliers/"
)
THEME_FONCTION_PUBLIQUE = "N19806"
PUBLIC_TITLE_TERMS = (
    "fonction publique", "fonctionnaire", "agent public", "agents publics",
    "agent territorial", "agents territoriaux", "collectivité territoriale",
    "collectivités territoriales", "agent contractuel de droit public",
    "contractuel de droit public", "fonctionnaire territorial",
    "fonctionnaire hospitalier", "fonctionnaire de l'état",
    "fonction publique hospitalière", "fonction publique territoriale",
    "fonction publique de l'état", "ouvrier de l'état",
)
PUBLIC_REFERENCE_TERMS = (
    "code général de la fonction publique", "cgfp",
    "décret n° 85-1250", "décret n° 86-83", "décret n° 87-602",
    "décret n° 88-386", "décret n° 88-145", "décret n° 91-155",
    "décret n° 2002-60", "décret n° 2002-634", "décret n° 2004-878",
    "décret n° 2020-592", "décret n° 2025-564", "décret n° 2026-705",
)
MAX_ARCHIVE_BYTES = 100 * 1024 * 1024
MAX_XML_BYTES = 8 * 1024 * 1024


def local_name(tag: str) -> str:
    """Return an XML local name, regardless of namespace or prefix."""
    return tag.rsplit("}", 1)[-1].split(":")[-1]


def _resource_score(resource: dict[str, Any]) -> int:
    title = str(resource.get("title") or "").casefold()
    description = str(resource.get("description") or "").casefold()
    url = str(resource.get("url") or "").casefold()
    fmt = str(resource.get("format") or "").casefold()
    score = 0
    if fmt == "xml":
        score += 5
    if url.endswith(".zip"):
        score += 5
    if "particulier" in title or "particulier" in description:
        score += 4
    if "vosdroits" in url or "latest" in url:
        score += 3
    if "schema" in title or "schema" in url:
        score -= 10
    return score


def resolve_archive_resource(metadata: dict[str, Any]) -> dict[str, Any]:
    resources = metadata.get("resources")
    if not isinstance(resources, list):
        raise RuntimeError("Métadonnées data.gouv.fr invalides : resources absent.")
    candidates = [
        r for r in resources
        if isinstance(r, dict) and str(r.get("url") or "").startswith("https://")
        and _resource_score(r) >= 12
    ]
    if not candidates:
        raise RuntimeError("Archive ZIP XML des fiches particuliers introuvable.")
    # Prefer the resource explicitly marked as the current/latest archive.
    return max(candidates, key=_resource_score)


def telecharger_archive_sp(client: httpx.Client | None = None) -> tuple[zipfile.ZipFile, dict[str, Any]]:
    own_client = client is None
    client = client or httpx.Client(
        timeout=httpx.Timeout(90.0, connect=15.0),
        follow_redirects=True,
        headers={"User-Agent": "Dikevia-OpenDataImporter/1.0"},
    )
    try:
        metadata_response = client.get(DATASET_API_URL, timeout=30.0)
        metadata_response.raise_for_status()
        metadata = metadata_response.json()
        resource = resolve_archive_resource(metadata)
        archive_response = client.get(resource["url"], timeout=90.0)
        archive_response.raise_for_status()
        content = archive_response.content
        if len(content) > MAX_ARCHIVE_BYTES:
            raise RuntimeError("Archive supérieure à la limite de sécurité (100 Mo).")
        if not zipfile.is_zipfile(io.BytesIO(content)):
            raise RuntimeError("La ressource annoncée n'est pas une archive ZIP valide.")
        zf = zipfile.ZipFile(io.BytesIO(content))
        return zf, {
            "dataset_api_url": DATASET_API_URL,
            "dataset_id": metadata.get("id"),
            "dataset_title": metadata.get("title"),
            "dataset_last_update": metadata.get("last_update"),
            "resource_id": resource.get("id"),
            "resource_title": resource.get("title"),
            "download_url": resource["url"],
            "filename": Path(urlparse(resource["url"]).path).name,
            "file_date": (resource.get("last_modified") or resource.get("extras", {}).get("analysis:last-modified-at") or "")[:10] or None,
            "resource_last_modified": resource.get("last_modified") or resource.get("extras", {}).get("analysis:last-modified-at"),
            "resource_checksum": resource.get("checksum") or resource.get("extras", {}).get("analysis:checksum"),
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
            "license": metadata.get("license"),
            "attribution": "Service-Public.gouv.fr / DILA",
        }
    finally:
        if own_client:
            client.close()


def _elements(root: ET.Element, name: str) -> list[ET.Element]:
    return [node for node in root.iter() if local_name(node.tag) == name]


def _text(node: ET.Element) -> str:
    return " ".join(" ".join(node.itertext()).split())


def _theme_ids(root: ET.Element) -> set[str]:
    ids: set[str] = set()
    for node in root.iter():
        if local_name(node.tag) in {"Theme", "Niveau"}:
            value = node.attrib.get("ID") or node.attrib.get("id")
            if value:
                ids.add(value.strip())
    return ids


def _extract_references(root: ET.Element) -> list[dict[str, str]]:
    references: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for node in _elements(root, "Reference"):
        ref_id = node.attrib.get("ID") or node.attrib.get("id") or ""
        ref_type = node.attrib.get("type") or node.attrib.get("Type") or ""
        label = _text(node)
        if not (ref_id or label):
            continue
        item = (ref_id.strip(), ref_type.strip(), label)
        if item not in seen:
            seen.add(item)
            references.append({
                "id_legifrance": item[0],
                "type": item[1],
                "libelle": item[2],
            })
    return references


def _extract_blocs_cas(root: ET.Element) -> list[dict[str, str]]:
    blocs: list[dict[str, str]] = []
    for node in _elements(root, "BlocCas"):
        blocs.append({
            "type": node.attrib.get("type", ""),
            "id": node.attrib.get("ID") or node.attrib.get("id", ""),
            "titre": next(
                (_text(child) for child in node.iter()
                 if local_name(child.tag).casefold() in {"title", "titre"} and _text(child)),
                "",
            ),
            "contenu": _text(node),
        })
    return blocs


def _extract_title(root: ET.Element) -> str:
    # Prefer the Dublin Core title when present; otherwise use the first title.
    titles = [node for node in root.iter() if local_name(node.tag).casefold() in {"title", "titre"}]
    for node in titles:
        namespace = node.tag[1:].split("}", 1)[0] if node.tag.startswith("{") else ""
        if namespace.casefold() in {"dc", "http://purl.org/dc/elements/1.1/"} and _text(node):
            return _text(node)
    return next((_text(node) for node in titles if _text(node)), "")


def _is_public_function_fiche(root: ET.Element) -> bool:
    """Require a public-service title or an explicit public-service legal reference."""
    title = _extract_title(root).casefold()
    references = " ".join(item.get("libelle", "") for item in _extract_references(root)).casefold()
    return (
        any(term in title for term in PUBLIC_TITLE_TERMS)
        or any(term in references for term in PUBLIC_REFERENCE_TERMS)
    )


def extraire_fiches_fonctionnaires(zf: zipfile.ZipFile) -> list[dict[str, Any]]:
    fiches: list[dict[str, Any]] = []
    for info in zf.infolist():
        filename = info.filename
        if not re.search(r"(?:^|/)F\d+\.xml$", filename, flags=re.IGNORECASE):
            continue
        if info.file_size > MAX_XML_BYTES:
            continue
        try:
            root = ET.fromstring(zf.read(info))
        except (ET.ParseError, ValueError):
            continue

        themes = _theme_ids(root)
        if THEME_FONCTION_PUBLIQUE not in themes or not _is_public_function_fiche(root):
            continue

        blocks = _extract_blocs_cas(root)
        versants = sorted({
            token
            for block in blocks
            for token in re.findall(r"\b(?:FPT|FPE|FPH)\b", block["type"] + " " + block["id"] + " " + block["titre"] + " " + block["contenu"], re.I)
        })
        full_text = _text(root)
        fiches.append({
            "fiche_id": Path(filename).stem.upper(),
            "titre_courant": _extract_title(root),
            "theme_ids": sorted(themes),
            "versants_detectes": versants,
            "blocs_cas": blocks,
            "contenu": full_text,
            "references_juridiques": _extract_references(root),
            "statut_validation_juridique": "NON_VERIFIE",
        })
    return sorted(fiches, key=lambda item: item["fiche_id"])


def build_output(fiches: list[dict[str, Any]], provenance: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "source": provenance,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "theme_filtre": THEME_FONCTION_PUBLIQUE,
        "nombre_fiches": len(fiches),
        "avertissement": (
            "Référentiel lexical/documentaire extrait de Service-Public. "
            "Les références juridiques doivent être vérifiées sur les sources officielles "
            "avant toute utilisation comme fondement d'une réponse."
        ),
        "fiches": fiches,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("corpus_national/referentiels/service_public_fonction_publique.json"),
    )
    args = parser.parse_args()
    archive, provenance = telecharger_archive_sp()
    try:
        fiches = extraire_fiches_fonctionnaires(archive)
    finally:
        archive.close()
    if not fiches:
        raise RuntimeError(
            "Aucune fiche trouvée pour N19806 : arrêt sans écraser le référentiel existant."
        )
    output = build_output(fiches, provenance)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(f"{len(fiches)} fiches Fonction publique extraites vers {args.output}")
    print(f"Source : {provenance['download_url']}")
    print(f"Licence : {provenance.get('license')} — attribution : Service-Public.gouv.fr / DILA")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERREUR import Service-Public : {exc}", file=sys.stderr)
        raise SystemExit(1)
