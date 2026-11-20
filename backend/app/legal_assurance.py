"""Deterministic legal-source classification and cautious comparison helpers.

This module ranks source families for review workflows; it does not decide
legality or resolve conflicts without a complete legal analysis.
"""
from __future__ import annotations

import re
import unicodedata
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
        "VERSION_RETRIEVED_AT_REQUESTED_DATE",
        "DECISION_ANTERIOR_OR_CONTEMPORANEOUS_TO_FACTS",
        "DECISION_POSTERIOR_TO_FACTS",
        "DECISION_DATE_VERIFIED_NO_FACTS_DATE",
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
_SOURCE_ID_CITATION_RE = re.compile(r"\[source:([A-Za-z0-9:_-]{6,128})\]", re.IGNORECASE)
_NUMERIC_FACT_RE = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:%|jours?|mois|ans?|heures?|minutes?|euros?|€)(?!\w)", re.IGNORECASE)
_DATE_FACT_RE = re.compile(r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}(?:er)?\s+(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+\d{4})\b", re.IGNORECASE)
_EVIDENCE_STOPWORDS = {
    "article", "code", "general", "fonction", "publique", "territoriale", "territorial",
    "agent", "agents", "doit", "doivent", "peut", "peuvent", "est", "sont", "etre",
    "avoir", "dans", "pour", "avec", "selon", "une", "des", "les", "du", "de", "la",
    "le", "aux", "au", "sur", "par", "sous", "qui", "que", "dont", "ainsi", "toute",
    "toutes", "tous", "leur", "leurs", "ses", "son", "sa", "cette", "celui", "celle",
    "ceux", "notamment", "relatif", "relative", "relatifs", "relatives", "faits",
    "situation", "regard", "exposee", "expose", "numero",
}
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
            for key in ("title", "article", "official_number", "case_number", "official_source_id", "source_version_id", "excerpt", "text")
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
    for match in _SOURCE_ID_CITATION_RE.finditer(answer or ""):
        detected.append(("id", match.group(1)))

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
        _SOURCE_ID_CITATION_RE,
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



def _normalized_evidence_text(value: Any) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", str(value or ""))).strip()


def _evidence_tokens(value: Any) -> set[str]:
    decomposed = unicodedata.normalize("NFKD", str(value or "").casefold())
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    tokens = set(re.findall(r"[a-z]{4,}", plain))
    return tokens - _EVIDENCE_STOPWORDS


def validate_claim_evidence(payload: Any, sources: list[dict[str, Any]]) -> dict[str, Any]:
    """Fail closed unless each generated legal claim quotes its own eligible source.

    This verifies exact quote provenance, source identity, date/scope eligibility and
    simple numeric/date consistency. It does not prove semantic entailment; human
    legal review remains necessary for the interpretation of each quoted passage.
    """
    if not isinstance(payload, dict) or not isinstance(payload.get("claims"), list):
        return {
            "valid": False, "claims": [],
            "invalid_claims": ["structured_claims_missing_or_invalid"],
            "verification_scope": "EXACT_QUOTE_SOURCE_DATE_SCOPE_NUMERIC_AND_LEXICAL_RELEVANCE_CHECKS",
        }

    raw_claims = payload["claims"]
    if len(raw_claims) > 12:
        return {
            "valid": False, "claims": [],
            "invalid_claims": ["too_many_claims"],
            "verification_scope": "EXACT_QUOTE_SOURCE_DATE_SCOPE_AND_NUMERIC_CHECKS",
        }

    eligible_statuses = {
        "IN_FORCE_ON_REQUESTED_DATE",
        "DECISION_AVAILABLE_BY_REQUESTED_DATE",
        "VERSION_RETRIEVED_AT_REQUESTED_DATE",
        "DECISION_ANTERIOR_OR_CONTEMPORANEOUS_TO_FACTS",
        "DECISION_POSTERIOR_TO_FACTS",
        "DECISION_DATE_VERIFIED_NO_FACTS_DATE",
        "VERIFIED_APPLICABLE",
    }
    eligible_by_id: dict[str, list[dict[str, Any]]] = {}
    for source in sources:
        source_id = source.get("source_id")
        if not isinstance(source_id, str) or not source_id:
            continue
        source_type = str(source.get("source_type") or "")
        integrity = source.get("citation_integrity") or {}
        temporal_status = source.get("temporal_status")
        if integrity.get("valid") is not True:
            continue
        if source_type in {"CGFP_SNAPSHOT", "LEGIFRANCE_CETAT_SEARCH"}:
            continue
        if source.get("content_kind") == "METADATA":
            continue
        if source.get("reference_role") == "BASELINE_CONTEXT_ONLY":
            continue
        if source.get("analysis_eligible") is False or source.get("public_service_scope") == "SCOPE_TO_VERIFY":
            continue
        general_information_only = (
            temporal_status == "TEMPORAL_SCOPE_INCOMPLETE"
            and source.get("general_info_eligible") is True
        )
        if temporal_status not in eligible_statuses and not general_information_only:
            continue
        if source_type in {"LOCAL_DOCUMENT", "LOCAL_COLLECTIVITY_DOCUMENT"}:
            if source.get("validation_status") != "VERIFIED_APPLICABLE":
                continue
        elif source_type not in {
            "LEGIFRANCE_API", "LEGIFRANCE_LODA", "LEGIFRANCE_CETAT_FULL_TEXT",
        } and source.get("official_source") is not True:
            continue
        evidence_text = source.get("excerpt") or str(source.get("text") or "")[:1800]
        normalized_evidence = _normalized_evidence_text(evidence_text)
        if len(normalized_evidence) < 20:
            continue
        eligible_by_id.setdefault(source_id, []).append({
            "source": source,
            "normalized_evidence": normalized_evidence,
        })

    validated: list[dict[str, str]] = []
    invalid: list[str] = []
    for index, item in enumerate(raw_claims):
        if not isinstance(item, dict):
            invalid.append(f"claim_{index}:not_an_object")
            continue
        claim_text = item.get("text")
        source_id = item.get("source_id")
        quote = item.get("quote")
        if not isinstance(claim_text, str) or not 12 <= len(claim_text.strip()) <= 1500 or "\n" in claim_text or "\r" in claim_text:
            invalid.append(f"claim_{index}:invalid_text")
            continue
        if not isinstance(source_id, str) or not 6 <= len(source_id) <= 128:
            invalid.append(f"claim_{index}:invalid_source_id")
            continue
        if not isinstance(quote, str) or not 20 <= len(quote.strip()) <= 1000:
            invalid.append(f"claim_{index}:invalid_quote")
            continue
        matching_sources = eligible_by_id.get(source_id, [])
        if len(matching_sources) != 1:
            invalid.append(f"claim_{index}:source_missing_ineligible_or_ambiguous")
            continue
        normalized_quote = _normalized_evidence_text(quote)
        normalized_evidence = matching_sources[0]["normalized_evidence"]
        if normalized_quote not in normalized_evidence:
            invalid.append(f"claim_{index}:quote_not_exactly_found_in_source")
            continue
        claim_tokens = _evidence_tokens(claim_text)
        quote_tokens = _evidence_tokens(normalized_quote)
        lexical_overlap = len(claim_tokens & quote_tokens) / max(1, len(claim_tokens))
        if len(claim_tokens) < 2 or lexical_overlap < 0.25:
            invalid.append(f"claim_{index}:quote_not_relevantly_aligned")
            continue
        # Dates and quantified rules are high-risk hallucination vectors. Require
        # every such value in the paraphrase to appear in its exact supporting quote.
        quote_folded = normalized_quote.casefold()
        unsupported_numbers = [
            value for value in _NUMERIC_FACT_RE.findall(claim_text)
            if _normalized_evidence_text(value).casefold() not in quote_folded
        ]
        unsupported_dates = [
            value for value in _DATE_FACT_RE.findall(claim_text)
            if _normalized_evidence_text(value).casefold() not in quote_folded
        ]
        if unsupported_numbers or unsupported_dates:
            invalid.append(f"claim_{index}:unsupported_numeric_or_date_detail")
            continue
        source = matching_sources[0]["source"]
        source_title = str(source.get("title") or source_id).strip()
        source_reference = source.get("article") or source.get("official_number") or source.get("case_number")
        if source_reference and str(source_reference).casefold() not in source_title.casefold():
            source_title = f"{source_title} — réf. {source_reference}"
        validated.append({
            "text": " ".join(claim_text.split()),
            "source_id": source_id,
            "source_title": source_title[:300],
            "quote": " ".join(quote.split()),
        })

    return {
        "valid": not invalid,
        "claims": validated,
        "invalid_claims": invalid,
        "claim_count": len(validated),
        "verification_scope": "EXACT_QUOTE_SOURCE_DATE_SCOPE_NUMERIC_AND_LEXICAL_RELEVANCE_CHECKS_NOT_SEMANTIC_ENTAILMENT",
    }
