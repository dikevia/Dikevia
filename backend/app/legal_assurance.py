"""Deterministic legal-source classification and cautious comparison helpers.

This module ranks source families for review workflows; it does not decide
legality or resolve conflicts without a complete legal analysis.
"""
from __future__ import annotations

import re
from typing import Any

# This is a review order, not a universal rule for resolving every conflict.
_SOURCE_CLASS = {
    "CONSTITUTIONAL": (100, "Norme constitutionnelle"),
    "EUROPEAN_TREATY": (95, "Droit de l'Union / convention internationale"),
    "LAW": (80, "Loi / ordonnance ratifiée selon son régime"),
    "CODE": (80, "Disposition codifiée (valeur à déterminer selon le texte)"),
    "ORDONNANCE": (78, "Ordonnance (régime à vérifier)"),
    "DECREE": (65, "Décret"),
    "ORDER": (60, "Arrêté"),
    "ADMIN_CASELAW": (55, "Jurisprudence administrative"),
    "CIRCULAR": (30, "Circulaire / instruction"),
    "LOCAL_DELIBERATION": (20, "Délibération locale"),
    "LOCAL_REGULATION": (15, "Règlement / document local"),
    "LOCAL_PROTOCOL": (10, "Protocole / accord local"),
    "OTHER": (0, "Nature juridique à qualifier"),
}


def classify_legal_source(source: dict[str, Any]) -> dict[str, Any]:
    kind = str(source.get("document_kind") or source.get("source_type") or "OTHER").upper()
    if kind == "CGFP_SNAPSHOT":
        kind = "CODE"
    elif kind in {"LEGIFRANCE_CETAT_SEARCH", "LEGIFRANCE_CETAT_FULL_TEXT"}:
        kind = "ADMIN_CASELAW"
    elif kind == "DILA_CIRCULAIRES":
        kind = "CIRCULAR"
    elif kind == "LEGIFRANCE_API":
        kind = "CODE"
    elif kind.startswith("LEGIFRANCE_"):
        kind = str(source.get("document_kind") or "OTHER").upper()
    if kind in {"LOCAL_DOCUMENT", "LOCAL_COLLECTIVITY_DOCUMENT"}:
        doc_type = str(source.get("local_document_type") or "").upper()
        if "DELIB" in doc_type:
            kind = "LOCAL_DELIBERATION"
        elif "PROTOCOLE" in doc_type or "ACCORD" in doc_type:
            kind = "LOCAL_PROTOCOL"
        else:
            kind = "LOCAL_REGULATION"
    rank, label = _SOURCE_CLASS.get(kind, _SOURCE_CLASS["OTHER"])
    status = str(source.get("temporal_status") or source.get("validation_status") or "UNKNOWN")
    usable = status in {
        "IN_FORCE_ON_REQUESTED_DATE", "DECISION_AVAILABLE_BY_REQUESTED_DATE",
        "VERIFIED_APPLICABLE",
    }
    return {
        "source_family": kind,
        "source_family_label": label,
        "review_priority": rank,
        "temporal_or_validation_status": status,
        "usable_for_conclusion": usable,
        "limitation": "Classement indicatif pour organiser la vérification ; ne tranche ni la hiérarchie complète ni la légalité du document.",
    }


def assess_source_set(sources: list[dict[str, Any]]) -> dict[str, Any]:
    classified = [{**s, "legal_assurance": classify_legal_source(s)} for s in sources]
    local = [s for s in classified if s["legal_assurance"]["source_family"].startswith("LOCAL_")]
    national = [s for s in classified if not s["legal_assurance"]["source_family"].startswith("LOCAL_")]
    warnings: list[str] = []
    if local and national:
        warnings.append("Des sources nationales et locales sont présentes : comparer leur champ d'application, leur date d'effet et leur compatibilité. Leur coexistence ne prouve pas une contradiction.")
    if any(not s["legal_assurance"]["usable_for_conclusion"] for s in classified):
        warnings.append("Au moins une source a un statut temporel ou de validation incomplet : ne pas l'utiliser seule pour établir une règle applicable.")
    if any(s["legal_assurance"]["source_family"] in {"CIRCULAR", "ADMIN_CASELAW"} for s in classified):
        warnings.append("Les circulaires et décisions juridictionnelles exigent une analyse de leur portée, de leur contexte et de leur état jurisprudentiel ; le rang indicatif ne suffit pas.")
    return {
        "sources": classified,
        "comparison_required": bool(local and national),
        "warnings": warnings,
        "status": "A_COMPARER" if local and national else ("VERIFICATION_INCOMPLETE" if warnings else "SOURCES_A_EXAMINER"),
    }

def _normalize_citation_reference(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


_ARTICLE_CITATION_RE = re.compile(
    r"\b(?:articles?|art\.?)\s+([LDR]\.?\s*\d+(?:-\d+)*|\d+(?:-\d+)*)",
    re.IGNORECASE,
)
_STANDALONE_CODE_ARTICLE_RE = re.compile(
    r"\b([LDR])\.?\s*(\d+(?:-\d+)*)\b", re.IGNORECASE
)
_ARTICLE_IN_SOURCE_RE = re.compile(
    r"\b(?:articles?|art\.?)\s*([LDR]\.?\s*\d+(?:-\d+)*|\d+(?:-\d+)*)",
    re.IGNORECASE,
)
_AUTHORITY_CITATION_RE = re.compile(
    r"\b(?:décret|decret|loi|arrêté|arrete|ordonnance|circulaire)\s+"
    r"(?:n[°o]\s*)?((?:19|20)\d{2}[-/]\d+[A-Za-z0-9./-]*|\d{2,3}[-/]\d+[A-Za-z0-9./-]*)",
    re.IGNORECASE,
)
_CASE_CITATION_RE = re.compile(
    r"\b(?:CE|CAA|TA|Conseil\s+d['’]État|Cour\s+administrative\s+d['’]appel|"
    r"Tribunal\s+administratif)\b[^;\n]{0,180}?\b(?:n[°o]\s*|numéro\s+)"
    r"([A-Z0-9][A-Z0-9./-]{3,})",
    re.IGNORECASE,
)
_OFFICIAL_ID_RE = re.compile(r"\b(?:CETATEXT|LEGIARTI|LEGITEXT)\d{12}\b", re.IGNORECASE)
_LEGAL_CLAIM_RE = re.compile(
    r"\b(?:doit|doivent|peut|peuvent|ne peut pas|obligation|interdit|délai|droit|"
    r"prévoit|impose|autorise|permet|applicable|illégal|licite|est tenu|sont tenus|jurisprudence|juridiction|conformément|en vertu|"
    r"ouvre droit|est soumis|s'applique|s’applique)\b",
    re.IGNORECASE,
)


def validate_answer_citations(
    answer: str,
    sources: list[dict[str, Any]],
    *,
    require_explicit_citation: bool = True,
) -> dict[str, Any]:
    """Validate every machine-detectable legal reference against model input sources.

    This is a fail-closed citation check, not a legal opinion or proof that the
    source itself is authentic/current. Only source records marked citation-valid
    are admitted to the reference registry.
    """
    allowed_articles: set[str] = set()
    allowed_authorities: set[str] = set()
    allowed_case_numbers: set[str] = set()
    allowed_ids: set[str] = set()

    for source in sources:
        integrity = source.get("citation_integrity") or {}
        if integrity.get("valid") is not True:
            continue
        article = source.get("article")
        if article:
            allowed_articles.add(_normalize_citation_reference(article))
        official_number = source.get("official_number")
        if official_number:
            allowed_authorities.add(_normalize_citation_reference(official_number))
        case_number = source.get("case_number")
        if case_number:
            allowed_case_numbers.add(_normalize_citation_reference(case_number))
        source_id = source.get("source_id")
        if source_id:
            allowed_ids.add(_normalize_citation_reference(source_id))

        source_text = " ".join(
            str(source.get(key) or "")
            for key in ("title", "article", "official_number", "case_number", "excerpt", "text")
        )
        for match in _ARTICLE_IN_SOURCE_RE.finditer(source_text):
            allowed_articles.add(_normalize_citation_reference(match.group(1)))
        for match in _AUTHORITY_CITATION_RE.finditer(source_text):
            allowed_authorities.add(_normalize_citation_reference(match.group(1)))
        for match in _CASE_CITATION_RE.finditer(source_text):
            allowed_case_numbers.add(_normalize_citation_reference(match.group(1)))
        for match in _OFFICIAL_ID_RE.finditer(source_text):
            allowed_ids.add(_normalize_citation_reference(match.group(0)))

    detected: list[tuple[str, str]] = []
    for match in _ARTICLE_CITATION_RE.finditer(answer or ""):
        detected.append(("article", match.group(1)))
    for match in _STANDALONE_CODE_ARTICLE_RE.finditer(answer or ""):
        detected.append(("article", match.group(1) + match.group(2)))
    for match in _AUTHORITY_CITATION_RE.finditer(answer or ""):
        detected.append(("authority", match.group(1)))
    for match in _CASE_CITATION_RE.finditer(answer or ""):
        detected.append(("case", match.group(1)))
    for match in _OFFICIAL_ID_RE.finditer(answer or ""):
        detected.append(("id", match.group(0)))

    invalid: list[str] = []
    for kind, value in detected:
        normalized = _normalize_citation_reference(value)
        allowed = (
            allowed_articles if kind == "article" else
            allowed_authorities if kind == "authority" else
            allowed_case_numbers if kind == "case" else allowed_ids
        )
        if normalized not in allowed:
            invalid.append(f"{kind}:{value}")

    has_explicit_citation = bool(detected)
    if require_explicit_citation and not has_explicit_citation:
        invalid.append("missing_explicit_source_citation")

    # Every line that makes a legal/operative assertion must carry a reference
    # on that same line; a citation elsewhere in the answer cannot validate it.
    citation_patterns = (
        _ARTICLE_CITATION_RE, _STANDALONE_CODE_ARTICLE_RE,
        _AUTHORITY_CITATION_RE, _CASE_CITATION_RE, _OFFICIAL_ID_RE,
    )
    for line_number, line in enumerate((answer or "").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if _LEGAL_CLAIM_RE.search(stripped) and not any(
            pattern.search(stripped) for pattern in citation_patterns
        ):
            invalid.append(f"uncited_legal_claim_line:{line_number}")

    return {
        "valid": not invalid,
        "has_explicit_citation": has_explicit_citation,
        "detected_references": [f"{kind}:{value}" for kind, value in detected],
        "invalid_references": invalid,
        "registry_counts": {
            "articles": len(allowed_articles),
            "authorities": len(allowed_authorities),
            "case_numbers": len(allowed_case_numbers),
            "official_ids": len(allowed_ids),
        },
        "verification_scope": "EXACT_REFERENCE_MATCH_AGAINST_INJECTED_VALID_SOURCES_ONLY",
    }

