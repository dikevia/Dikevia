"""Deterministic routing hints for questions handled by the selected public-service branch.

This module classifies the subject and explicit status cues only. It does not
decide legal applicability, infer missing facts, or create legal evidence.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


def _fold(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or "").casefold())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value)).strip()


CONVERSATION_HISTORY_MESSAGE_LIMIT = 20
RECENT_USER_CONTEXT_LIMIT = 10


_CLARIFICATION_REPLY = re.compile(
    r"^(?:oui\b|non\b|exactement\b|c['’]est\s+(?:ça|bien\s+ça)\b|"
    r"je\s+suis\b|je\s+travaille\b|mon\s+statut\b|"
    r"depuis\s+(?:le\s+)?(?:\d|janvier\b|février\b|mars\b|avril\b|"
    r"mai\b|juin\b|juillet\b|août\b|septembre\b|octobre\b|"
    r"novembre\b|décembre\b)|"
    r"à\s+temps\b|à\s+\d{1,3}\s*%|"
    r"en\s+(?:cdi|cdd|catégorie\s+[abc]|classe\s+normale)\b|"
    r"titulaire\b|contractuel(?:le)?\b|stagiaire\b|fonctionnaire\b|"
    r"agent\b|temps\s+(?:partiel|complet|non\s+complet)\b)",
    re.IGNORECASE,
)


_CONTEXTUAL_FOLLOWUP = re.compile(
    r"^(?:et\s+(?:pour|si|dans|concernant)\b|"
    r"et\s+(?:les|la|le)\s+(?:agents?\s+)?(?:contractuel(?:le)?s?|stagiaires?|"
    r"titulaires?|fonctionnaires?)\b|"
    r"dans ce cas\b|pour les\b|pour la\b|pour le\b|"
    r"qu['’]en est-il\b|quid\b|même chose\b|cela\b|ça\b)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ContextualResearchContext:
    question: str
    is_followup: bool


def build_contextual_research_context(
    current_question: str,
    prior_user_questions: list[str] | None = None,
    prior_assistant_messages: list[str] | None = None,
) -> ContextualResearchContext:
    """Resolve short follow-ups while exposing the classification explicitly."""
    current = " ".join(str(current_question or "").split())
    if not current:
        return ContextualResearchContext(question="", is_followup=False)
    if len(current) >= 220:
        return ContextualResearchContext(question=current[:500], is_followup=False)

    prior_questions = [
        str(item).strip()
        for item in (prior_user_questions or [])
        if str(item).strip()
    ]
    if _CONTEXTUAL_FOLLOWUP.match(current):
        if not prior_questions:
            return ContextualResearchContext(question=current[:500], is_followup=True)
        # A chain of short follow-ups keeps the last substantive user subject.
        prior = next(
            (
                item for item in reversed(prior_questions)
                if not _CONTEXTUAL_FOLLOWUP.match(item)
            ),
            prior_questions[-1],
        )
        contextual = f"{current[:300]}\n{prior[:180]}"[:500]
        return ContextualResearchContext(question=contextual, is_followup=True)

    # A short answer such as "oui" or "contractuel" is contextual only when
    # the assistant's immediately preceding turn actually asked a question.
    if _CLARIFICATION_REPLY.match(current) and prior_questions:
        assistants = [
            str(item).strip()
            for item in (prior_assistant_messages or [])
            if str(item).strip()
        ]
        if assistants:
            fragments = re.findall(r"[^?]{1,260}\?", assistants[-1][-1200:])
            if fragments:
                prior = next(
                    (
                        item for item in reversed(prior_questions)
                        if not _CONTEXTUAL_FOLLOWUP.match(item)
                    ),
                    prior_questions[-1],
                )
                clarification = " ".join(fragments[-1].split())[-200:]
                contextual = (
                    f"{current[:100]}\n{prior[:160]}\n"
                    f"Question de clarification précédente : {clarification}"
                )[:500]
                return ContextualResearchContext(question=contextual, is_followup=True)

    # Independent questions never inherit unrelated facts or topics.
    return ContextualResearchContext(question=current[:500], is_followup=False)


def build_contextual_research_question(
    current_question: str,
    prior_user_questions: list[str] | None = None,
    prior_assistant_messages: list[str] | None = None,
) -> str:
    """Backward-compatible text-only wrapper for contextual research."""
    return build_contextual_research_context(
        current_question,
        prior_user_questions=prior_user_questions,
        prior_assistant_messages=prior_assistant_messages,
    ).question


def qualify_legal_question(
    question: str, employer: str | None = None, public_service: str = "FPT",
) -> dict:
    """Return conservative pre-research routing hints; never a legal conclusion."""
    folded = _fold(question)
    topic = "UNCLASSIFIED"
    for candidate, markers in _TOPIC_MARKERS:
        if any(_fold(marker) in folded for marker in markers):
            topic = candidate
            break

    if re.search(r"\b(agent|agents|je suis)\s+contractuel(le)?s?\b|\bcontractuel(le)?s?\b", folded):
        status = "CONTRACTUEL_EXPLICIT"
    elif re.search(r"\b(stagiaire|fonctionnaire stagiaire)\b", folded):
        status = "STAGIAIRE_EXPLICIT"
    elif re.search(r"\b(titulaire|fonctionnaire titulaire)\b", folded):
        status = "TITULAIRE_EXPLICIT"
    elif re.search(r"\bfonctionnaire\b", folded):
        status = "FONCTIONNAIRE_STATUS_UNSPECIFIED"
    elif re.search(r"\b(cdd|cdi)\b", folded):
        # A CDD/CDI alone does not establish public-agent contractual status.
        status = "EMPLOYMENT_STATUS_AMBIGUOUS"
    else:
        status = "NOT_SPECIFIED"

    # Versant selection is routing context only; explicit references to another
    # branch are flagged so rules are never transposed across public services.
    public_service = str(public_service or "FPT").upper()
    if public_service not in {"FPT", "FPE", "FPH"}:
        public_service = "FPT"
    branch_markers = {
        "FPT": ("OUT_OF_SCOPE_FPE", (
            "fonction publique de l etat", "fonction publique d etat",
            "agent de l etat", "agents de l etat", "fonctionnaire de l etat",
            "fonctionnaires de l etat",
        ), "OUT_OF_SCOPE_FPH", (
            "fonction publique hospitaliere", "agent hospitalier",
            "agents hospitaliers", "fonctionnaire hospitalier",
            "etablissement public de sante", "personnel hospitalier",
        )),
        "FPE": ("OUT_OF_SCOPE_FPT", (
            "fonction publique territoriale", "agent territorial", "agents territoriaux",
            "fonctionnaire territorial", "collectivite territoriale", "collectivites territoriales",
        ), "OUT_OF_SCOPE_FPH", (
            "fonction publique hospitaliere", "agent hospitalier",
            "agents hospitaliers", "fonctionnaire hospitalier",
            "etablissement public de sante", "personnel hospitalier",
        )),
        "FPH": ("OUT_OF_SCOPE_FPT", (
            "fonction publique territoriale", "agent territorial", "agents territoriaux",
            "fonctionnaire territorial", "collectivite territoriale", "collectivites territoriales",
        ), "OUT_OF_SCOPE_FPE", (
            "fonction publique de l etat", "fonction publique d etat",
            "agent de l etat", "agents de l etat", "fonctionnaire de l etat",
            "fonctionnaires de l etat",
        )),
    }
    first_code, first_markers, second_code, second_markers = branch_markers[public_service]
    scope_status = f"{public_service}_PRODUCT_SCOPE"
    scope_evidence = []
    for candidate, markers in (
        (first_code, first_markers),
        (second_code, second_markers),
        ("OUT_OF_SCOPE_PRIVATE", (
            "salarie du prive", "salarie dans le prive", "secteur prive",
            "entreprise privee", "employeur prive", "droit prive",
        )),
    ):
        matched = [marker for marker in markers if _fold(marker) in folded]
        if matched:
            scope_status = candidate
            scope_evidence = matched[:3]
            break

    local_employer_selected = bool(employer and employer != "NATIONAL")
    priorities = [
        "CODE_GENERAL_FONCTION_PUBLIQUE",
        f"{public_service}_IMPLEMENTING_LAWS_DECREES_AND_ORDERS",
        "RELEVANT_ADMINISTRATIVE_CASE_LAW",
    ]
    if public_service == "FPT" and local_employer_selected:
        priorities.append("VALIDATED_LOCAL_COLLECTIVITY_ACTS_AND_DOCUMENTS")

    return {
        "target_legal_field": {"FPT": "FRENCH_TERRITORIAL_PUBLIC_SERVICE", "FPE": "FRENCH_STATE_PUBLIC_SERVICE", "FPH": "FRENCH_HOSPITAL_PUBLIC_SERVICE"}[public_service],
        "scope_status": scope_status,
        "scope_evidence": scope_evidence,
        "topic": topic,
        "agent_status": status,
        "public_service": public_service,
        "employer_document_scope": (
            "LOCAL_EMPLOYER_SELECTED" if public_service == "FPT" and local_employer_selected else "NATIONAL_CORPUS_ONLY"
        ),
        "research_priorities": priorities,
        "code_du_travail_rule": "DO_NOT_APPLY_WITHOUT_VERIFIED_EXPRESS_LEGAL_BASIS_OR_REFERRAL",
        "qualification_limits": [
            "Routing hints only; not a determination of legal applicability.",
            "Do not infer agent status, facts, dates, or local rules when not stated.",
            "Do not transpose rules between FPT, FPE, FPH or the private sector.",
        ],
    }
