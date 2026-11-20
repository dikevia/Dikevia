"""Deterministic routing hints for questions handled by the FPT legal assistant.

This module classifies the subject and explicit status cues only. It does not
decide legal applicability, infer missing facts, or create legal evidence.
"""
from __future__ import annotations

import re
import unicodedata


def _fold(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or "").casefold())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value)).strip()


_TOPIC_MARKERS = (
    ("UNION_RIGHTS", ("droit syndical", "droits syndicaux", "syndicat", "representant du personnel", "representants du personnel",
                      "decharge d activite", "autorisation speciale d absence syndicale",
                      "local syndical", "comite social territorial", "cst", "formation specialisee")),
    ("DISCIPLINE", ("sanction disciplinaire", "procedure disciplinaire", "conseil de discipline",
                    "avertissement", "blame", "exclusion temporaire", "revocation")),
    ("CONTRACTUAL_EMPLOYMENT", ("agent contractuel", "agents contractuels", "cdd", "cdi",
                                "renouvellement de contrat", "fin de contrat")),
    ("WORKING_TIME", ("temps de travail", "duree du travail", "heures supplementaires",
                      "heures sup", "ihts", "astreinte", "annualisation", "repos compensateur",
                      "travail de nuit", "travail le dimanche")),
    ("SICK_LEAVE_AND_SERVICE_INJURY", ("conge maladie", "citis", "accident de service",
                                       "maladie professionnelle", "conge longue maladie",
                                       "conge longue duree")),
    ("HARASSMENT_AND_PROTECTION", ("harcelement moral", "harcelement sexuel",
                                   "agissement sexiste", "protection fonctionnelle")),
    ("REMUNERATION", ("remuneration", "traitement indiciaire", "regime indemnitaire",
                      "rifseep", "ifse", "nbi", "prime", "indemnite")),
    ("LEAVE", ("conges annuels", "conge annuel", "compte epargne temps",
               "autorisation speciale d absence")),
)


def qualify_legal_question(question: str, employer: str | None = None) -> dict:
    """Return conservative pre-research routing hints; never a legal conclusion."""
    folded = _fold(question)
    topic = "UNCLASSIFIED"
    for candidate, markers in _TOPIC_MARKERS:
        if any(_fold(marker) in folded for marker in markers):
            topic = candidate
            break

    if re.search(r"\b(agent|agents|je suis)\s+contractuel(le)?\b|\bcontractuel(le)?\b|\bcdd\b|\bcdi\b", folded):
        status = "CONTRACTUEL_EXPLICIT"
    elif re.search(r"\b(stagiaire|fonctionnaire stagiaire)\b", folded):
        status = "STAGIAIRE_EXPLICIT"
    elif re.search(r"\b(titulaire|fonctionnaire titulaire)\b", folded):
        status = "TITULAIRE_EXPLICIT"
    elif re.search(r"\bfonctionnaire\b", folded):
        status = "FONCTIONNAIRE_STATUS_UNSPECIFIED"
    else:
        status = "NOT_SPECIFIED"

    local_employer_selected = bool(employer and employer != "NATIONAL")
    priorities = [
        "CODE_GENERAL_FONCTION_PUBLIQUE",
        "FPT_IMPLEMENTING_LAWS_DECREES_AND_ORDERS",
        "RELEVANT_ADMINISTRATIVE_CASE_LAW",
    ]
    if local_employer_selected:
        priorities.append("VALIDATED_LOCAL_COLLECTIVITY_ACTS_AND_DOCUMENTS")

    return {
        "target_legal_field": "FRENCH_TERRITORIAL_PUBLIC_SERVICE",
        "topic": topic,
        "agent_status": status,
        "employer_document_scope": (
            "LOCAL_EMPLOYER_SELECTED" if local_employer_selected else "NATIONAL_CORPUS_ONLY"
        ),
        "research_priorities": priorities,
        "code_du_travail_rule": "DO_NOT_APPLY_WITHOUT_VERIFIED_EXPRESS_LEGAL_BASIS_OR_REFERRAL",
        "qualification_limits": [
            "Routing hints only; not a determination of legal applicability.",
            "Do not infer agent status, facts, dates, or local rules when not stated.",
            "Do not transpose private-sector rules to territorial public servants.",
        ],
    }
