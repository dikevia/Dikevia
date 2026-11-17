"""Deterministic legal-source classification and cautious comparison helpers.

This module ranks source families for review workflows; it does not decide
legality or resolve conflicts without a complete legal analysis.
"""
from __future__ import annotations

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
