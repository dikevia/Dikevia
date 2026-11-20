"""Contrôle déterministe des références juridiques avant exposition.

Ce module vérifie la fidélité d'une citation à un document effectivement chargé.
Il ne certifie ni l'authenticité officielle du document, ni son applicabilité temporelle.
"""
from __future__ import annotations

from datetime import date
import re
from typing import Any

ARTICLE_RE = re.compile(r"^[LDR]\d+(?:-\d+)*$", re.I)


def parse_facts_date(value: str | None) -> date | None:
    if value is None or value == "":
        return None
    try:
        # Format ISO strict : pas de date ambiguë interprétée automatiquement.
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError("La date des faits doit être au format AAAA-MM-JJ.")
    if parsed.isoformat() != value:
        raise ValueError("La date des faits doit être au format AAAA-MM-JJ.")
    return parsed


def validate_snapshot_citation(citation: dict[str, Any], article: dict[str, Any]) -> dict[str, Any]:
    """Retourne un rapport vérifiable par code, sans faire confiance au modèle."""
    expected_ref = str(article.get("article", "")).upper()
    cited_ref = str(citation.get("article", "")).upper()
    expected_source = str(article.get("source_id", ""))
    cited_source = str(citation.get("source_id", ""))
    excerpt = str(citation.get("excerpt", "")).strip()
    full_text = str(article.get("text", ""))
    try:
        page_start = int(citation.get("page_start"))
        page_end = int(citation.get("page_end"))
    except (TypeError, ValueError):
        page_start = page_end = -1
    page_match = (page_start == int(article.get("page_start", -2))
                  and page_end == int(article.get("page_end", -2)))
    # Les extraits du moteur peuvent être raccourcis avec une ellipse aux bords.
    excerpt_core = re.sub(r"\s+", " ", excerpt).strip(" …")
    full_core = re.sub(r"\s+", " ", full_text).strip()
    excerpt_match = bool(excerpt_core) and excerpt_core in full_core
    valid = bool(
        ARTICLE_RE.fullmatch(cited_ref)
        and cited_ref == expected_ref
        and cited_source == expected_source
        and page_match
        and excerpt_match
    )
    return {
        "valid": valid,
        "checks": {
            "article_reference": bool(ARTICLE_RE.fullmatch(cited_ref) and cited_ref == expected_ref),
            "source_identity": bool(cited_source and cited_source == expected_source),
            "pdf_page_range": page_match,
            "excerpt_matches_full_text": excerpt_match,
        },
        "verification_scope": "snapshot_document_integrity_only",
        "does_not_verify": [
            "authenticité officielle de la version du texte",
            "applicabilité à la date des faits",
            "textes réglementaires ou spéciaux complémentaires",
            "jurisprudence et actes locaux",
        ],
    }
