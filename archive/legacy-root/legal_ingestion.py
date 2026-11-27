"""Import contrôlé des métadonnées CIRCULAIRES DILA depuis un XML Open Data."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import date
from typing import Any
from urllib.parse import urlparse

from .legal_corpus import clean_text


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].split(":")[-1].upper()


def _descendant_text(element: ET.Element, names: set[str]) -> str | None:
    for child in element.iter():
        if _local(child.tag) in names:
            value = " ".join(part.strip() for part in child.itertext() if part.strip())
            if value:
                return value[:10000]
    return None


def _date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None


def parse_circulaires_xml(xml_bytes: bytes) -> list[dict[str, Any]]:
    if not xml_bytes or len(xml_bytes) > 50 * 1024 * 1024:
        raise ValueError("Le fichier XML est vide ou dépasse 50 Mo.")
    # Reject DTD/entity declarations: the importer handles only the supplied XML tree.
    payload_upper = xml_bytes.upper()
    if b"<!DOCTYPE" in payload_upper or b"<!ENTITY" in payload_upper:
        raise ValueError("Les déclarations DTD/ENTITY ne sont pas acceptées.")
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ValueError("Le fichier XML CIRCULAIRES est invalide.") from exc

    records = []
    candidates = [node for node in root.iter() if _local(node.tag) in {
        "CIRCULAIRE", "INSTRUCTION", "CIRCULAIRE_INSTRUCTION", "DOCUMENT"}]
    if not candidates:
        candidates = [node for node in root.iter() if _descendant_text(node, {"ID", "IDENTIFIANT", "ID_CIRCULAIRE"})]
    seen = set()
    for node in candidates:
        identifier = node.attrib.get("id") or node.attrib.get("ID") or _descendant_text(
            node, {"ID", "IDENTIFIANT", "ID_CIRCULAIRE", "ID_CIRC"})
        title = _descendant_text(node, {"TITRE", "OBJET", "INTITULE", "TITLE"})
        if not identifier or not title:
            continue
        identifier = identifier.strip()
        if identifier in seen:
            continue
        seen.add(identifier)
        url = node.attrib.get("url") or _descendant_text(node, {"URL", "LIEN", "URL_LEGIFRANCE"})
        if url and not (urlparse(url).scheme == "https" and urlparse(url).hostname in {
            "www.legifrance.gouv.fr", "legifrance.gouv.fr"}):
            url = None
        number = _descendant_text(node, {"NOR", "NUMERO", "NUMERO_CIRCULAIRE"})
        signed = _date(_descendant_text(node, {"DATE_SIGNATURE", "DATESIGNATURE", "DATE"}))
        published = _date(_descendant_text(node, {"DATE_PUBLICATION", "DATEPUBLICATION", "DATE_PUBLI"}))
        body = _descendant_text(node, {"TEXTE", "CONTENU", "TEXTE_INTEGRAL", "CONTENU_HTML"})
        text = clean_text(body or "")
        records.append({"source_type": "DILA_CIRCULAIRES", "source_id": identifier,
            "title": title, "document_kind": "CIRCULAR", "official_number": number,
            "publisher": _descendant_text(node, {"MINISTERE", "EMETTEUR", "AUTEUR"}),
            "official_url": url, "signature_date": signed, "publication_date": published,
            "status": "UNKNOWN", "source_status": "IMPORTED_UNVERIFIED",
            "valid_from": None, "valid_to": None, "version_status": "UNKNOWN",
            "version_key": "dila-xml-" + (published.isoformat() if published else "undated"),
            "full_text": text, "raw_metadata": {"xml_element": _local(node.tag),
                "identifier": identifier, "import_method": "DILA_CIRCULAIRES_XML"}})
    return records
