"""Import contrôlé des métadonnées CIRCULAIRES DILA depuis un XML Open Data."""
from __future__ import annotations

import re
from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException
from datetime import date
from typing import Any
from urllib.parse import urlparse

from .legal_corpus import clean_text



_ADMIN_OPEN_DATA_ARCHIVES = {
    "CE": ("DCE", date(2021, 6, 1)),
    "CAA": ("DCA", date(2022, 3, 1)),
    "TA": ("DTA", date(2022, 6, 1)),
}


def administrative_open_data_archive_url(
    court: str, year: int, month: int, *, today: date | None = None,
) -> str:
    """Build a monthly archive URL on the official, fixed justice-administrative host."""
    normalized_court = str(court or "").strip().upper()
    archive = _ADMIN_OPEN_DATA_ARCHIVES.get(normalized_court)
    if archive is None:
        raise ValueError("La juridiction doit être CE, CAA ou TA.")
    if isinstance(year, bool) or not isinstance(year, int):
        raise ValueError("L'année de l'archive est invalide.")
    if isinstance(month, bool) or not isinstance(month, int) or not 1 <= month <= 12:
        raise ValueError("Le mois de l'archive est invalide.")
    try:
        requested_month = date(year, month, 1)
    except ValueError as exc:
        raise ValueError("L'année de l'archive est invalide.") from exc
    current = today or date.today()
    current_month = date(current.year, current.month, 1)
    folder, first_available = archive
    if requested_month < first_available or requested_month > current_month:
        raise ValueError("Aucune archive mensuelle n'est attendue pour cette période.")
    return (
        "https://opendata.justice-administrative.fr/"
        f"{folder}/{year}/{month:02d}/{normalized_court}_{year}{month:02d}.zip"
    )




def filter_administrative_open_data_items(
    items: list[dict[str, Any]], *, versant: str = "FPT",
) -> list[dict[str, Any]]:
    """Keep only decisions explicitly scoped to the requested versant or common rules."""
    target = str(versant or "").strip().upper()
    if target not in {"FPT", "FPE", "FPH"}:
        raise ValueError("Le versant doit être FPT, FPE ou FPH.")
    allowed = {target, "COMMON_PUBLIC_SERVICE"}
    selected = []
    for item in items:
        if not isinstance(item, dict):
            continue
        metadata = item.get("raw_metadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        if str(metadata.get("public_service_scope") or "").strip().upper() in allowed:
            selected.append(item)
    return selected


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


def _is_fpt_employment_case_law(title: str, body: str, scope: dict[str, Any]) -> bool:
    """Require a direct territorial-employment link, not incidental local references.

    A municipality mentioned somewhere in a decision about a State or hospital
    employee is not sufficient to classify that decision as FPT. Accept either
    explicit territorial-employment terminology or a local authority's own HR
    decision in the opening procedural section.
    """
    import unicodedata

    raw = f"{title} {body}"
    corpus = unicodedata.normalize("NFKD", raw.casefold())
    corpus = "".join(char for char in corpus if not unicodedata.combining(char))
    corpus = re.sub(r"[^a-z0-9]+", " ", corpus)
    corpus = re.sub(r"\\s+", " ", corpus).strip()
    opening = unicodedata.normalize("NFKD", str(body or "")[:6000].casefold())
    opening = "".join(char for char in opening if not unicodedata.combining(char))
    opening = re.sub(r"[^a-z0-9]+", " ", opening)
    opening = re.sub(r"\\s+", " ", opening).strip()

    if scope.get("scope") in {"FPE", "FPH", "OUT_OF_SCOPE_EUROPEAN_LAW"}:
        return False

    explicit_fpt_employment = (
        "fonction publique territoriale", "fonctionnaire territorial",
        "fonctionnaires territoriaux", "agent territorial", "agents territoriaux",
        "agent contractuel territorial", "agents contractuels territoriaux",
        "personnel communal", "personnels communaux", "agent communal",
        "agents communaux", "agent de la commune", "agent de la mairie",
        "personnel territorial", "personnels territoriaux",
        "decret 88 145", "decret n 88 145", "decret 87 602",
        "decret n 87 602", "decret 89 677", "decret n 89 677",
        "decret 91 298", "decret n 91 298",
    )
    has_explicit_fpt = any(marker in corpus for marker in explicit_fpt_employment)

    local_authority_hr_decisions = (
        "decision du maire", "arrete du maire", "par lequel le maire",
        "par laquelle le maire", "decision de la commune", "arrete de la commune",
        "par lequel la commune", "par laquelle la commune",
        "decision du president du conseil departemental",
        "decision de la presidente du conseil departemental",
        "decision du president du conseil regional",
        "decision de la presidente du conseil regional",
        "decision du president du centre de gestion",
        "decision de la presidente du centre de gestion",
    )
    hr_subjects = (
        "affectation", "agent", "fonctionnaire", "personnel", "disciplinaire",
        "remuneration", "conge", "harcelement", "maladie", "temps de travail",
        "licenciement", "recrutement", "protection fonctionnelle",
    )
    has_local_hr_decision = (
        any(marker in opening for marker in local_authority_hr_decisions)
        and any(marker in opening for marker in hr_subjects)
    )
    direct_local_hr_relationship = (
        any(marker in opening for marker in (
            "service des ressources humaines de la commune",
            "service des ressources humaines de la mairie",
            "service rh de la commune",
            "service rh de la mairie",
            "aupres du service des ressources humaines de la commune",
            "aupres du service des ressources humaines de la mairie",
        ))
        and any(marker in opening for marker in (
            "protection fonctionnelle", "harcelement", "sanction disciplinaire",
            "affectation", "remuneration", "conge de maladie",
        ))
    )

    # Explicit FPT language is strong evidence, except when the opening
    # identifies a different public employer and no local HR decision is at issue.
    state_or_hospital_employer = any(marker in opening for marker in (
        "ministre des armees", "ministere des armees", "ministere de l interieur",
        "ministre de l interieur", "recteur de l academie", "rectrice de l academie",
        "rectorat", "ministre", "ministere", "centre hospitalier",
        "etablissement public de sante", "commandant de la legion etrangere",
    ))
    if has_explicit_fpt and (not state_or_hospital_employer or has_local_hr_decision):
        return True
    if has_local_hr_decision or direct_local_hr_relationship:
        return True
    return False


def _public_service_employment_case_law_scope(title: str, body: str) -> dict[str, Any] | None:
    """Identify a decision tied to HR law in exactly one public-service branch.

    FPT keeps its stricter local-employer relevance rule. FPE and FPH require
    explicit branch evidence plus both an employment subject and an HR topic.
    Explicitly common rules may be retained only when the text says they cover
    the three public-service branches.
    """
    import unicodedata

    from .fpt_scope import classify_public_service_scope

    corpus = unicodedata.normalize("NFKD", f"{title} {body}".casefold())
    corpus = "".join(char for char in corpus if not unicodedata.combining(char))
    corpus = re.sub(r"[^a-z0-9]+", " ", corpus)
    corpus = re.sub(r"\s+", " ", corpus).strip()
    public_employment = (
        "agent public", "agents publics", "fonctionnaire", "fonctionnaires",
        "agent de l etat", "agents de l etat", "agent contractuel de l etat",
        "agent hospitalier", "agents hospitaliers", "personnel hospitalier",
        "personnels hospitaliers", "agent contractuel hospitalier",
        "agent territorial", "agents territoriaux", "fonctionnaire territorial",
        "fonctionnaires territoriaux", "agent contractuel territorial",
        "agents des trois versants", "agents des trois fonctions publiques",
    )
    hr_subjects = (
        "protection fonctionnelle", "harcelement moral", "harcelement sexuel",
        "agissement sexiste", "agissements sexistes", "sanction disciplinaire",
        "conseil de discipline", "temps de travail", "duree du travail",
        "conge de maladie", "conge maladie", "accident de service",
        "maladie professionnelle", "droit syndical", "droits syndicaux",
        "decharge d activite de service", "autorisation speciale d absence",
        "traitement indiciaire", "regime indemnitaire", "remuneration",
        "detachement", "disponibilite", "retraite d office",
        "carriere d un agent", "service des ressources humaines",
        "direction des ressources humaines",
    )
    has_public_employment = any(marker in corpus for marker in public_employment)
    has_hr_subject = any(marker in corpus for marker in hr_subjects)

    source = {"title": title, "text": body, "document_kind": "ADMIN_CASELAW"}
    fpt_scope = classify_public_service_scope(source, target_versant="FPT")
    # A local employer and an HR subject can establish a territorial link only
    # when the same decision does not contain competing branch-specific markers.
    # Otherwise the local-employer fallback below would incorrectly override an
    # unresolved FPT/FPE or FPT/FPH conflict during corpus ingestion.
    if fpt_scope.get("scope") in {
        "MIXED_OR_CONFLICTING_PUBLIC_SERVICE_SCOPE",
        "OUT_OF_SCOPE_EUROPEAN_LAW",
    }:
        return None
    if fpt_scope.get("scope") == "OUT_OF_SCOPE_OR_UNCONFIRMED":
        scope_evidence = [str(item).casefold() for item in fpt_scope.get("evidence", [])]
        fpt_markers = ("fonction publique territoriale", "agent territorial", "agents territoriaux",
                       "fonctionnaire territorial", "fonctionnaires territoriaux")
        other_branch_markers = (
            "fonction publique de l etat", "fonctionnaire de l etat",
            "fonctionnaires de l etat", "agent de l etat", "agents de l etat",
            "agent contractuel de l etat", "agents contractuels de l etat",
            "administration centrale", "administrations centrales",
            "service deconcentre de l etat", "services deconcentres de l etat",
            "fonction publique hospitaliere", "etablissement public de sante",
            "etablissements publics de sante", "centre hospitalier",
            "centres hospitaliers", "agent hospitalier", "agents hospitaliers",
            "agent contractuel hospitalier", "agents contractuels hospitaliers",
        )
        has_fpt_evidence = any(any(marker in item for marker in fpt_markers) for item in scope_evidence)
        has_other_branch_evidence = any(
            any(marker in item for marker in other_branch_markers) for item in scope_evidence
        )
        if has_fpt_evidence and has_other_branch_evidence:
            return None
    if _is_fpt_employment_case_law(title, body, fpt_scope):
        if fpt_scope.get("scope") == "OUT_OF_SCOPE_OR_UNCONFIRMED":
            return {
                "scope": "FPT",
                "evidence": ["Décision locale portant sur un sujet de gestion des agents publics"],
                "analysis_eligible": True,
                "claim_eligible": True,
            }
        return fpt_scope

    if not (has_public_employment and has_hr_subject):
        return None

    for branch in ("FPE", "FPH"):
        scope = classify_public_service_scope(source, target_versant=branch)
        if scope.get("analysis_eligible") is True and scope.get("scope") in {
            branch, "COMMON_PUBLIC_SERVICE",
        }:
            return scope
    return None

def parse_administrative_open_data_zip(zip_bytes: bytes, archive_name: str) -> list[dict[str, Any]]:
    """Import dated, full-text administrative decisions relevant to public-service HR law.

    Branch-specific decisions require explicit FPT, FPE or FPH scope evidence;
    explicitly common rules may be retained when their three-branch scope is stated.
    The official portal publishes monthly ZIP archives, not an API. XML files are
    parsed in-place (never extracted), with strict archive and XML resource limits.
    """
    import hashlib
    import zipfile

    if not zip_bytes or len(zip_bytes) > 100 * 1024 * 1024:
        raise ValueError("L'archive Open Data est vide ou dépasse 100 Mo.")
    try:
        archive = zipfile.ZipFile(__import__("io").BytesIO(zip_bytes))
    except (zipfile.BadZipFile, OSError) as exc:
        raise ValueError("L'archive Open Data n'est pas un ZIP valide.") from exc

    with archive:
        xml_entries = [
            info for info in archive.infolist()
            if not info.is_dir() and re.search(r"\.xml(?:_[a-z0-9]+)?$", info.filename.lower())
        ]
        if not xml_entries:
            preview = [info.filename for info in archive.infolist()[:12]]
            raise ValueError(
                f"Archive {archive_name}: aucun fichier XML reconnu parmi "
                f"{len(archive.infolist())} entrées ZIP ; exemples : {preview!r}."
            )
        if len(xml_entries) > 25000:
            raise ValueError(
                f"Archive {archive_name}: {len(xml_entries)} fichiers XML, limite de 25 000 dépassée."
            )
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
            source_court_label = value("Nom_Juridiction", "NomJuridiction", max_length=250)
            court_name = source_court_label
            court_seat = None
            decision_section = None
            if (court_code or "").upper() == "CE":
                # In some Conseil d'État XML archives, Nom_Juridiction contains
                # "Section du Contentieux" rather than the institution's name.
                court_name = "Conseil d'État"
                court_seat = "Paris"
                if source_court_label and source_court_label.casefold().replace("’", "'") not in {
                    "conseil d'etat", "conseil d'état"
                }:
                    decision_section = source_court_label
            elif source_court_label:
                seat_match = re.search(
                    r"^(?:tribunal administratif|cour administrative d'appel) de (.+)$",
                    source_court_label, re.IGNORECASE,
                )
                if seat_match:
                    court_seat = seat_match.group(1).strip()
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
            body = clean_text(body_source)
            if not 80 <= len(body) <= 100000:
                continue

            title = f"Décision du {court_name} n° {case_number} du {decision_date.isoformat()}"
            scope = _public_service_employment_case_law_scope(title, body)
            if scope is None:
                continue

            ecli = value("Numero_ECLI", "NumeroECLI", max_length=160)
            identification = value("Identification", max_length=250) or info.filename
            publication_code = value("Code_Publication", "CodePublication", max_length=20)
            decision_type = value("Type_Decision", "TypeDecision", max_length=80)
            solution = value("Solution", max_length=250)
            recourse_type = value("Type_Recours", "TypeRecours", max_length=160)
            hearing_date = _date(value("Date_Audience", "DateAudience", max_length=40))
            formation = value("Formation_Jugement", "FormationJugement", max_length=200)
            citation_court = f"{court_name} (siège à {court_seat})" if court_seat else court_name
            if decision_section:
                citation_court += f" — {decision_section}"
            if formation:
                citation_court += f" — {formation}"
            title = f"Décision du {citation_court} n° {case_number} du {decision_date.isoformat()}"
            role_number = value("Numero_Role", "NumeroRole", max_length=100)
            update_date = _date(value("Date_Mise_Jour", "DateMiseAJour", max_length=40))
            identity = "|".join((court_code or court_name, case_number, decision_date.isoformat(), identification))
            source_digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32]
            body_digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
            if len(records) >= 1000:
                raise ValueError("L'archive contient plus de 1 000 décisions pertinentes ; découpez l'import en archives mensuelles plus petites.")
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
                    "court_name": court_name, "court_seat": court_seat,
                    "decision_section": decision_section,
                    "publication_code": publication_code,
                    "decision_type": decision_type, "solution": solution,
                    "recourse_type": recourse_type,
                    "hearing_date": hearing_date.isoformat() if hearing_date else None,
                    "formation": formation, "role_number": role_number,
                    "xml_identification": identification,
                    "source_archive": archive_name[:250],
                    "public_service_scope": scope.get("scope"),
                    "scope_evidence": scope.get("evidence", []),
                    "source_license": "Licence Ouverte version 2.0",
                    "source_xml_sha256": hashlib.sha256(xml_bytes).hexdigest(),
                    "import_method": "JUSTICE_ADMINISTRATIVE_OPEN_DATA_XML",
                },
                "raw_version_payload": {
                    "xml_filename": info.filename[:250],
                    "source_archive": archive_name[:250],
                    "source_xml_sha256": hashlib.sha256(xml_bytes).hexdigest(),
                    "ecli": ecli,
                },
            })
        return records
