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


_CONTEXTUAL_SCOPE_MODIFIER = re.compile(
    r"^et pour (?:les? |la )?(?:agent(?:e)?s? )?(?:contractuel(?:le)?s?|stagiaires?|"
    r"titulaires?|fonctionnaires?|fpt|fpe|fph|moi|nous|"
    r"temps partiel|temps complet|temps non complet)\b",
    re.IGNORECASE,
)


_CONTEXTUAL_FOLLOWUP = re.compile(
    r"^(?:et\s+(?:pour|si|dans|concernant)\b|"
    r"et\s+(?:les|la|le)\s+(?:agent(?:e)?s?\s+)?(?:contractuel(?:le)?s?|stagiaires?|"
    r"titulaires?|fonctionnaires?)\b|"
    r"pour\s+les?\s+(?:agent(?:e)?s?\s+)?(?:contractuel(?:le)?s?|stagiaires?|"
    r"titulaires?|fonctionnaires?)\s*\??$|"
    r"dans ce cas\b|"
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
        current_topics = _matched_question_topics(current)
        prior_topics = _matched_question_topics(prior)
        if (
            prior_topics
            and not current_topics
            and _fold(current).startswith("et pour ")
            and not _CONTEXTUAL_SCOPE_MODIFIER.match(_fold(current))
        ):
            # Unknown named subjects are safer as independent questions than
            # as accidental continuations of an unrelated legal topic.
            return ContextualResearchContext(question=current[:500], is_followup=False)
        if current_topics and prior_topics and current_topics.isdisjoint(prior_topics):
            # A short "Et pour ..." that names a different legal family is a
            # new question, not a continuation of the previous legal issue.
            return ContextualResearchContext(question=current[:500], is_followup=False)
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
                current_topics = _matched_question_topics(current)
                prior_topics = _matched_question_topics(prior)
                if current_topics and prior_topics and current_topics.isdisjoint(prior_topics):
                    # A substantive new legal topic must not be mistaken for
                    # an answer merely because it starts with "Je suis".
                    return ContextualResearchContext(question=current[:500], is_followup=False)
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


_TOPIC_MARKERS = (
    ("UNION_RIGHTS", ("droit syndical", "droits syndicaux", "syndicat", "representant du personnel",
                      "representants du personnel", "representant syndical", "representants syndicaux",
                      "decharge d activite", "decharge syndicale", "credit de temps syndical",
                      "credit d heures syndical", "asa syndicale", "autorisation speciale d absence syndicale",
                      "local syndical", "locaux syndicaux", "reunion d information syndicale",
                      "formation syndicale", "comite social territorial", "cst", "formation specialisee")),
    ("TERMINATION_OF_TITULAR", ("peut me virer", "me virer", "me mettre dehors",
                                "mettre dehors", "me licencier", "peut me licencier",
                                "mettre fin a mes fonctions", "fin de mes fonctions",
                                "licenciement fonctionnaire", "radiation des cadres",
                                "perte de la qualite de fonctionnaire", "insuffisance professionnelle")),
    ("STAFFING_AND_WORK_CONDITIONS", ("manque de personnel", "manque d effectifs",
                                      "pas assez d agents", "pas suffisamment d agents",
                                      "on manque d agents", "on est pas assez nombreux",
                                      "on n est pas assez nombreux", "sous effectif",
                                      "effectif reduit", "effectifs insuffisants",
                                      "equipe en sous effectif", "equipes en sous effectif",
                                      "mon service est en sous effectif", "surcharge de travail",
                                      "ne renforce pas les equipes", "ne recrute pas",
                                      "charge de travail", "conditions de travail",
                                      "risques psychosociaux", "risques professionnels",
                                      "sante et securite au travail")),
    ("DISCIPLINE", ("sanction disciplinaire", "procedure disciplinaire", "conseil de discipline",
                    "avertissement", "blame", "exclusion temporaire", "revocation",
                    "on me sanctionne", "je suis sanctionne", "sanctionne par ma collectivite")),
    # Status is classified independently below: the word "contractuel" must not mask the actual topic.
    ("CONTRACTUAL_EMPLOYMENT", ("renouvellement de contrat", "fin de contrat",
                                "licenciement contractuel", "recrutement contractuel",
                                "terme du contrat", "non renouvellement", "refuse le renouvellement",
                                "refus de renouvellement", "refus du renouvellement")),
    ("WORKING_TIME", ("temps de travail", "duree du travail", "heures supplementaires",
                      "heures sup", "ihts", "astreinte", "annualisation", "repos compensateur",
                      "travail de nuit", "travail le dimanche", "venir le dimanche",
                      "travailler le dimanche", "venir travailler le dimanche")),
    ("WORKPLACE_INCIDENT_AND_AGENT_PROTECTION", (
        "agresse par un usager", "agressee par un usager", "agression par un usager",
        "agression d un usager", "agression au travail", "agent victime d une agression",
        "violence d un usager", "menace d un usager", "usager m a frappe",
        "refuse que je fasse un rapport", "refuse de faire un rapport",
    )),
    ("SICK_LEAVE_AND_SERVICE_INJURY", ("conge maladie", "arret maladie", "arrets maladie", "citis", "accident de service",
                                       "maladie professionnelle", "conge longue maladie",
                                       "conge longue duree")),
    ("HARASSMENT_AND_PROTECTION", ("harcelement moral", "harcelement sexuel",
                                   "agissement sexiste", "protection fonctionnelle")),
    ("REMUNERATION", ("remuneration", "traitement indiciaire", "regime indemnitaire",
                      "rifseep", "ifse", "nbi", "prime", "indemnite")),
    ("LEAVE", ("conges annuels", "conge annuel", "poser des conges", "prendre des conges",
               "compte epargne temps", "autorisation speciale d absence")),
    ("RETIREMENT", ("retraite", "pension", "liquidation des droits", "age legal de depart",
                    "depart a la retraite", "retraite progressive", "carriere longue")),
    ("TELEWORK", ("teletravail", "tele travailler", "jours de teletravail", "autorisation de teletravail")),
    ("PROFESSIONAL_TRAINING", ("formation professionnelle", "formation continue", "conge de formation",
                               "cpf", "compte personnel de formation", "bilan de competences")),
    ("CAREER_AND_PROMOTION", ("avancement de grade", "promotion interne", "avancement d echelon",
                              "entretien professionnel", "evaluation professionnelle", "mobilite interne")),
)

def _matched_question_topics(question: str) -> set[str]:
    folded = _fold(question)
    return {
        candidate for candidate, markers in _TOPIC_MARKERS
        if any(_fold(marker) in folded for marker in markers)
    }


def qualify_legal_question(
    question: str, employer: str | None = None, public_service: str = "FPT",
) -> dict:
    """Return conservative pre-research routing hints; never a legal conclusion."""
    folded = _fold(question)
    matched_topics = [
        candidate for candidate, markers in _TOPIC_MARKERS
        if any(_fold(marker) in folded for marker in markers)
    ]
    topic = matched_topics[0] if matched_topics else "UNCLASSIFIED"

    # Status describes the user's own situation, not a third party or a
    # population mentioned in the question. Use only the current turn's first
    # line so prior conversation context cannot overwrite a new status.
    current_lines = str(question or "").splitlines()
    current_line = current_lines[0] if current_lines else ""
    current_folded = _fold(current_line)
    negative_status_match = re.search(
        r"\bje\s+(?:ne\s+)?(?:suis|travaille)\s+(?:pas|plus|jamais)\s+"
        r"(?:comme\s+)?(?:(?:un|une|agent(?:e)?)\s+)?"
        r"(contractuel(?:le)?s?|stagiaires?|titulaires?|fonctionnaires?)\b",
        current_folded,
    )
    negative_status_raw = (
        _fold(negative_status_match.group(1))
        if negative_status_match else None
    )
    negative_status = (
        "contractuel" if negative_status_raw and negative_status_raw.startswith("contractuel")
        else "stagiaire" if negative_status_raw and negative_status_raw.startswith("stagiaire")
        else "titulaire" if negative_status_raw and negative_status_raw.startswith("titulaire")
        else "fonctionnaire" if negative_status_raw and negative_status_raw.startswith("fonctionnaire")
        else None
    )
    short_status_reply = re.fullmatch(
        r"(?:(?:et\s+)?pour\s+les?\s+|et\s+les?\s+)?(?:agent(?:e)?s?\s+)?"
        r"(?:contractuel(?:le)?s?|stagiaires?|titulaires?|fonctionnaires?)\s*\??",
        current_folded,
    )
    if negative_status != "contractuel" and ((
        short_status_reply and re.search(r"contractuel", current_folded)
    ) or re.search(
        r"\b(?:je suis|je travaille comme|en tant qu|en tant que|mon statut est)\s+"
        r"(?:(?:un|une)\s+)?(?:(?:agent|agente)\s+)?contractuel(?:le)?s?\b",
        current_folded,
    )):
        status = "CONTRACTUEL_EXPLICIT"
    elif negative_status != "stagiaire" and ((
        short_status_reply and "stagiaire" in current_folded
    ) or re.search(
        r"\b(?:je suis|je travaille comme|en tant qu|en tant que|mon statut est)\s+"
        r"(?:(?:un|une)\s+)?(?:fonctionnaire\s+)?stagiaire\b",
        current_folded,
    )):
        status = "STAGIAIRE_EXPLICIT"
    elif negative_status != "titulaire" and ((
        short_status_reply and "titulaire" in current_folded
    ) or re.search(
        r"\b(?:je suis|je travaille comme|en tant qu|en tant que|mon statut est)\s+"
        r"(?:(?:un|une)\s+)?(?:(?:agent|fonctionnaire)\s+)?titulaire\b",
        current_folded,
    )):
        status = "TITULAIRE_EXPLICIT"
    elif negative_status != "fonctionnaire" and ((
        short_status_reply and "fonctionnaire" in current_folded
    ) or re.search(r"\bje suis fonctionnaire\b", current_folded)):
        status = "FONCTIONNAIRE_STATUS_UNSPECIFIED"
    elif re.search(r"\b(?:je suis|je travaille) en (?:cdd|cdi)\b", current_folded):
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
        "topics": matched_topics,
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
