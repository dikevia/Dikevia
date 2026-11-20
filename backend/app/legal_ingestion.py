"""Import contrôlé des métadonnées CIRCULAIRES DILA depuis un XML Open Data."""
from __future__ import annotations

import re
from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException
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
        root = ET.fromstring(xml_bytes)  # nosec B314: ET is defusedxml.ElementTree.
    except (ET.ParseError, DefusedXmlException) as exc:
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


def parse_administrative_open_data_zip(zip_bytes: bytes, archive_name: str) -> list[dict[str, Any]]:
    """Import only dated, full-text decisions whose content is relevant to FPT.

    The official portal publishes monthly ZIP archives, not an API. XML files are
    parsed in-place (never extracted), with strict archive and XML resource limits.
    """
    import hashlib
    import zipfile

    from .fpt_scope import classify_public_service_scope

    if not zip_bytes or len(zip_bytes) > 100 * 1024 * 1024:
        raise ValueError("L'archive Open Data est vide ou dépasse 100 Mo.")
    try:
        archive = zipfile.ZipFile(__import__("io").BytesIO(zip_bytes))
    except (zipfile.BadZipFile, OSError) as exc:
        raise ValueError("L'archive Open Data n'est pas un ZIP valide.") from exc

    with archive:
        xml_entries = [info for info in archive.infolist() if not info.is_dir() and info.filename.lower().endswith(".xml")]
        if not xml_entries or len(xml_entries) > 5000:
            raise ValueError("L'archive doit contenir entre 1 et 5 000 fichiers XML.")
        total_size = sum(info.file_size for info in xml_entries)
        if total_size > 500 * 1024 * 1024:
            raise ValueError("Le volume XML décompressé dépasse 500 Mo.")
        records: list[dict[str, Any]] = []
        for info in xml_entries:
            if info.flag_bits & 0x1 or info.file_size <= 0 or info.file_size > 15 * 1024 * 1024:
                continue
            if info.compress_size and info.file_size / info.compress_size > 200:
                continue
            try:
                xml_bytes = archive.read(info)
                if b"<!DOCTYPE" in xml_bytes.upper() or b"<!ENTITY" in xml_bytes.upper():
                    continue
                root = ET.fromstring(xml_bytes)
            except (KeyError, OSError, EOFError, RuntimeError, NotImplementedError, zipfile.BadZipFile, ET.ParseError, DefusedXmlException):
                continue

            def value(*names: str, max_length: int = 1000) -> str | None:
                found = _descendant_text(root, {name.upper() for name in names})
                return found[:max_length] if found else None

            court_code = value("Code_Juridiction", "CodeJuridiction", max_length=80)
            court_name = value("Nom_Juridiction", "NomJuridiction", max_length=250)
            case_number = value("Numero_Dossier", "NumeroDossier", max_length=120)
            decision_date_raw = value("Date_Lecture", "DateLecture", max_length=40)
            decision_date = _date(decision_date_raw)
            if not case_number or not decision_date or not court_name:
                continue

            body_node = next((node for node in root.iter() if _local(node.tag) == "TEXTE_INTEGRAL"), None)
            if body_node is None:
                continue
            paragraphs = [
                clean_text(" ".join(part.strip() for part in node.itertext() if part.strip()))
                for node in body_node.iter() if _local(node.tag) in {"P", "PARAGRAPHE"}
            ]
            body_source = "\n".join(paragraph for paragraph in paragraphs if paragraph) or " ".join(
                part.strip() for part in body_node.itertext() if part.strip()
            )
            body = clean_text(body_source)[:100000]
            if len(body) < 80:
                continue

            title = f"Décision du {court_name} n° {case_number} du {decision_date.isoformat()}"
            scope = classify_public_service_scope({"title": title, "text": body, "document_kind": "ADMIN_CASELAW"})
            if not scope.get("analysis_eligible"):
                continue

            ecli = value("Numero_ECLI", "NumeroECLI", max_length=160)
            identification = value("Identification", max_length=250) or info.filename
            publication_code = value("Code_Publication", "CodePublication", max_length=20)
            decision_type = value("Type_Decision", "TypeDecision", max_length=80)
            recourse_type = value("Type_Recours", "TypeRecours", max_length=160)
            hearing_date = _date(value("Date_Audience", "DateAudience", max_length=40))
            formation = value("Formation_Jugement", "FormationJugement", max_length=200)
            role_number = value("Numero_Role", "NumeroRole", max_length=100)
            update_date = _date(value("Date_Mise_Jour", "DateMiseAJour", max_length=40))
            identity = "|".join((court_code or court_name, case_number, decision_date.isoformat(), identification))
            source_digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32]
            body_digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
            if len(records) >= 1000:
                raise ValueError("L'archive contient plus de 1 000 décisions FPT pertinentes ; découpez l'import en archives mensuelles plus petites.")
            records.append({
                "source_type": "OTHER_OFFICIAL",
                "source_id": "OPEN_DATA_JA_" + source_digest,
                "title": title,
                "document_kind": "ADMIN_CASELAW",
                "official_number": case_number,
                "jurisdiction": court_name,
                "publisher": "Conseil d'État — Open Data de la justice administrative",
                "official_url": "https://opendata.justice-administrative.fr/",
                "signature_date": decision_date,
                "publication_date": update_date,
                "status": "UNKNOWN",
                "source_status": "OFFICIAL_XML_IMPORTED",
                "valid_from": None,
                "valid_to": None,
                "version_status": "UNKNOWN",
                "version_key": "open-data-xml-" + body_digest[:32],
                "source_version_id": ecli or identification,
                "full_text": body,
                "raw_metadata": {
                    "court_code": court_code, "ecli": ecli,
                    "publication_code": publication_code,
                    "decision_type": decision_type, "recourse_type": recourse_type,
                    "hearing_date": hearing_date.isoformat() if hearing_date else None,
                    "formation": formation, "role_number": role_number,
                    "xml_identification": identification,
                    "source_archive": archive_name[:250],
                    "public_service_scope": scope.get("scope"),
                    "scope_evidence": scope.get("evidence", []),
                    "source_license": "Licence Ouverte version 2.0",
                    "import_method": "JUSTICE_ADMINISTRATIVE_OPEN_DATA_XML",
                },
                "raw_version_payload": {
                    "xml_filename": info.filename[:250],
                    "source_archive": archive_name[:250],
                    "ecli": ecli,
                },
            })
        return records
