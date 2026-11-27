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
    r"je\s+suis\s+(?:(?:un|une|agent(?:e)?\s+)?(?:contractuel(?:le)?s?|stagiaires?|titulaires?|fonctionnaires?)\b)|"
    r"je\s+ne\s+suis\s+(?:plus|pas|jamais)\s+(?:(?:un|une|agent(?:e)?\s+)?(?:contractuel(?:le)?s?|stagiaires?|titulaires?|fonctionnaires?)\b)|"
    r"je\s+travaille\s+(?:comme|en\s+tant\s+que)\b|mon\s+statut\b|"
    r"depuis\s+(?:le\s+)?(?:\d|janvier\b|février\b|mars\b|avril\b|"
    r"mai\b|juin\b|juillet\b|août\b|septembre\b|octobre\b|"
    r"novembre\b|décembre\b)|"
    r"à\s+temps\b|à\s+\d{1,3}\s*%|"
    r"en\s+(?:cdi|cdd|catégorie\s+[abc]|classe\s+normale)\b|"
    r"titulaire\b|contractuel(?:le)?\b|stagiaire\b|fonctionnaire\b|"
    r"je\s+viens\s+d['’]être\s+(?:agent\s+)?titularisé(?:e|s|es)?\b|"
    r"j['’]ai\s+été\s+(?:agent\s+)?titularisé(?:e|s|es)?\b|"
    r"agent\b|temps\s+(?:partiel|complet|non\s+complet)\b)",
    re.IGNORECASE,
)


_CONTEXTUAL_SCOPE_MODIFIER = re.compile(
    r"^et pour (?:les? |la )?(?:agent(?:e)?s? )?(?:contractuel(?:le)?s?|stagiaires?|"
    r"titulaires?|fonctionnaires?|fpt|fpe|fph|moi|nous|"
    r"temps partiel|temps complet|temps non complet)\b",
    re.IGNORECASE,
)


# Carry only an explicitly declared first-person public-agent status across
# genuine follow-ups. Population questions and third-party descriptions do not
# become facts about the current user.
_EXPLICIT_STATUS_DECLARATION = re.compile(
    r"\b(?:(?:je\s+viens\s+d['’]être|j['’]ai\s+été|je\s+suis)\s+(?:(?:un|une|agent(?:e)?)\s+)?titularisé(?:e|s|es)?|"
    r"(?:je\s+suis|je\s+travaille\s+comme|en\s+tant\s+que|mon\s+statut\s+est)\s+"
    r"(?:(?:un|une)\s+)?(?:(?:agent|agente|fonctionnaire)\s+)?"
    r"(?:contractuel(?:le)?s?|stagiaires?|titulaires?|fonctionnaires?)\b)",
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

_ASSISTANT_REFERENTIAL_FOLLOWUP = re.compile(
    r"^(?:"
    r"(?:peux[- ]tu|pourrais[- ]tu)\s+(?:préciser|détailler|développer|expliquer|reformuler|reprendre)\b|"
    r"(?:qu['’]entends-tu par|que veux-tu dire par)\b|"
    r"tu\s+(?:dis|as dit|as indiqué|viens de dire)\b|"
    r"dans ta réponse\b|"
    r"(?:et\s+)?(?:le|la)\s+(?:premier|première|deuxième|second|seconde|dernier|dernière|précédent|précédente)\s+"
    r"(?:point|élément|condition|règle|disposition|argument)\b|"
    r"(?:ce|cette)\s+(?:point|passage|terme|mot|principe|condition|règle|disposition)\b"
    r")",
    re.IGNORECASE,
)

_LONG_CONTEXTUAL_FOLLOWUP = re.compile(
    r"^(?:dans (?:cette|la) (?:situation|affaire|hypothèse)|"
    r"pour revenir à|à ce propos|concernant (?:ce|cette|mon|ma)|"
    r"suite à (?:ce|cette|mon|ma)|par rapport à (?:ce|cette|mon|ma)|"
    r"comme je (?:l['’]ai|l['’]avais) indiqué|"
    r"pour préciser (?:ma|cette) situation|"
    r"(?:peux[- ]tu|pourrais[- ]tu)\s+(?:préciser|détailler|développer|expliquer|reprendre)\s+"
    r"(?:le (?:premier|première|deuxième|second|seconde|dernier|dernière) point|"
    r"ce point|cette règle|cette disposition|ta réponse|ce que tu as dit))\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ContextualResearchContext:
    question: str
    is_followup: bool
    assistant_context: str | None = None


def _explicit_working_time_declaration(question: str) -> str | None:
    folded = _fold(str(question or ""))
    if re.search(r"\b(?:emploi\s+)?(?:a\s+)?temps\s+non\s+complet\b", folded):
        return "temps non complet"
    if re.search(r"\b(?:emploi\s+)?(?:a\s+)?temps\s+complet\b|\btemps\s+plein\b", folded):
        return "temps complet"
    return None


def build_contextual_research_context(
    current_question: str,
    prior_user_questions: list[str] | None = None,
    prior_assistant_messages: list[str] | None = None,
) -> ContextualResearchContext:
    """Resolve short follow-ups while exposing the classification explicitly."""
    current = " ".join(str(current_question or "").split())
    if not current:
        return ContextualResearchContext(question="", is_followup=False)
    prior_questions = [
        str(item).strip()
        for item in (prior_user_questions or [])
        if str(item).strip()
    ]
    if len(current) >= 220:
        if _LONG_CONTEXTUAL_FOLLOWUP.match(current) and prior_questions:
            prior = next(
                (
                    item for item in reversed(prior_questions)
                    if not _CONTEXTUAL_FOLLOWUP.match(item)
                ),
                prior_questions[-1],
            )
            assistants = [
                str(item).strip()
                for item in (prior_assistant_messages or [])
                if str(item).strip()
            ]
            contextual = f"{current[:5000]}\nContexte antérieur de la situation : {prior[:1200]}"
            if not _EXPLICIT_STATUS_DECLARATION.search(current):
                for earlier_question in reversed(prior_questions):
                    declaration = _EXPLICIT_STATUS_DECLARATION.search(earlier_question)
                    if declaration:
                        contextual += (
                            "\nContexte de statut déclaré précédemment : "
                            + declaration.group(0)
                        )
                        break
            if not _explicit_working_time_declaration(current):
                for earlier_question in reversed(prior_questions):
                    working_time = _explicit_working_time_declaration(earlier_question)
                    if working_time:
                        contextual += (
                            "\nContexte de temps de travail déclaré précédemment : "
                            + working_time
                        )
                        break
            return ContextualResearchContext(
                question=contextual[:6800],
                is_followup=True,
                assistant_context=assistants[-1][-1800:] if assistants else None,
            )
        return ContextualResearchContext(question=current[:5000], is_followup=False)

    if _ASSISTANT_REFERENTIAL_FOLLOWUP.match(current):
        assistants = [
            str(item).strip()
            for item in (prior_assistant_messages or [])
            if str(item).strip()
        ]
        if not prior_questions or not assistants:
            return ContextualResearchContext(question=current[:5000], is_followup=False)
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
            return ContextualResearchContext(question=current[:5000], is_followup=False)
        contextual = f"{current[:5000]}\n{prior[:1200]}"
        if not _EXPLICIT_STATUS_DECLARATION.search(current):
            for earlier_question in reversed(prior_questions):
                declaration = _EXPLICIT_STATUS_DECLARATION.search(earlier_question)
                if declaration:
                    contextual += (
                        "\nContexte de statut déclaré précédemment : "
                        + declaration.group(0)
                    )
                    break
        if not _explicit_working_time_declaration(current):
            for earlier_question in reversed(prior_questions):
                working_time = _explicit_working_time_declaration(earlier_question)
                if working_time:
                    contextual += (
                        "\nContexte de temps de travail déclaré précédemment : "
                        + working_time
                    )
                    break
        return ContextualResearchContext(
            question=contextual[:6800],
            is_followup=True,
            assistant_context=assistants[-1][-1800:],
        )

    if _CONTEXTUAL_FOLLOWUP.match(current):
        if not prior_questions:
            return ContextualResearchContext(question=current[:5000], is_followup=True)
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
            return ContextualResearchContext(question=current[:5000], is_followup=False)
        if current_topics and prior_topics and current_topics.isdisjoint(prior_topics):
            # A short "Et pour ..." that names a different legal family is a
            # new question, not a continuation of the previous legal issue.
            return ContextualResearchContext(question=current[:5000], is_followup=False)
        contextual = f"{current[:5000]}\n{prior[:1200]}"
        # Retain a first-person status declared in an earlier user turn across
        # a genuine follow-up, unless the current turn declares a new status.
        if not _EXPLICIT_STATUS_DECLARATION.search(current):
            for earlier_question in reversed(prior_questions):
                declaration = _EXPLICIT_STATUS_DECLARATION.search(earlier_question)
                if declaration:
                    contextual += (
                        "\nContexte de statut déclaré précédemment : "
                        + declaration.group(0)
                    )
                    break
        if not _explicit_working_time_declaration(current):
            for earlier_question in reversed(prior_questions):
                working_time = _explicit_working_time_declaration(earlier_question)
                if working_time:
                    contextual += (
                        "\nContexte de temps de travail déclaré précédemment : "
                        + working_time
                    )
                    break
        contextual = contextual[:6800]
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
                    return ContextualResearchContext(question=current[:5000], is_followup=False)
                clarification = " ".join(fragments[-1].split())[-200:]
                contextual = (
                    f"{current[:100]}\n{prior[:160]}\n"
                    f"Question de clarification précédente : {clarification}"
                )[:500]
                return ContextualResearchContext(question=contextual, is_followup=True)

    # Independent questions never inherit unrelated facts or topics.
    return ContextualResearchContext(question=current[:5000], is_followup=False)


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


_EXPLICIT_SELF_VERSANT_PATTERNS = {
    "FPT": (
        r"\bje suis (?:un |une )?(?:agent|fonctionnaire) territorial\b",
        r"\bje releve de la fonction publique territoriale\b",
        r"\bmon employeur est (?:(?:la|une) )?(?:mairie|commune|collectivite territoriale)\b",
    ),
    "FPE": (
        r"\bje suis (?:un |une )?(?:agent|fonctionnaire) (?:public )?de l etat\b",
        r"\bje releve de la fonction publique de l etat\b",
        r"\bje travaille (?:au|dans un|pour un) ministere\b",
        r"\bmon employeur est (?:un )?ministere\b",
    ),
    "FPH": (
        r"\bje suis (?:un |une )?(?:agent|fonctionnaire) hospitalier\b",
        r"\bje releve de la fonction publique hospitaliere\b",
        r"\bje travaille (?:dans un|au sein d un) etablissement public de sante\b",
        r"\bmon employeur est (?:un )?etablissement public de sante\b",
    ),
}


def _explicit_self_versant(question: str) -> str | None:
    """Return a branch only when the user explicitly describes their own employer/status."""
    question_lines = str(question or "").splitlines()
    folded = _fold(question_lines[0] if question_lines else "")
    for versant, patterns in _EXPLICIT_SELF_VERSANT_PATTERNS.items():
        if any(re.search(pattern, folded) for pattern in patterns):
            return versant
    return None


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
    ("REPORT_HIERARCHICAL_CONTESTATION", (
        "rapport hierarchique", "rapport contre moi", "rapport fait contre moi",
        "mon chef a fait un rapport", "mon superieur a fait un rapport",
        "rapport a charge", "rapport defavorable", "rapport circonstancie",
        "contester un rapport de mon chef", "contester le rapport de mon superieur",
    )),
    ("DISCIPLINE", ("sanction disciplinaire", "procedure disciplinaire", "conseil de discipline",
                    "avertissement", "blame", "exclusion temporaire", "revocation",
                    "on me sanctionne", "je suis sanctionne", "sanctionne par ma collectivite")),
    # Status is classified independently below: the word "contractuel" must not mask the actual topic.
    ("CONTRACTUAL_EMPLOYMENT", ("renouvellement de contrat", "fin de contrat",
                                "licenciement contractuel", "recrutement contractuel",
                                "terme du contrat", "contrat arrive a son terme",
                                "mon contrat arrive a son terme", "non renouvellement", "refuse le renouvellement",
                                "refus de renouvellement", "refus du renouvellement")),
    ("WORKING_TIME", ("temps de travail", "duree du travail", "temps partiel",
                      "temps non complet", "heures supplementaires", "heures sup",
                      "ihts", "astreinte", "annualisation", "repos compensateur",
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
    ("AVAILABILITY", ("mise en disponibilite", "demande de disponibilite", "disponibilite d office",
                      "disponibilite pour convenances personnelles", "disponibilite")),
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
    # Only the contextualizer may add this dedicated line, based on an
    # explicit first-person declaration in a previous user turn.
    if not _EXPLICIT_STATUS_DECLARATION.search(current_line):
        inherited_status = next((
            line.split(":", 1)[1].strip()
            for line in current_lines[1:]
            if line.startswith("Contexte de statut déclaré précédemment :") and ":" in line
        ), None)
        if inherited_status:
            current_line = inherited_status
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
    negative_titularization = bool(re.search(
        r"\bje\s+(?:ne\s+)?(?:suis|viens\s+d\s+etre|ai\s+ete)\s+"
        r"(?:pas|plus|jamais)\s+(?:agent\s+)?titularise(?:e|s|es)?\b",
        current_folded,
    ))
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
    elif negative_status != "titulaire" and not negative_titularization and (
        re.search(
            r"\b(?:je viens d etre|j ai ete|je suis) (?:agent )?titularise(?:e|s|es)?\b",
            current_folded,
        ) or (short_status_reply and "titulaire" in current_folded) or re.search(
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

    working_time_folded = _fold(str(question or ""))
    if re.search(r"\b(?:emploi\s+)?a\s+temps\s+non\s+complet\b", working_time_folded):
        agent_working_time_status = "NON_COMPLETE_EXPLICIT"
    elif re.search(r"\b(?:emploi\s+)?a\s+temps\s+complet\b|\btemps\s+plein\b", working_time_folded):
        agent_working_time_status = "FULL_TIME_EXPLICIT"
    else:
        agent_working_time_status = "NOT_SPECIFIED"

    explicit_self_versant = _explicit_self_versant(question)
    scope_mismatch_versant = (
        explicit_self_versant
        if explicit_self_versant and explicit_self_versant != public_service
        else None
    )

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
        "explicit_self_versant_mismatch": scope_mismatch_versant,
        "topic": topic,
        "topics": matched_topics,
        "agent_status": status,
        "agent_working_time_status": agent_working_time_status,
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


def build_legal_conversation_state(
    current_question: str,
    conversation_history: list[dict] | None = None,
    is_followup: bool = False,
    current_turn_metadata: dict | None = None,
) -> dict:
    """Build a bounded legal case context from user-declared facts only.

    Assistant prose is never promoted to fact or legal authority. Historical
    metadata is inherited only for a classified follow-up; current-turn values
    take precedence over older declarations.
    """
    state = {
        "continuity": "FOLLOW_UP" if is_followup else "NEW_TOPIC",
        "facts_origin": "USER_DECLARATIONS_ONLY",
        "agent_status_declare": None,
        "temps_travail_declare": None,
        "type_contrat_declare": None,
        "employeur_selectionne": None,
        "periode_faits_declaree": None,
        "messages_utilisateur_pertinents": [],
        "question_clarification_precedente": None,
        "limits": [
            "Les déclarations utilisateur ne sont pas des faits matériellement vérifiés.",
            "Les réponses antérieures de l'assistant ne constituent jamais une preuve juridique.",
            "Un nouveau sujet ne récupère pas les faits personnels d'un dossier antérieur.",
        ],
    }
    if not is_followup:
        return state

    history = [
        item for item in (conversation_history or [])
        if isinstance(item, dict) and item.get("role") in {"user", "assistant"}
    ]
    user_records = [item for item in history if item.get("role") == "user"]
    # Restrict inherited facts to the latest substantive user topic and its
    # short follow-ups. Older independent topics are not part of this case.
    relevant_user_records = []
    for record in reversed(user_records):
        content = str(record.get("content") or "").strip()
        if not content:
            continue
        relevant_user_records.append(record)
        if not _CONTEXTUAL_FOLLOWUP.match(content) and not _CLARIFICATION_REPLY.match(content):
            break
    relevant_user_records.reverse()
    current = " ".join(str(current_question or "").split())

    def metadata_of(record: dict) -> dict:
        value = record.get("metadata")
        if isinstance(value, dict):
            return value
        return {}

    current_meta = current_turn_metadata if isinstance(current_turn_metadata, dict) else {}
    records = relevant_user_records + [{"role": "user", "content": current, "metadata": current_meta}]

    status_declaration = None
    working_time_declaration = None
    contract_declaration = None
    for record in reversed(records):
        content = str(record.get("content") or "")
        if status_declaration is None:
            match = re.search(
                r"\bje ne suis (?:plus|pas|jamais) "
                r"(?:(?:un|une|agent(?:e)?)\s+)?(?:contractuel(?:le)?s?|"
                r"stagiaires?|titulaires?|fonctionnaires?)\b",
                content,
                re.IGNORECASE,
            ) or _EXPLICIT_STATUS_DECLARATION.search(content)
            if match:
                status_declaration = match.group(0)[:180]
        if working_time_declaration is None:
            match = re.search(
                r"\bje ne suis (?:plus|pas) (?:à|a) temps "
                r"(?:partiel|complet|non complet)\b",
                content,
                re.IGNORECASE,
            ) or re.search(
                r"\b(?:je suis|je travaille)\s+(?:à|a)\s+temps\s+"
                r"(?:partiel|complet|non complet)\b",
                content,
                re.IGNORECASE,
            )
            if match:
                working_time_declaration = match.group(0)[:120]
        if contract_declaration is None:
            match = re.search(
                r"\bje ne suis plus en (?:CDD|CDI)\b",
                content,
                re.IGNORECASE,
            )
            if match:
                contract_declaration = match.group(0)[:40].upper()
            else:
                match = re.search(
                    r"\b(?:je suis en|mon contrat est un)\s+(CDD|CDI)\b",
                    content,
                    re.IGNORECASE,
                )
                if match:
                    contract_declaration = match.group(1).upper()
    if (
        status_declaration
        and re.search(r"\bje ne suis (?:plus|pas|jamais) "
                      r"(?:(?:un|une|agent(?:e)?)\s+)?contractuel(?:le)?s?\b",
                      status_declaration, re.IGNORECASE)
        and not re.search(r"\b(?:je suis en|mon contrat est un)\s+(?:CDD|CDI)\b",
                          current, re.IGNORECASE)
    ):
        contract_declaration = "NON_CONTRACTUEL"
    previous_clarification = None
    if history and history[-1].get("role") == "assistant":
        previous_answer = str(history[-1].get("content") or "").strip()
        questions = re.findall(r"[^?]{1,260}\\?", previous_answer[-1600:])
        if questions:
            previous_clarification = " ".join(questions[-1].split())[-260:]
    if previous_clarification:
        if (
            status_declaration is None
            and re.search(r"statut|titulaire|contractuel|fonctionnaire", previous_clarification, re.IGNORECASE)
            and re.fullmatch(r"(?:agent(?:e)?\\s+)?(?:contractuel(?:le)?|titulaire|stagiaire|fonctionnaire)", current, re.IGNORECASE)
        ):
            status_declaration = current[:120] + " (réponse explicite à la clarification précédente)"
        if (
            contract_declaration is None
            and re.search(r"\\bCDD\\b|\\bCDI\\b", previous_clarification, re.IGNORECASE)
            and re.fullmatch(r"(?:en\\s+)?(?:CDD|CDI)", current, re.IGNORECASE)
        ):
            contract_declaration = re.sub(r"^en\\s+", "", current, flags=re.IGNORECASE).upper()
        if (
            working_time_declaration is None
            and re.search(r"temps\\s+(?:partiel|complet|non complet)", previous_clarification, re.IGNORECASE)
            and re.fullmatch(r"(?:à|a)\\s+temps\\s+(?:partiel|complet|non complet)", current, re.IGNORECASE)
        ):
            working_time_declaration = current[:120]

    state["agent_status_declare"] = status_declaration
    state["temps_travail_declare"] = working_time_declaration
    state["type_contrat_declare"] = contract_declaration

    employer = current_meta.get("employer")
    if not employer or employer == "NATIONAL":
        for record in reversed(relevant_user_records):
            previous_employer = metadata_of(record).get("employer")
            if previous_employer and previous_employer != "NATIONAL":
                employer = previous_employer
                break
    state["employeur_selectionne"] = employer if employer and employer != "NATIONAL" else None

    period_keys = ("facts_date", "facts_start_date", "facts_end_date", "situation_ongoing")
    current_period = {key: current_meta.get(key) for key in period_keys}
    if not any(current_period.get(key) for key in period_keys):
        for record in reversed(relevant_user_records):
            candidate = {key: metadata_of(record).get(key) for key in period_keys}
            if any(candidate.get(key) for key in period_keys):
                current_period = candidate
                break
    if any(current_period.get(key) for key in period_keys):
        state["periode_faits_declaree"] = {
            "date_exacte": current_period.get("facts_date"),
            "debut": current_period.get("facts_start_date"),
            "fin": current_period.get("facts_end_date"),
            "situation_en_cours": bool(current_period.get("situation_ongoing")),
            "origine": "déclaration utilisateur dans cette conversation",
        }

    relevant_user_messages = [
        str(record.get("content") or "").strip()[:1200]
        for record in relevant_user_records[-6:]
        if str(record.get("content") or "").strip()
    ]
    state["messages_utilisateur_pertinents"] = relevant_user_messages
    if history and history[-1].get("role") == "assistant":
        previous_answer = str(history[-1].get("content") or "").strip()
        questions = re.findall(r"[^?]{1,260}\?", previous_answer[-1600:])
        if questions:
            state["question_clarification_precedente"] = " ".join(questions[-1].split())[-260:]
    return state
