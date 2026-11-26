import asyncio
import json
import inspect
from datetime import date, datetime
from zoneinfo import ZoneInfo
from uuid import uuid4
import logging
import re
import time

from .schemas import AskRequest, AskResponse
from .config import settings
from .cgfp import get_cgfp_article
from .cgfp_relevance import search_cgfp
from .fpt_scope import _fold, classify_public_service_scope, is_ihts_relevant_source, is_ihts_question, is_topic_relevant_source
from .legal_validation import validate_snapshot_citation, parse_facts_date
from .ai_provider import analyze_question, plan_legal_research, evaluate_source_relevance, verify_claim_entailment, parse_structured_answer, AIAnalysisResult, AIProviderUnavailable, AIAnalysisRefusedNoSources, answer_references_are_grounded, check_provider_availability
from .legifrance import connector as legifrance, LegifranceUnavailable
from .jurisprudence import AdministrativeCaseLawConnector, decision_temporal_status, interleave_case_law_results
from .legal_corpus import search_legal_corpus, select_multi_source_chunks, corpus_version_citation_id
from .legal_assurance import assess_source_set, validate_answer_citations, validate_claim_evidence
from .local_corpus import search_local_documents, local_document_temporal_status
from .article_lookup import missing_direct_article_reference
from .legal_search_plan import (
    build_official_search_queries,
    build_official_research_axes,
    select_required_research_axes,
    merge_ai_and_fallback_research_queries,
    clarification_for_union_assistance_summons,
)
from .legal_qualification import (
    qualify_legal_question, build_contextual_research_context,
    CONVERSATION_HISTORY_MESSAGE_LIMIT,
)


def _source_metadata(source: dict) -> dict:
    value = source.get("raw_metadata")
    return value if isinstance(value, dict) else {}


def _citation_is_valid(source: dict) -> bool:
    if not isinstance(source, dict):
        return False
    integrity = source.get("citation_integrity")
    return isinstance(integrity, dict) and integrity.get("valid") is True


def _cgfp_article_fpt_eligible(article_ref: str, target_versant: str = "FPT") -> bool:
    """Check the article body before treating a CGFP hit as a selected-branch research lead."""
    normalized_ref = re.sub(r"\s+", "", str(article_ref or "")).upper()
    if not re.fullmatch(r"[LDR]\d+(?:-\d+)*", normalized_ref):
        return False
    article_document = get_cgfp_article(normalized_ref)
    if not article_document:
        return False
    scope = classify_public_service_scope({
        "title": f"Code général de la fonction publique — article {normalized_ref}",
        "article": normalized_ref,
        "text": article_document.get("text") or "",
        "document_kind": "CODE",
    }, target_versant=target_versant)
    return scope.get("analysis_eligible") is True


def _build_versant_fallback_research(
    question: str, public_service: str,
) -> tuple[list[str], list[str]]:
    """Build deterministic fallback searches without leaking FPT templates to FPE/FPH."""
    if public_service == "FPT":
        queries = build_official_search_queries(question)
        axes = build_official_research_axes(question)
        # A single recognized topic does not become a mandatory coverage axis:
        # only independently identified sub-questions are required to be covered.
        return queries, axes
    branch_qualifier = (
        "fonction publique de l'État" if public_service == "FPE"
        else "fonction publique hospitalière"
    )
    branch_query = f"{question} {branch_qualifier}".strip()
    topic_labels = {
        "UNION_RIGHTS": "droits syndicaux et autorisations spéciales d'absence",
        "TERMINATION_OF_TITULAR": "fin de fonctions et cessation d'emploi du fonctionnaire",
        "STAFFING_AND_WORK_CONDITIONS": "effectifs, charge et conditions de travail",
        "DISCIPLINE": "procédure disciplinaire et sanctions",
        "CONTRACTUAL_EMPLOYMENT": "contrat, renouvellement et fin de contrat",
        "SICK_LEAVE_AND_SERVICE_INJURY": "congé maladie, accident de service et CITIS",
        "HARASSMENT_AND_PROTECTION": "harcèlement et protection fonctionnelle",
        "REMUNERATION": "rémunération, traitement et indemnités",
        "LEAVE": "congés et autorisations d'absence",
        "RETIREMENT": "retraite et pension",
        "TELEWORK": "télétravail",
        "PROFESSIONAL_TRAINING": "formation professionnelle",
        "CAREER_AND_PROMOTION": "carrière et avancement",
        "AVAILABILITY": "disponibilité",
        "WORKING_TIME": "temps de travail, heures supplémentaires et astreintes",
        "WORKPLACE_INCIDENT_AND_AGENT_PROTECTION": "agression par un usager et protection de l'agent",
    }
    topics = qualify_legal_question(
        question, public_service=public_service,
    ).get("topics") or []
    focused_axes = [
        f"{question} — {topic_labels[topic]} — {branch_qualifier}"
        for topic in topics if topic in topic_labels
    ][:4]
    if len(focused_axes) > 1:
        # Keep one broad fallback, then one deterministic query/coverage axis
        # per independently recognized legal family. The merge routine reserves
        # these focused axes so model-generated queries cannot hide a subtopic.
        return [branch_query, *focused_axes], focused_axes
    return [branch_query], [branch_query]


def _build_targeted_cgfp_article_queries(question: str, public_service: str = "FPT") -> list[str]:
    """Return exact CGFP CMO provisions for explicit ordinary sick-leave questions."""
    if str(public_service or "").upper() != "FPT":
        return []
    folded = _fold(str(question or ""))
    if not any(marker in folded for marker in (
        "conge de maladie ordinaire", "maladie ordinaire",
        "jour de carence", "jours de carence", "cmo",
    )):
        return []
    return [f"article L822-{number}" for number in range(1, 6)]


def _build_code_research_queries(
    research_queries: list[str],
    cgfp_article_queries: list[str] | None = None,
    max_queries: int = 5,
) -> list[str]:
    """Keep every legal axis; use only spare budget for exact article lookups."""
    limit = max(0, int(max_queries))
    base_queries = list(dict.fromkeys(query for query in research_queries if query))[:limit]
    exact_budget = max(0, limit - len(base_queries))
    return [
        *base_queries,
        *[query for query in dict.fromkeys(cgfp_article_queries or []) if query][:exact_budget],
    ]


def _build_targeted_regulatory_queries(
    question: str, public_service: str = "FPT",
) -> list[str]:
    """Add exact, date-scoped implementing-text searches for the selected public-service branch."""
    folded = " ".join(str(question or "").casefold().split())
    queries: list[str] = []
    availability = any(marker in folded for marker in (
        "disponibilité", "disponibilite", "convenances personnelles",
    ))
    if availability:
        branch_availability_articles = {
            "FPT": (
                "décret n° 86-68 du 13 janvier 1986 article 21 disponibilité sur demande convenances personnelles fonctionnaires territoriaux",
            ),
            "FPE": (
                "décret n° 85-986 du 16 septembre 1985 article 44 disponibilité sur demande convenances personnelles fonctionnaires de l'État",
            ),
            "FPH": (
                "décret n° 88-976 du 13 octobre 1988 article 31 disponibilité sur demande convenances personnelles fonctionnaires hospitaliers",
            ),
        }
        queries.extend(branch_availability_articles.get(public_service, ()))

    ordinary_sick_leave = any(marker in folded for marker in (
        "congé de maladie ordinaire", "conge de maladie ordinaire",
        "maladie ordinaire", "jour de carence", "jours de carence", "cmo",
    ))
    if public_service == "FPT" and ordinary_sick_leave:
        queries.extend([
            "décret n° 87-602 du 30 juillet 1987 articles 14 et 15 congé de maladie fonctionnaires territoriaux",
            "loi n° 2017-1837 du 30 décembre 2017 article 115 jour de carence agents publics",
        ])

    citis = any(marker in folded for marker in (
        "citis", "invalidité temporaire imputable au service",
        "invalidite temporaire imputable au service",
    )) or any(marker in folded for marker in (
        "accident de service", "accident de trajet", "maladie professionnelle",
    ))
    therapeutic_part_time = any(marker in folded for marker in (
        "temps partiel thérapeutique", "temps partiel therapeutique",
        "temps partiel pour raison thérapeutique",
        "temps partiel pour raison therapeutique", "tpt",
    ))

    # Target the current implementing decrees for the selected branch. These
    # searches are deliberately disjoint: FPE and FPH must never inherit FPT
    # decrees, and a cross-versant title remains subject to the scope guard.
    if public_service == "FPE":
        if citis:
            queries.extend([
                "décret n° 86-442 du 14 mars 1986 titre VI bis articles 47-1 à 47-20 congé pour invalidité temporaire imputable au service fonctionnaires de l'État",
                "décret n° 2026-705 du 29 juillet 2026 et décret n° 86-442 articles 47-1 à 47-20 CITIS fonction publique de l'État",
            ])
        if therapeutic_part_time:
            queries.extend([
                "décret n° 86-442 du 14 mars 1986 titre II bis articles 23-1 à 23-14 temps partiel pour raison thérapeutique fonctionnaires de l'État",
                "décret n° 2026-705 du 29 juillet 2026 et décret n° 86-442 articles 23-1 à 23-14 temps partiel thérapeutique fonction publique de l'État",
            ])
    elif public_service == "FPH":
        if citis:
            queries.extend([
                "décret n° 88-386 du 19 avril 1988 articles 35-2 et 35-3 déclaration accident de service maladie professionnelle CITIS fonctionnaires hospitaliers",
                "décret n° 2026-705 du 29 juillet 2026 et décret n° 88-386 titre IV CITIS fonction publique hospitalière",
            ])
        if therapeutic_part_time:
            queries.extend([
                "décret n° 88-386 du 19 avril 1988 titre II bis articles 13-1 à 13-14 temps partiel pour raison thérapeutique fonctionnaires hospitaliers",
                "décret n° 2026-705 du 29 juillet 2026 et décret n° 88-386 articles 13-1 à 13-14 temps partiel thérapeutique fonction publique hospitalière",
            ])

    # The following implementing texts are specific to the territorial
    # health/absence regimes and must never be sent as FPE/FPH requirements.
    if public_service != "FPT":
        return list(dict.fromkeys(queries))

    # Target the FPT overtime framework explicitly. These searches complement,
    # rather than replace, the user's wording and the ordinary research axes.
    # The 2002-60 decree is retrieved as the reference IHTS regime; its FPT
    # application must still be assessed together with the territorial texts
    # and the local deliberation. Never inject these FPT queries into FPE/FPH.
    overtime = any(marker in folded for marker in (
        "heures supplémentaires", "heures supplementaires",
        "heures sup", "heures en plus",
        "travaux supplémentaires", "travaux supplementaires",
        "temps de travail effectif au-delà", "temps de travail effectif au-dela",
        "dépasser les horaires", "depasser les horaires",
        "ihts", "repos compensateur", "récupérer", "recuperer",
        "récupération", "recuperation",
    ))
    if overtime:
        queries.extend([
            "décret n° 2000-815 du 25 août 2000 articles 3 et 4 durée du travail cycles de travail heures supplémentaires fonction publique",
            "décret n° 2001-623 du 12 juillet 2001 articles 1 et 4 cycles de travail fonction publique territoriale délibération comité social territorial",
            "décret n° 2002-60 du 14 janvier 2002 articles 3 4 5 6 7 8 et 9 repos compensateur définition heures supplémentaires exclusivité contingent calcul majorations nuit dimanche astreintes IHTS",
            "décret n° 91-875 du 6 septembre 1991 article 2 liste des emplois ouvrant droit aux IHTS délibération organe délibérant fonction publique territoriale",
        ])

        # Some territorial medico-social/medico-technical cadres follow a
        # specific equivalence route and a 20-hour monthly ceiling. Do not
        # generalize this exception to the whole social/health sector: retrieve
        # the exact territorial equivalences and hospital-reference texts.
        medico_social_ihts = any(marker in folded for marker in (
            "filière médico-sociale", "filiere medico-sociale",
            "filière médico-technique", "filiere medico-technique",
            "cadre de santé", "cadre de sante",
            "cadre territorial de santé", "cadre territorial de sante",
            "cadres territoriaux de santé", "cadres territoriaux de sante",
            "cadre de santé paramédical", "cadre de sante paramedical",
            "technicien paramédical", "technicien paramedical",
            "sage-femme", "sage femme", "puéricultrice", "puericultrice",
            "auxiliaire de puériculture", "auxiliaire de puericulture",
            "masseur-kinésithérapeute", "masseur-kinesitherapeute",
            "orthophoniste", "ergothérapeute", "ergotherapeute",
            "psychomotricien", "20 heures", "20h",
        ))
        if medico_social_ihts:
            queries.extend([
                "décret n° 91-875 du 6 septembre 1991 annexes 1 et 2 fonctions médico-sociales cadres d'emplois territoriaux corps de référence IHTS",
                "décret n° 98-1057 du 16 novembre 1998 article 1 régime indemnitaire personnels paramédicaux civils ministère de la défense",
                "décret n° 2002-598 du 25 avril 2002 articles 6 7 et 8 contingent 20 heures IHTS équivalence fonction publique territoriale",
                "arrêté du 25 avril 2002 liste des corps grades emplois éligibles IHTS article 1",
            ])

    if citis:
        queries.extend([
            "décret n° 87-602 articles 37-1 37-2 37-5 37-9 37-9-1 37-20 CITIS accident de service déclaration imputabilité instruction",
            "décret n° 2026-705 article 3 modifie articles 37-2 et 37-9-1 CITIS fonction publique territoriale déclaration accident maladie professionnelle",
        ])
    if therapeutic_part_time:
        queries.extend([
            "décret n° 87-602 articles 13-1 13-2 13-3 13-5 13-7 13-9 13-11 13-13 temps partiel pour raison thérapeutique fonctionnaire territorial",
            "décret n° 2026-705 article 3 modifie articles 13-2 et 13-5 temps partiel pour raison thérapeutique fonctionnaire territorial",
            "décret n° 88-145 article 9-1 temps partiel pour raison thérapeutique agent contractuel territorial",
            "décret n° 2026-705 article 6 temps partiel pour raison thérapeutique agent contractuel territorial décret 88-145",
        ])
    return list(dict.fromkeys(queries))


def _cgfp_article_discovery_queries(found: dict | None, target_versant: str = "FPT") -> list[str]:
    """Turn relevant, selected-branch snapshot hits into exact live CGFP lookups."""
    if not isinstance(found, dict):
        return []
    queries: list[str] = []
    seen: set[str] = set()
    for hit in found.get("results", []):
        article_ref = re.sub(r"\s+", "", str(hit.get("article") or "")).upper()
        if not re.fullmatch(r"[LDR]\d+(?:-\d+)*", article_ref) or article_ref in seen:
            continue
        eligible = (
            _cgfp_article_fpt_eligible(article_ref)
            if target_versant == "FPT"
            else _cgfp_article_fpt_eligible(article_ref, target_versant)
        )
        if not eligible:
            continue
        if not (
            hit.get("matched_concepts")
            or hit.get("relevance_label") in {
                "Correspondance lexicale à confirmer",
                "Correspondance lexicale — pertinence à vérifier",
            }
        ):
            continue
        queries.append(f"article {article_ref}")
        seen.add(article_ref)
        if len(queries) >= 6:
            break
    return queries


def should_use_cgfp_snapshot_fallback(
    live_issue: str | None,
    found: dict | None,
    research_queries: list[str] | str,
    target_versant: str = "FPT",
    live_sources: list[dict] | None = None,
) -> bool:
    """Use the dated snapshot when live CGFP search failed or yielded no relevant article."""
    queries = research_queries if isinstance(research_queries, list) else [research_queries]
    # Regulatory decrees may complement the CGFP but do not replace a failed
    # live CGFP article lookup. Only a relevant live code article suppresses
    # the documentary CGFP snapshot fallback.
    live_covers_an_axis = any(
        source.get("source_type") in {None, "LEGIFRANCE_API"}
        and _source_relevant_for_target(queries, source, target_versant)
        and source.get("analysis_eligible") is not False
        for source in (live_sources or [])
    )
    # Use the dated snapshot as a discovery/context fallback whenever live
    # retrieval failed OR returned no relevant CGFP article for the requested
    # axis. Its scope and claim-eligibility guards still prevent it from
    # grounding a current legal assertion.
    live_unusable = bool(live_issue) or not live_covers_an_axis
    return bool(
        live_unusable and isinstance(found, dict) and found.get("results")
        and any(
            _source_relevant_for_target(queries, hit, target_versant)
            and (
                _cgfp_article_fpt_eligible(str(hit.get("article") or ""))
                if target_versant == "FPT"
                else _cgfp_article_fpt_eligible(str(hit.get("article") or ""), target_versant)
            )
            for hit in found["results"]
        )
    )


case_law_connector = AdministrativeCaseLawConnector(legifrance)
logger = logging.getLogger(__name__)

# The corpus is filtered for topic, source authority and public-service scope
# after retrieval. Overfetch per axis so the first six lexical/vector hits do
# not crowd out relevant documents before those deterministic guards run.
LEGAL_CORPUS_CANDIDATE_LIMIT = 12
LEGAL_CORPUS_INTERLEAVED_LIMIT = 18


def _should_search_local_employer_documents(public_service: str, employer: str) -> bool:
    """Local employer acts currently belong only to the supported FPT employers."""
    return (
        str(public_service or "").upper() == "FPT"
        and str(employer or "").upper() in {"VILLE_SAINT_ETIENNE", "SAINT_ETIENNE_METROPOLE"}
    )


def _effective_employer_for_versant(public_service: str, employer: str) -> str:
    """Do not pass an FPT-only employer selector as the legal employer in FPE/FPH."""
    return str(employer or "NATIONAL") if str(public_service or "").upper() == "FPT" else "NATIONAL"


def _france_today() -> date:
    return datetime.now(ZoneInfo("Europe/Paris")).date()


def _case_law_reference_date(
    period_start: date | None,
    period_end: date | None,
    situation_ongoing: bool,
    today: date,
) -> date | None:
    """Use today for continuing situations; otherwise use the known facts date."""
    if situation_ongoing and period_start:
        return today
    return period_end or period_start


def _local_document_reference_dates(
    period_start: date | None,
    period_end: date | None,
    today: date,
) -> list[tuple[date, str]]:
    """Check local acts at the facts-period endpoints and against today's rules."""
    roles: dict[date, str] = {}
    if period_start:
        roles[period_start] = "START"
    if period_end:
        roles[period_end] = "END"
    roles.setdefault(today, "CURRENT")
    return sorted(roles.items())


def _analysis_mode(question_intent: str, facts_date_provided: bool) -> str:
    if facts_date_provided:
        return "CASE_SPECIFIC"
    if question_intent == "PERSONAL_CASE":
        return "PERSONAL_CASE_WITHOUT_FACTS_DATE"
    return "GENERAL_CURRENT_LAW_WITHOUT_FACTS_DATE"


def _permanent_source_temporal_metadata(
    item: dict, facts_reference_date: date | None,
) -> tuple[str | None, str | None]:
    status = item.get("temporal_status")
    explanation = None
    document_kind = str(item.get("document_kind") or "").upper()
    if document_kind == "ADMIN_CASELAW":
        raw_date = item.get("signature_date")
        if status == "DECISION_POSTERIOR_TO_REQUESTED_DATE":
            return (
                "DECISION_AFTER_RETRIEVAL_DATE",
                "Date de décision postérieure à la date de recherche : source écartée en attendant une vérification.",
            )
        status = decision_temporal_status(
            str(raw_date) if raw_date else None, facts_reference_date,
        )
        if status == "DECISION_POSTERIOR_TO_FACTS":
            explanation = (
                "Décision postérieure aux faits : elle peut éclairer l'interprétation du droit antérieur, "
                "mais ne prouve pas à elle seule la règle applicable à la date des faits."
            )
        elif status == "DECISION_DATE_UNKNOWN":
            explanation = (
                "Date de décision non vérifiée : ne pas lui attribuer de portée temporelle certaine."
            )
    elif facts_reference_date and document_kind in {
        "CODE", "LAW", "ORDONNANCE", "DECREE", "ORDER",
    }:
        raw_requested_date = item.get("requested_date")
        try:
            retrieved_for_date = (
                raw_requested_date
                if isinstance(raw_requested_date, date)
                else date.fromisoformat(str(raw_requested_date)[:10])
            )
        except (TypeError, ValueError):
            retrieved_for_date = None
        if retrieved_for_date != facts_reference_date:
            valid_from = item.get("valid_from")
            valid_to = item.get("valid_to")
            try:
                valid_from = (
                    valid_from if isinstance(valid_from, date)
                    else date.fromisoformat(str(valid_from)[:10]) if valid_from else None
                )
                valid_to = (
                    valid_to if isinstance(valid_to, date)
                    else date.fromisoformat(str(valid_to)[:10]) if valid_to else None
                )
            except (TypeError, ValueError):
                valid_from = valid_to = None
            if valid_from and facts_reference_date < valid_from:
                status = "NOT_YET_EFFECTIVE"
                explanation = (
                    f"Cette version n'était pas encore applicable au {facts_reference_date.isoformat()}."
                )
            elif valid_to and facts_reference_date > valid_to:
                status = "NO_LONGER_IN_FORCE"
                explanation = (
                    f"La période de validité enregistrée pour cette version était terminée au {facts_reference_date.isoformat()}."
                )
            elif valid_from and valid_to:
                status = "IN_FORCE_ON_FACTS_DATE"
                explanation = (
                    f"Les bornes de validité enregistrées pour cette version couvrent le {facts_reference_date.isoformat()}."
                )
            else:
                status = "TEMPORAL_SCOPE_INCOMPLETE"
                explanation = (
                    "Les bornes de validité de cette version ne permettent pas de vérifier son applicabilité à la date des faits."
                )
    return status, explanation


def _classify_permanent_source_scope(source: dict, target_versant: str) -> dict:
    """Reuse ingestion-time scope for verified Open Data decisions.

    Administrative decisions are classified against their complete XML text at
    ingestion. Reclassifying only a retrieved passage can lose the branch marker
    and silently discard an otherwise qualified decision. Trust that stored
    result only for the exact official XML ingestion path and verified status.
    """
    metadata = source.get("raw_metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    stored_scope = str(metadata.get("public_service_scope") or "").upper()
    trusted_open_data_case = (
        source.get("source_type") == "OTHER_OFFICIAL"
        and source.get("document_kind") == "ADMIN_CASELAW"
        and source.get("source_status") == "OFFICIAL_XML_IMPORTED"
        and metadata.get("import_method") == "JUSTICE_ADMINISTRATIVE_OPEN_DATA_XML"
        and stored_scope in {"FPT", "FPE", "FPH", "COMMON_PUBLIC_SERVICE"}
    )
    if trusted_open_data_case:
        applicable = stored_scope == "COMMON_PUBLIC_SERVICE" or stored_scope == target_versant
        evidence = metadata.get("scope_evidence")
        return {
            "scope": stored_scope,
            "evidence": evidence if isinstance(evidence, list) else [],
            "analysis_eligible": applicable,
            "claim_eligible": applicable,
        }
    return classify_public_service_scope(source, target_versant=target_versant)


def _is_usable_permanent_source(source: dict, permanent_source_ids: set) -> bool:
    """Apply the final corpus-source eligibility gate, including historical versions."""
    if (
        source.get("source_id") not in permanent_source_ids
        or source.get("content_kind") != "FULL_TEXT"
        or not _citation_is_valid(source)
        or source.get("analysis_eligible") is not True
        or source.get("claim_eligible", True) is False
        or source.get("research_axis_relevant", True) is False
    ):
        return False
    temporal_status = source.get("temporal_status")
    if temporal_status in {
        "IN_FORCE_ON_REQUESTED_DATE",
        "IN_FORCE_ON_FACTS_DATE",
        "DECISION_AVAILABLE_BY_REQUESTED_DATE",
        "DECISION_ANTERIOR_OR_CONTEMPORANEOUS_TO_FACTS",
        "DECISION_DATE_VERIFIED_NO_FACTS_DATE",
    }:
        return True
    return (
        temporal_status == "TEMPORAL_SCOPE_INCOMPLETE"
        and source.get("general_info_eligible") is True
        and source.get("version_status") not in {"REPEALED", "NOT_IN_FORCE"}
    )


def classify_question_intent(question: str) -> str:
    """Classify whether the current turn describes an individual event or asks for general rules.

    This is a conservative routing heuristic, not a legal or semantic judgement.
    It distinguishes an individual situation from a general question; it does
    not make the facts date mandatory. Hypothetical employer powers remain general.
    """
    text = " ".join(str(question or "").casefold().split())
    if not text:
        return "GENERAL_INFORMATION"

    personal_event_patterns = (
        r"\bon ne me (?:paie|paye|compense|donne)\b",
        r"\bon m['’]a (?:refusé|sanctionné|notifié|imposé|retiré|placé|licencié|convoqué)\b",
        r"\bje (?:n['’]ai pas (?:été payé|reçu|touché|obtenu)|ne suis pas payé|ne touche pas|subis)\b",
        # A named hierarchical colleague may be the person who conducted the
        # individual evaluation; this remains a personal case even without its date.
        r"\bmon\s+(?:agent|responsable|chef|supérieur hiérarchique|superieur hierarchique)\b.{0,100}\bm['’]a(?:s)? fait\b.{0,100}\b(?:évaluation|evaluation|entretien professionnel|compte rendu)\b",
        r"\bj['’]ai (?:été sanctionné|été licencié|été convoqué|été refusé|reçu|déposé|contesté|effectué)\b",
        r"\b(?:mon employeur|ma collectivité) (?:refuse|ne me paie|ne me paye|m['’]a refusé|m['’]a sanctionné|a refusé|a rejeté)\b.{0,100}\b(?:ma demande|mon congé|ma rémunération|ma protection fonctionnelle|mon recours)\b",
        r"\b(?:mon employeur|ma collectivité) refuse de me (?:payer|verser|compenser)\b",
        r"\b(?:mon|ma|mes)\s+[\wÀ-ÿ'’-]{2,40}\s+(?:a été|ont été)\s+(?:refusé|refusée|refusés|refusées|retiré|retirée|supprimé|supprimée|notifié|notifiée|rejeté|rejetée|suspendu|suspendue)\b",
        r"\b(?:ma demande|mon congé|mon arrêt|ma rémunération|mon dossier)\b.{0,80}\b(?:refusé|refusée|refusés|refusées|rejeté|rejetée|suspendu|suspendue)\b",
        r"\b(?:j['’]ai reçu|on m['’]a notifié|on m['’]a adressé)\b.{0,80}\b(?:refus|décision|sanction|notification|convocation)\b",
        r"\b(?:dans mon cas|dans ma situation|concernant mon dossier)\b",
        # Union representatives often describe a member's case in the third person.
        r"\b(?:un|une|l['’])\s*agent(?:e)?\b.{0,100}\b(?:a eu|a reçu|a subi|a été|fait l['’]objet|s['’]est vu|subit|rencontre)\b",
        r"\b(?:un|une|l['’])\s*agent(?:e)?\b.{0,100}\b(?:sa demande|son congé|sa rémunération|sa protection fonctionnelle)\b.{0,50}\b(?:refusé|refusée|rejeté|rejetée|suspendu|suspendue)\b",
    )
    if any(re.search(pattern, text) for pattern in personal_event_patterns):
        return "PERSONAL_CASE"

    # Generic rights framing must not hide an actual individual event described
    # in the same message. Personal-event evidence takes precedence over
    # hypothetical/general wording.
    general_hypothetical_patterns = (
        r"^(?:quels sont|quels seraient|comment connaitre|comment connaître)\s+mes droits\b",
        r"\bsi\s+(?:mon employeur|ma collectivité|un employeur)\s+(?:refuse|rejette|sanctionne|impose)\b",
        r"\b(?:peut-il|peut-elle|est-il possible|dans quels cas)\b",
    )
    if any(re.search(pattern, text) for pattern in general_hypothetical_patterns):
        return "GENERAL_INFORMATION"

    # A question about what an employer may generally do is not evidence that
    # the user has personally received a refusal or decision.
    return "GENERAL_INFORMATION"


def question_needs_case_date(question: str) -> bool:
    """Compatibility wrapper: identify a personal case without requiring its date."""
    return classify_question_intent(question) == "PERSONAL_CASE"

def filter_irrelevant_sources_for_display(sources: list[dict]) -> list[dict]:
    """Exclude sources explicitly unrelated to every independently searched axis."""
    return [
        source for source in sources
        if source.get(
            "research_axis_relevant",
            source.get("ihts_relevant") is not False and source.get("topic_relevant") is not False,
        )
    ]



async def apply_semantic_source_relevance(
    *, question: str, research_axes: list[str], sources: list[dict],
    target_versant: str = "FPT", allow_local_documents: bool = False,
    usage_events: list[dict] | None = None,
) -> None:
    """Apply Gemini relevance verdicts while preserving lexical fallback on provider failure."""
    for source in sources:
        source["research_axis_relevant"] = _source_relevant_for_target(
            research_axes, source, target_versant,
        )
    try:
        semantic_sources = [
            source for source in sources
            if allow_local_documents or source.get("source_type") not in {
                "LOCAL_DOCUMENT", "LOCAL_COLLECTIVITY_DOCUMENT",
            }
        ]
        semantic_verdicts = await evaluate_source_relevance(
            question=question,
            research_axes=research_axes,
            sources=semantic_sources,
            **_provider_usage_kwargs(evaluate_source_relevance, usage_events if usage_events is not None else []),
        )
        for source in sources:
            verdict = semantic_verdicts.get(source.get("source_id"))
            if verdict in {"DIRECT", "CONTEXTUAL"}:
                source["research_axis_relevant"] = True
                source["semantic_relevance"] = verdict
            elif verdict == "UNCERTAIN":
                # Uncertainty is not positive relevance evidence: keep the lexical result.
                source["semantic_relevance"] = verdict
            elif verdict == "IRRELEVANT":
                source["research_axis_relevant"] = False
                source["semantic_relevance"] = verdict
    except AIProviderUnavailable as exc:
        # The semantic pass is optional; retain the deterministic lexical assessment.
        logger.warning("Semantic source relevance unavailable; using lexical fallback: %s", exc)


def _source_relevant_to_any_research_axis(
    research_queries: list[str], source: dict, target_versant: str = "FPT",
) -> bool:
    """Require topic relevance while applying FPT-only safeguards to FPT questions."""
    return any(
        is_topic_relevant_source(query, source, target_versant=target_versant)
        and is_ihts_relevant_source(query, source, target_versant=target_versant)
        for query in research_queries
    )


def _source_relevant_for_target(
    research_queries: list[str], source: dict, target_versant: str,
) -> bool:
    # Keep the historical two-argument FPT call contract for existing adapters
    # and tests; FPE/FPH must not inherit FPT-specific retrieval guards.
    if str(target_versant or "FPT").upper() == "FPT":
        return _source_relevant_to_any_research_axis(research_queries, source)
    return _source_relevant_to_any_research_axis(
        research_queries, source, target_versant,
    )


def _tag_official_versions(items: list[dict], requested_date: date, endpoint: str) -> list[dict]:
    """Give each dated API result a unique citation key while retaining its official ID."""
    tagged = []
    for item in items:
        source = dict(item)
        official_id = source.get("source_id")
        if not isinstance(official_id, str) or not official_id:
            continue
        source["official_source_id"] = official_id
        source["source_version_id"] = source.get("source_version_id") or official_id
        source["source_id"] = f"{official_id}_V{requested_date:%Y%m%d}"
        source["requested_effective_date"] = requested_date.isoformat()
        source["version_endpoint"] = endpoint
        source["version_key"] = f"{official_id}:{requested_date.isoformat()}"
        tagged.append(source)
    return tagged


def _source_covers_period(source: dict, start_date: date, end_date: date) -> bool:
    """Require explicit validity metadata spanning the whole declared facts period."""
    try:
        valid_from = date.fromisoformat(str(source.get("valid_from") or source.get("effective_from"))[:10])
    except (TypeError, ValueError):
        return False
    raw_valid_to = source.get("valid_to") or source.get("effective_to")
    # A NULL end date may mean "unknown" rather than "still in force".
    # Without an explicit upper bound, do not certify whole-period coverage.
    if not raw_valid_to:
        return False
    try:
        valid_to = date.fromisoformat(str(raw_valid_to)[:10])
    except (TypeError, ValueError):
        return False
    return valid_from <= start_date and valid_to >= end_date


def _source_allowed_for_period_analysis(
    source: dict,
    period_comparison: bool,
    period_start: date | None,
    period_end: date,
) -> bool:
    """Keep dated legal evidence in period analyses without demanding case law cover the facts period."""
    if not period_comparison:
        return True
    source_type = source.get("source_type")
    if source_type in {"LEGIFRANCE_API", "LEGIFRANCE_LODA"}:
        return source.get("period_endpoint_match") is True
    temporal_status = source.get("temporal_status")
    if (
        source_type == "LEGIFRANCE_CETAT_FULL_TEXT"
        or source.get("document_kind") == "ADMIN_CASELAW"
    ):
        return (
            source.get("content_kind") == "FULL_TEXT"
            and temporal_status in {
                "DECISION_ANTERIOR_OR_CONTEMPORANEOUS_TO_FACTS",
                "DECISION_POSTERIOR_TO_FACTS",
                "DECISION_DATE_VERIFIED_NO_FACTS_DATE",
            }
        )
    if source_type in {"LOCAL_DOCUMENT", "LOCAL_COLLECTIVITY_DOCUMENT"}:
        return (
            source.get("validation_status") in {"VERIFIED_APPLICABLE", "VERIFIED_HISTORICAL"}
            and temporal_status == "VERIFIED_APPLICABLE"
            and source.get("version_endpoint") in {"START", "END", "CURRENT"}
        )
    return bool(period_start and _source_covers_period(source, period_start, period_end))


def _compare_official_period_versions(
    code_sources: list[dict], regulatory_sources: list[dict],
    start_date: date, end_date: date,
) -> dict:
    """Compare the retrieved official texts at period endpoints without inferring missing law."""
    grouped: dict[tuple[str, str], dict[str, dict]] = {}
    for source in [*code_sources, *regulatory_sources]:
        endpoint = source.get("version_endpoint")
        if endpoint not in {"START", "END"}:
            continue
        source_type = str(source.get("source_type") or "")
        if source_type == "LEGIFRANCE_API":
            canonical = str(source.get("article") or source.get("official_source_id") or source.get("source_version_id") or "")
        else:
            # A number alone is not a unique instrument identity across legal
            # document families (law, decree, order). Prefer the document kind
            # together with the official number; fall back to the stable LEGITEXT ID.
            document_kind = str(source.get("document_kind") or "UNKNOWN").upper()
            official_number = str(source.get("official_number") or "")
            canonical = (
                f"{document_kind}:{official_number}" if official_number
                else f"{document_kind}:{source.get('official_source_id') or source.get('source_version_id') or ''}"
            )
        if not canonical:
            continue
        grouped.setdefault((source_type, canonical), {})[endpoint] = source

    changed = unchanged = start_only = end_only = 0
    details = []
    for (source_type, canonical), versions in grouped.items():
        start_source, end_source = versions.get("START"), versions.get("END")
        if start_source and end_source:
            start_text = " ".join(str(start_source.get("text") or start_source.get("full_text") or start_source.get("excerpt") or "").split())
            end_text = " ".join(str(end_source.get("text") or end_source.get("full_text") or end_source.get("excerpt") or "").split())
            status = "DIFFERENT_TEXT_AT_ENDPOINTS" if start_text != end_text else "SAME_TEXT_AT_ENDPOINTS"
            if status == "DIFFERENT_TEXT_AT_ENDPOINTS":
                changed += 1
            else:
                unchanged += 1
        elif start_source:
            status = "FOUND_ONLY_IN_START_SEARCH"
            start_only += 1
        else:
            status = "FOUND_ONLY_IN_END_SEARCH"
            end_only += 1
        details.append({
            "source_type": source_type, "canonical_reference": canonical,
            "comparison": status,
            "start_source_id": start_source.get("source_id") if start_source else None,
            "end_source_id": end_source.get("source_id") if end_source else None,
        })
    matched_source_ids = [
        source_id
        for item in details if item.get("start_source_id") and item.get("end_source_id")
        for source_id in (item["start_source_id"], item["end_source_id"])
    ]
    return {
        "status": "ENDPOINTS_COMPARED_NOT_COMPLETE_HISTORY",
        "start_date": start_date.isoformat(), "end_date": end_date.isoformat(),
        "changed_text_count": changed, "same_text_count": unchanged,
        "start_only_search_count": start_only, "end_only_search_count": end_only,
        "matched_source_ids": matched_source_ids,
        "results": details[:30],
        "limitation": (
            "Comparaison des résultats Légifrance retrouvés aux deux bornes uniquement. "
            "Un résultat absent à une borne ne prouve pas l'abrogation ou l'inapplicabilité. "
            "Les modifications intermédiaires et dates d'effet de chaque version doivent être vérifiées."
        ),
    }



def _provider_usage_kwargs(provider_function, events: list[dict]) -> dict:
    """Keep test doubles and alternate provider adapters compatible with optional telemetry."""
    try:
        parameters = inspect.signature(provider_function).parameters.values()
        supported = any(p.name == "usage_events" or p.kind == inspect.Parameter.VAR_KEYWORD for p in parameters)
    except (TypeError, ValueError):
        supported = False
    return {"usage_events": events} if supported else {}


def _immediate_prior_assistant_messages(history: list[dict]) -> list[str]:
    """Only the immediately preceding turn may answer a clarification prompt."""
    if not history or not isinstance(history[-1], dict):
        return []
    latest = history[-1]
    if latest.get("role") != "assistant":
        return []
    content = str(latest.get("content") or "").strip()
    return [content[:1200]] if content else []


def _provider_context_history(
    contextual_question: str,
    is_followup: bool,
    assistant_context: str | None = None,
) -> list[dict]:
    """Pass only the resolved prior user turn and, when needed, a non-source assistant referent."""
    if not is_followup:
        return []
    normalized_question = str(contextual_question or "").replace("\\n", "\n")
    parts = normalized_question.split("\n", 1)
    if len(parts) < 2:
        return []
    prior_question = parts[1].split("\n", 1)[0].strip()
    if not prior_question:
        return []
    history = [{"role": "user", "content": prior_question[:1200]}]
    if isinstance(assistant_context, str) and assistant_context.strip():
        history.append({
            "role": "assistant",
            "content": assistant_context.strip()[-1800:],
        })
    return history


class LegalOrchestrator:
    async def ask(self, request: AskRequest, organization_id: str, conn=None, conversation_history: list[dict] | None = None, allow_local_documents: bool = False, personal_user_id: str | None = None) -> AskResponse:
        request_id = str(uuid4())
        ai_usage_events: list[dict] = []
        answer_started_at = None
        try:
            legacy_date = parse_facts_date(request.facts_date)
            period_start = parse_facts_date(request.facts_start_date) or legacy_date
            period_end = parse_facts_date(request.facts_end_date)
            if legacy_date and not request.facts_start_date and not request.facts_end_date:
                # Compatibility: the former single-date field describes one exact day.
                period_end = legacy_date
            if request.situation_ongoing and period_end:
                raise ValueError("Une situation déclarée toujours en cours ne peut pas avoir de date de fin.")
            if request.situation_ongoing and not period_start:
                raise ValueError("Indiquez la date de début de la situation, même si elle est toujours en cours.")
            if period_start and period_end and period_end < period_start:
                raise ValueError("La fin de la période ne peut pas précéder son début.")
            # Always retrieve current law and case law. The facts date is an
            # additional applicability checkpoint, never a research cut-off.
            effective_date = _france_today()
            question_intent = classify_question_intent(request.question)
            # For an ongoing situation, case law is assessed through today:
            # decisions issued after its start may still govern its continuing
            # effects. Keep the declared start date separately for historical
            # statutory-version lookup and provenance.
            parsed_date = period_end or period_start
            facts_reference_date = _case_law_reference_date(
                period_start, period_end, bool(request.situation_ongoing), effective_date,
            )
            temporal_context = {
                "period_start": period_start.isoformat() if period_start else None,
                "period_end": period_end.isoformat() if period_end else None,
                "facts_reference_date": facts_reference_date.isoformat() if facts_reference_date else None,
                "ongoing": bool(request.situation_ongoing),
                "facts_date_provided": parsed_date is not None,
                "analysis_mode": _analysis_mode(question_intent, parsed_date is not None),
                "question_intent": question_intent,
                "reference_date_for_retrieval": effective_date.isoformat(),
                "legacy_exact_date": bool(legacy_date and not request.facts_start_date and not request.facts_end_date),
            }
        except ValueError as exc:
            return AskResponse(request_id=request_id, verification_status="NON_VERIFIE",
                answer="La période de la situation n'a pas pu être interprétée. Aucune analyse juridique n'est produite.",
                missing_information=[str(exc)])

        history = (conversation_history or [])[-CONVERSATION_HISTORY_MESSAGE_LIMIT:]
        prior_user_questions = [str(m.get("content", ""))[:1200] for m in history if m.get("role") == "user"]
        current_question = request.question.strip()
        prior_assistant_messages = _immediate_prior_assistant_messages(history)
        contextual_research_context = build_contextual_research_context(
            current_question, prior_user_questions, prior_assistant_messages,
        )
        contextual_question = contextual_research_context.question
        is_followup = contextual_research_context.is_followup
        provider_history = _provider_context_history(
            contextual_question, is_followup,
            assistant_context=contextual_research_context.assistant_context,
        )
        targeted_clarification = clarification_for_union_assistance_summons(contextual_question)
        if targeted_clarification:
            return AskResponse(
                request_id=request_id,
                verification_status="NON_VERIFIE",
                answer=targeted_clarification,
                clarification_question=targeted_clarification,
                sources=[],
                missing_information=[],
            )
        # A genuine short follow-up inherits the immediate prior referent and,
        # where relevant, the personal-case classification. Independent new
        # questions never inherit unrelated topics or facts.
        if is_followup and prior_user_questions:
            inherited_question = contextual_question.split("\n", 1)[1]
            if question_intent != "PERSONAL_CASE" and classify_question_intent(inherited_question) == "PERSONAL_CASE":
                question_intent = "PERSONAL_CASE"
                temporal_context["question_intent"] = question_intent
                temporal_context["analysis_mode"] = _analysis_mode(
                    question_intent, parsed_date is not None,
                )
        # Qualification must use the resolved referent so follow-ups such as
        # "Et pour les contractuels ?" retain the original legal topic.
        legal_context = qualify_legal_question(contextual_question, _effective_employer_for_versant(request.public_service, request.employer), request.public_service)
        legal_context["versant_fonction_publique"] = request.public_service
        mismatch_versant = legal_context.get("explicit_self_versant_mismatch")
        if mismatch_versant:
            labels = {
                "FPT": "fonction publique territoriale",
                "FPE": "fonction publique de l'État",
                "FPH": "fonction publique hospitalière",
            }
            clarification = (
                f"Cette conversation est configurée pour la {labels[request.public_service]}, "
                f"mais vous indiquez relever de la {labels[mismatch_versant]}. "
                "Pour éviter de vous présenter des règles d'un autre versant, démarrez "
                "une nouvelle conversation et sélectionnez le versant correspondant."
            )
            return AskResponse(
                request_id=request_id,
                verification_status="NON_VERIFIE",
                answer=clarification,
                clarification_question=clarification,
                sources=[],
                missing_information=[],
            )
        # Gemini plans the research from the actual facts before any legal source
        # is retrieved. Its output contains search language only, never legal evidence.
        # Deterministic topic templates remain a resilience fallback when the model
        # is not configured or temporarily unavailable.
        fallback_queries, fallback_axes = _build_versant_fallback_research(
            contextual_question, request.public_service,
        )
        research_plan = None
        try:
            research_plan = await plan_legal_research(
                question=contextual_question,
                employer=_effective_employer_for_versant(request.public_service, request.employer),
                facts_period=temporal_context,
                legal_context=legal_context,
                conversation_history=provider_history,
                **_provider_usage_kwargs(plan_legal_research, ai_usage_events),
            )
        except AIProviderUnavailable:
            logger.warning("Planification IA de la recherche juridique indisponible ; utilisation du plan de secours.")
        if research_plan is not None and research_plan.clarification_needed:
            clarification = research_plan.clarification_needed
            logger.info("Clarification juridique demandée avant recherche documentaire (request_id=%s).", request_id)
            return AskResponse(
                request_id=request_id,
                verification_status="NON_VERIFIE",
                answer=clarification,
                clarification_question=clarification,
                sources=[],
                missing_information=[],
                ai_usage_events=ai_usage_events,
            )
        if research_plan is not None:
            research_queries = merge_ai_and_fallback_research_queries(
                research_plan.queries, fallback_queries, fallback_axes, max_queries=5,
            )
            research_axes = select_required_research_axes(fallback_axes)
            legal_context["strategie_recherche"] = "PLANIFIEE_PAR_IA_AVANT_CONSULTATION"
            legal_context["axes_recherche_documentaire"] = research_axes
            legal_context["clarification_recherche"] = research_plan.clarification_needed
            legal_context["faits_extraits_de_la_question"] = research_plan.extracted_facts or []
            legal_context["faits_extraits_statut"] = "CITATIONS_TEXTUELLES_VERIFIEES_CONTRE_QUESTION"
            legal_context["faits_extraits_limite"] = (
                "Ces faits reprennent uniquement des passages explicitement présents dans la question. "
                "Ils ne prouvent pas leur exactitude et ne constituent pas une qualification juridique."
            )
        else:
            research_queries = fallback_queries
            legal_context["strategie_recherche"] = "SECOURS_DETERMINISTE_MODELE_INDISPONIBLE"
            legal_context["axes_recherche_documentaire"] = fallback_axes
        # PISTE search methods cap each query at 500 characters.
        research_queries = [query[:500] for query in research_queries if query.strip()][:5]
        live_sources: list[dict] = []
        regulatory_sources: list[dict] = []
        case_law_sources: list[dict] = []
        case_law_full_text_sources: list[dict] = []
        live_issue = None
        regulatory_issue = None
        case_law_issue = None
        case_law_fulltext_issue = None
        cgfp_issue = None

        async def search_cgfp_index():
            if not settings.cgfp_enabled:
                return None, "Index documentaire CGFP désactivé : le pilier CGFP n'a pas été interrogé."
            # Search the national CGFP discovery index once per recognized
            # sub-question. A single broad query can otherwise let its strongest
            # topic hide articles relevant to the other parts of a compound request.
            results_by_query = []
            for query in research_queries:
                try:
                    results_by_query.append(
                        await asyncio.to_thread(search_cgfp, query, limit=8)
                    )
                except Exception as exc:
                    results_by_query.append(exc)
            merged: dict[str, dict] = {}
            detected_topics: list[str] = []
            failed_queries = []
            source_metadata = None
            for query, result in zip(research_queries, results_by_query):
                if isinstance(result, BaseException) or not isinstance(result, dict):
                    logger.warning("Recherche index CGFP indisponible pour un axe (%s): %r", query[:100], result)
                    failed_queries.append(query)
                    continue
                source_metadata = source_metadata or result.get("source")
                detected_topics.extend(result.get("detected_topics") or [])
                for hit in result.get("results", []):
                    article = re.sub(r"\s+", "", str(hit.get("article") or "")).upper()
                    if not article:
                        continue
                    current = merged.get(article)
                    candidate = dict(hit)
                    if current is None:
                        merged[article] = candidate
                        continue
                    combined_concepts = list(dict.fromkeys([
                        *(current.get("matched_concepts") or []),
                        *(candidate.get("matched_concepts") or []),
                    ]))[:8]
                    if float(candidate.get("score") or 0) > float(current.get("score") or 0):
                        candidate["matched_concepts"] = combined_concepts
                        merged[article] = candidate
                    else:
                        current["matched_concepts"] = combined_concepts
            ranked = sorted(
                merged.values(),
                key=lambda item: (-float(item.get("score") or 0), str(item.get("article") or "")),
            )[:20]
            if failed_queries and len(failed_queries) == len(research_queries):
                return None, "Index documentaire CGFP indisponible pour tous les axes de recherche."
            return {
                "source": source_metadata,
                "results": ranked,
                "detected_topics": list(dict.fromkeys(detected_topics)),
                "queries_executed": len(research_queries) - len(failed_queries),
                "partial_issue": (
                    "La recherche dans l'index CGFP a échoué pour au moins une sous-question ; les autres axes ont été conservés."
                    if failed_queries else None
                ),
            }, None

        async def search_official_pillars(cgfp_article_queries: list[str] | None = None):
            if not legifrance.configured:
                issue = "Identifiants PISTE non configurés : les recherches officielles Légifrance n'ont pas été exécutées."
                return [], [], [], issue, issue, issue, issue, []
            try:
                # Refresh OAuth once before the date-scoped searches to avoid token races.
                await legifrance._get_token()
            except LegifranceUnavailable:
                logger.exception("Authentification PISTE indisponible avant la recherche multi-sources.")
                issue = "Authentification PISTE impossible : les recherches officielles n'ont pas pu être exécutées."
                return [], [], [], issue, issue, issue, issue, []

            date_roles: dict[date, str] = {}
            if period_start:
                date_roles[period_start] = "START"
            if period_end:
                date_roles[period_end] = "END"
            # Always add today's version, even when the user supplied a past date.
            date_roles.setdefault(effective_date, "END" if period_start and not period_end else "CURRENT")
            comparison_dates = sorted(date_roles)
            # The complete local CGFP snapshot is searched as a discovery
            # index. Its strongest article references become exact Légifrance
            # lookups; the snapshot itself never upgrades to verified evidence.
            # Keep every recognized research axis and reserve a bounded
            # additional budget for up to three exact CGFP article lookups.
            # Exact article calls are essential when lexical discovery identifies
            # a provision whose title/body does not repeat the user's wording.
            targeted_cmo_articles = _build_targeted_cgfp_article_queries(
                contextual_question, request.public_service,
            )
            # Reserve the exact statutory CMO articles instead of allowing broad
            # snapshot discovery to consume the bounded CGFP query budget.
            code_query_inputs = research_queries[:3] if targeted_cmo_articles else research_queries
            code_research_queries = _build_code_research_queries(
                code_query_inputs,
                [*targeted_cmo_articles, *(cgfp_article_queries or [])],
                max_queries=8,
            )
            # These targeted, exact-number queries are sent only to the LODA
            # regulatory-text endpoint. They do not consume the CGFP or CETAT
            # query budgets and preserve the applicable FPT implementing texts.
            regulatory_queries = list(dict.fromkeys([
                *research_queries,
                *_build_targeted_regulatory_queries(contextual_question, request.public_service),
            ]))
            # Exact article leads go only to the CGFP article endpoint, never
            # to regulatory-text or administrative case-law search.
            endpoint_results = await asyncio.gather(*[
                asyncio.gather(
                    asyncio.gather(*[
                        legifrance.search_code_articles(query, requested_date)
                        for query in code_research_queries
                    ], return_exceptions=True),
                    asyncio.gather(*[
                        legifrance.search_regulatory_texts(query, requested_date, limit=3)
                        for query in regulatory_queries
                    ], return_exceptions=True),
                )
                for requested_date in comparison_dates
            ])
            code_result, regulatory_result = [], []
            code_failures, regulatory_failures = [], []
            for requested_date, (code_queries_result, regulatory_queries_result) in zip(comparison_dates, endpoint_results):
                endpoint = date_roles[requested_date]
                for query, code_at_date in zip(code_research_queries, code_queries_result):
                    if isinstance(code_at_date, BaseException) or not isinstance(code_at_date, list):
                        logger.warning("Recherche code Légifrance en échec (%s) à %s : %r", query[:100], requested_date, code_at_date)
                        code_failures.append((requested_date.isoformat(), query))
                    else:
                        code_result.extend(_tag_official_versions(code_at_date, requested_date, endpoint))
                for query, regulatory_at_date in zip(regulatory_queries, regulatory_queries_result):
                    if isinstance(regulatory_at_date, BaseException) or not isinstance(regulatory_at_date, list):
                        logger.warning("Recherche réglementaire Légifrance en échec (%s) à %s : %r", query[:100], requested_date, regulatory_at_date)
                        regulatory_failures.append((requested_date.isoformat(), query))
                    else:
                        regulatory_result.extend(_tag_official_versions(regulatory_at_date, requested_date, endpoint))

            # De-duplicate repeated hits returned by overlapping research axes.
            unique_code = {}
            for source in code_result:
                unique_code[source.get("source_id") or str(id(source))] = source
            code_result = list(unique_code.values())

            # Exact-number retrieval may overlap the broad search; keep one
            # canonical source per dated source ID to avoid ambiguous citations.
            unique_regulatory = {}
            for source in regulatory_result:
                unique_regulatory[source.get("source_id") or str(id(source))] = source
            regulatory_result = list(unique_regulatory.values())

            case_results = await asyncio.gather(*[
                case_law_connector.search(query, effective_date)
                for query in research_queries
            ], return_exceptions=True)
            case_results_by_query = []
            case_search_failed = False
            case_search_succeeded = 0
            for query, result in zip(research_queries, case_results):
                if isinstance(result, BaseException) or not isinstance(result, list):
                    logger.warning("Recherche CETAT en échec (%s) : %r", query[:100], result)
                    case_search_failed = True
                    case_results_by_query.append([])
                else:
                    case_search_succeeded += 1
                    case_results_by_query.append(result)
            # Round-robin across the independent research axes: otherwise the
            # first broad query can monopolize the consultation budget and hide
            # decisions found only by a focused sub-question.
            case_result = interleave_case_law_results(case_results_by_query, limit=30)
            code_total = len(comparison_dates) * len(code_research_queries)
            regulatory_total = len(comparison_dates) * len(regulatory_queries)
            code_issue = (
                "La recherche d'articles du CGFP sur Légifrance est indisponible pour tous les axes et dates interrogés."
                if code_failures and len(code_failures) == code_total else None
            )
            regulatory_search_issue = (
                "La recherche des lois, décrets et arrêtés sur Légifrance est indisponible pour tous les axes et dates interrogés."
                if regulatory_failures and len(regulatory_failures) == regulatory_total else None
            )
            search_warnings = []
            if code_failures and code_issue is None:
                search_warnings.append(
                    "La recherche d'articles du CGFP a échoué pour certains axes ou certaines dates ; les résultats obtenus ont été conservés."
                )
            if regulatory_failures and regulatory_search_issue is None:
                search_warnings.append(
                    "La recherche des textes réglementaires a échoué pour certains axes ou certaines dates ; les résultats obtenus ont été conservés."
                )
            case_search_issue = (
                "La recherche de jurisprudence administrative (fonds CETAT) est indisponible pour tous les axes interrogés."
                if case_search_failed and case_search_succeeded == 0 else None
            )
            if case_search_failed and case_search_succeeded:
                search_warnings.append(
                    "La recherche de jurisprudence a échoué pour certaines sous-questions ; les résultats des autres axes ont été conservés."
                )
            elif case_search_issue and not re.search(
                r"jurisprudence|arr[eê]t|d[eé]cision du conseil d['’]etat|tribunal administratif",
                current_question,
                re.IGNORECASE,
            ):
                search_warnings.append(case_search_issue)
                case_search_issue = None
            temporal_issue = None
            if period_start and period_start < (period_end or effective_date) and len(comparison_dates) > 1 and (code_failures or regulatory_failures):
                temporal_issue = (
                    "Comparaison temporelle incomplète : Légifrance n'a pas répondu pour les deux bornes "
                    "de la période. Aucune conclusion couvrant toute la période n'est autorisée."
                )
            return (
                code_result, regulatory_result, case_result,
                code_issue, regulatory_search_issue, case_search_issue, temporal_issue,
                search_warnings,
            )

        # Search the complete bundled CGFP article index for discovery on
        # every request, then verify its best article leads against the live
        # date-scoped Légifrance API. Snapshot text remains unverified and is
        # used as a fallback only when live CGFP retrieval is unavailable.
        found, cgfp_issue = await search_cgfp_index()
        cgfp_partial_issue = found.get("partial_issue") if isinstance(found, dict) else None
        cgfp_article_queries = list(dict.fromkeys([
            *_build_targeted_cgfp_article_queries(contextual_question, request.public_service),
            *_cgfp_article_discovery_queries(found, request.public_service),
        ]))

        # Official legal texts and administrative case law remain the
        # authoritative verification path.
        official_result = await search_official_pillars(cgfp_article_queries)
        (
            live_sources, regulatory_sources, case_law_sources,
            live_issue, regulatory_issue, case_law_issue, temporal_issue, search_warnings,
        ) = official_result

        # One bounded evidence-guided refinement pass: Gemini reviews what the
        # official searches actually returned, identifies uncovered legal issues,
        # and may request a small number of genuinely new searches. It cannot
        # promote a result to evidence; the same official verification path runs again.
        if research_plan is not None:
            first_pass_evidence = [
                *live_sources, *regulatory_sources, *case_law_sources,
                *(
                    [{"source_type": "CGFP_SNAPSHOT", **item}
                     for item in (found or {}).get("results", [])[:8]]
                    if isinstance(found, dict) else []
                ),
            ]
            try:
                refinement = await plan_legal_research(
                    question=contextual_question,
                    employer=_effective_employer_for_versant(request.public_service, request.employer),
                    facts_period=temporal_context,
                    legal_context=legal_context,
                    conversation_history=provider_history,
                    previous_queries=research_queries,
                    retrieved_evidence=first_pass_evidence,
                    **_provider_usage_kwargs(plan_legal_research, ai_usage_events),
                )
            except AIProviderUnavailable:
                refinement = None
                logger.warning("Affinage IA après première recherche indisponible ; les résultats initiaux sont conservés.")
            if refinement is not None:
                additional_queries = [
                    query for query in refinement.queries
                    if query.casefold() not in {existing.casefold() for existing in research_queries}
                ][:2]
                # Model-generated issue labels are advisory only. Mandatory
                # coverage axes remain the deterministic axes derived from the
                # user's question; an LLM refinement cannot invent obligations.
                if additional_queries:
                    research_queries = [*research_queries, *additional_queries][:7]
                    logger.info(
                        "Recherche juridique affinée par IA : %d requête(s) complémentaire(s).",
                        len(additional_queries),
                    )
                    second_found, second_cgfp_issue = await search_cgfp_index()
                    if isinstance(second_found, dict):
                        merged_snapshot = {
                            str(item.get("article") or ""): item
                            for item in (found or {}).get("results", [])
                            if isinstance(item, dict)
                        } if isinstance(found, dict) else {}
                        for item in second_found.get("results", []):
                            if isinstance(item, dict):
                                merged_snapshot[str(item.get("article") or "")] = item
                        found = {**(found or {}), **second_found, "results": list(merged_snapshot.values())}
                        cgfp_issue = None
                    elif not isinstance(found, dict):
                        cgfp_issue = second_cgfp_issue or cgfp_issue
                    cgfp_partial_issue = found.get("partial_issue") if isinstance(found, dict) else cgfp_partial_issue
                    second_article_queries = _cgfp_article_discovery_queries(second_found, request.public_service)
                    second_result = await search_official_pillars(second_article_queries)
                    (
                        live_sources_2, regulatory_sources_2, case_law_sources_2,
                        live_issue_2, regulatory_issue_2, case_law_issue_2, temporal_issue_2, warnings_2,
                    ) = second_result
                    def merge_sources(existing, additions):
                        merged = {str(item.get("source_id") or id(item)): item for item in existing}
                        for item in additions:
                            merged[str(item.get("source_id") or id(item))] = item
                        return list(merged.values())
                    had_live = bool(live_sources_2)
                    had_regulatory = bool(regulatory_sources_2)
                    had_case_law = bool(case_law_sources_2)
                    live_sources = merge_sources(live_sources, live_sources_2)
                    regulatory_sources = merge_sources(regulatory_sources, regulatory_sources_2)
                    case_law_sources = merge_sources(case_law_sources, case_law_sources_2)
                    live_issue = None if had_live else (live_issue_2 or live_issue)
                    regulatory_issue = None if had_regulatory else (regulatory_issue_2 or regulatory_issue)
                    case_law_issue = None if had_case_law else (case_law_issue_2 or case_law_issue)
                    temporal_issue = temporal_issue_2 or temporal_issue
                    search_warnings = list(dict.fromkeys([*(search_warnings or []), *(warnings_2 or [])]))

        period_version_comparison = None
        comparison_end_date = period_end or effective_date
        if period_start and period_start < comparison_end_date:
            period_version_comparison = _compare_official_period_versions(
                live_sources, regulatory_sources, period_start, comparison_end_date,
            )
            # Keep every date-scoped version found at START, END or CURRENT.
            # A source found at only one facts-period endpoint may still protect
            # the agent for that part of the period; absence at the other endpoint
            # is not proof of repeal or non-applicability.
            for version_source in [*live_sources, *regulatory_sources]:
                version_source["period_endpoint_match"] = version_source.get("version_endpoint") in {
                    "START", "END", "CURRENT",
                }
            temporal_context["version_comparison"] = {
                key: value for key, value in period_version_comparison.items()
                if key != "matched_source_ids"
            }

        # CETAT search hits are metadata only. If the full-text route has not
        # been explicitly enabled and validated, never pass those hits to the model.
        if case_law_sources:
            if not settings.legifrance_cetat_fulltext_enabled:
                case_law_fulltext_issue = (
                    "Des décisions CETAT ont été repérées, mais leur consultation intégrale officielle "
                    "est désactivée ; les métadonnées ne peuvent pas fonder une analyse IA."
                )
            else:
                consultation_results = await asyncio.gather(
                    *(case_law_connector.consult(item["source_id"])
                      for item in case_law_sources[:min(6, len(research_queries))] if item.get("source_id")),
                    return_exceptions=True,
                )
                for result in consultation_results:
                    if isinstance(result, BaseException):
                        logger.warning("Consultation intégrale CETAT indisponible : %r", result)
                        case_law_fulltext_issue = (
                            "Au moins une décision CETAT n'a pas pu être consultée en texte intégral ; "
                            "son résultat de recherche reste une métadonnée non probante."
                        )
                        continue
                    # A decision rendered after the facts may still interpret
                    # the law applicable to them. Keep it, but label its timing.
                    temporal_status = decision_temporal_status(
                        result.get("decision_date"), facts_reference_date
                    )
                    result["temporal_status"] = temporal_status
                    if temporal_status == "DECISION_POSTERIOR_TO_FACTS":
                        result["temporal_explanation"] = (
                            "Décision postérieure aux faits : elle peut éclairer l'interprétation du droit, "
                            "mais ne prouve pas à elle seule la règle applicable à la date des faits."
                        )
                    elif temporal_status == "DECISION_DATE_UNKNOWN":
                        result["temporal_explanation"] = (
                            "Date de décision non vérifiée : ne pas lui attribuer de portée temporelle certaine."
                        )
                    result["content_kind"] = "FULL_TEXT"
                    decision_text = str(result.get("text") or "")
                    if len(decision_text) <= 12000:
                        result["excerpt"] = decision_text
                        result["retrieval_scope"] = "FULL_TEXT"
                    else:
                        result["excerpt"] = decision_text[:9000] + "\n\n[Passages intermédiaires non transmis]\n\n" + decision_text[-3000:]
                        result["retrieval_scope"] = "BEGINNING_AND_FINAL_PASSAGES_FROM_VERIFIED_FULL_TEXT"
                    scope = classify_public_service_scope(
                        result, target_versant=request.public_service,
                        agent_status=legal_context.get("agent_status"),
                        agent_working_time_status=legal_context.get("agent_working_time_status"),
                    )
                    result["public_service_scope"] = scope["scope"]
                    result["scope_evidence"] = scope["evidence"]
                    result["analysis_eligible"] = scope["analysis_eligible"]
                    result["claim_eligible"] = scope.get("claim_eligible", scope["analysis_eligible"])
                    if not scope["analysis_eligible"] or not _source_relevant_for_target(research_queries, result, request.public_service):
                        logger.info(
                            "Décision CETAT écartée du dossier IA : périmètre ou thème non confirmé (source=%s, scope=%s)",
                            result.get("source_id"), scope["scope"],
                        )
                        case_law_fulltext_issue = (
                            "Une décision CETAT consultée a été écartée car son lien avec la fonction publique territoriale ou le sujet posé n'est pas suffisamment établi."
                        )
                        continue
                    result["citation_integrity"] = {
                        "valid": bool(
                            result.get("source_id")
                            and result.get("source_status") == "OFFICIAL_FULL_TEXT_ID_MATCHED"
                            and result.get("full_text_retrieved") is True
                            and result.get("official_source") is True
                            and len(result.get("text") or "") >= 80
                        ),
                        "verification_scope": "PISTE_CETAT_CONSULT_ID_AND_FULL_TEXT_AND_DATE_AND_SCOPE",
                    }
                    if result["citation_integrity"]["valid"]:
                        case_law_full_text_sources.append(result)
                    else:
                        case_law_fulltext_issue = (
                            "Une décision CETAT consultée n'a pas satisfait tous les contrôles d'identifiant, de provenance et de texte intégral."
                        )
        local_sources: list[dict] = []
        local_issue = None
        if _should_search_local_employer_documents(request.public_service, request.employer):
            if conn is None:
                local_issue = "Les documents propres à l'employeur ne sont pas accessibles dans ce contexte."
            else:
                try:
                    local_sources = []
                    # Keep the search strictly tenant-scoped, but execute it for
                    # each deterministic legal sub-question. Sequential calls
                    # intentionally reuse the same asyncpg connection.
                    local_hits_by_id: dict[str, dict] = {}
                    local_failed_queries = []
                    for local_query in research_queries:
                        try:
                            query_hits = await search_local_documents(
                                conn, organization_id, request.employer,
                                local_query[:500], effective_date, limit=5,
                            )
                        except Exception:
                            logger.exception(
                                "Échec de la recherche locale pour un axe juridique (%s).",
                                local_query[:100],
                            )
                            local_failed_queries.append(local_query)
                            continue
                        for query_hit in query_hits:
                            source_key = str(query_hit.get("source_id") or "")
                            if not source_key:
                                continue
                            existing = local_hits_by_id.get(source_key)
                            if existing is None or float(query_hit.get("relevance") or 0) > float(existing.get("relevance") or 0):
                                local_hits_by_id[source_key] = dict(query_hit)
                    if local_failed_queries:
                        local_issue = (
                            "La recherche dans les documents locaux a échoué pour au moins une sous-question."
                        )
                    base_local_hits = sorted(
                        local_hits_by_id.values(),
                        key=lambda item: -float(item.get("relevance") or 0),
                    )[:15]
                    for local_date, local_endpoint in _local_document_reference_dates(
                        period_start, period_end, effective_date,
                    ):
                        for base_hit in base_local_hits:
                            hit = dict(base_hit)
                            original_id = str(hit.get("source_id") or "")
                            if not original_id:
                                continue
                            hit["source_id"] = f"{original_id}_V{local_date:%Y%m%d}"
                            hit["temporal_status"] = local_document_temporal_status(
                                hit.get("effective_from"), hit.get("effective_to"),
                                str(hit.get("validation_status") or "COLLECTED_UNVERIFIED"),
                                local_date,
                            )
                            hit["requested_effective_date"] = local_date.isoformat()
                            hit["version_endpoint"] = local_endpoint
                            hit["version_matches_facts_date"] = bool(
                                parsed_date and local_date == parsed_date
                            )
                            hit["version_role"] = (
                                "FACTS_DATE_VERSION"
                                if parsed_date and local_date == parsed_date
                                else "FACTS_PERIOD_START_VERSION"
                                if local_endpoint == "START"
                                else "FACTS_PERIOD_END_VERSION"
                                if local_endpoint == "END"
                                else "CURRENT_LAW_VERSION"
                            )
                            hit["title"] = (
                                f"{hit.get('title') or 'Document local'} — situation au {local_date.isoformat()}"
                            )
                            local_sources.append(hit)
                except Exception:
                    logger.exception("Échec de la recherche dans le corpus local tenant-scoped.")
                    local_issue = "La recherche dans les documents de l'employeur n'a pas pu être exécutée."


        personal_sources: list[dict] = []
        if conn is not None and personal_user_id:
            try:
                personal_hits_by_id: dict[str, dict] = {}
                for personal_query in research_queries:
                    rows = await conn.fetch(
                        """SELECT id,title,document_type,collectivity_scope,validation_status,
                                  effective_from,effective_to,
                                  ts_rank(search_vector,plainto_tsquery('french',$2)) relevance,
                                  ts_headline('french',extracted_text,plainto_tsquery('french',$2),
                                    'MaxWords=90,MinWords=20,ShortWord=2,HighlightAll=false') excerpt
                           FROM personal_documents
                           WHERE owner_user_id=$1::uuid AND scan_status='CLEAN'
                             AND extraction_status='EXTRACTED'
                             AND search_vector @@ plainto_tsquery('french',$2)
                           ORDER BY relevance DESC,created_at DESC LIMIT $3""",
                        personal_user_id, personal_query[:500], 5,
                    )
                    for row in rows:
                        key = str(row["id"])
                        candidate = dict(row)
                        existing = personal_hits_by_id.get(key)
                        if existing is None or float(candidate.get("relevance") or 0) > float(existing.get("relevance") or 0):
                            personal_hits_by_id[key] = candidate
                for hit in sorted(
                    personal_hits_by_id.values(),
                    key=lambda item: -float(item.get("relevance") or 0),
                )[:10]:
                    excerpt = re.sub(r"</?b>", "", str(hit.get("excerpt") or ""), flags=re.IGNORECASE)
                    if not excerpt.strip():
                        continue
                    personal_sources.append({
                        "source_type": "PERSONAL_DOCUMENT",
                        "source_id": str(hit["id"]),
                        "title": str(hit.get("title") or "Document personnel"),
                        "document_type": str(hit.get("document_type") or "PERSONAL_REFERENCE"),
                        "collectivity_scope": str(hit.get("collectivity_scope") or "UNCLASSIFIED"),
                        "validation_status": str(hit.get("validation_status") or "COLLECTED_UNVERIFIED"),
                        "effective_from": hit["effective_from"].isoformat() if hit.get("effective_from") else None,
                        "effective_to": hit["effective_to"].isoformat() if hit.get("effective_to") else None,
                        "excerpt": excerpt[:2500],
                        "content_kind": "EXCERPT",
                        "source_status": "USER_UPLOADED_PRIVATE_UNVERIFIED",
                        "temporal_status": "PERSONAL_DOCUMENT_VALIDITY_UNVERIFIED",
                        "reference_role": "PERSONAL_CONTEXT_ONLY",
                        "claim_eligible": False,
                        "official_source": False,
                        "transfer_status": (
                            "TRANSMITTED_FOR_THIS_REQUEST"
                            if allow_local_documents else "NOT_TRANSMITTED"
                        ),
                        "legal_assurance": {
                            "authority_label": "Document personnel non vérifié",
                            "usable_for_conclusion": False,
                            "usable_for_interpretation": False,
                            "reference_role": "PERSONAL_CONTEXT_ONLY",
                        },
                    })
            except Exception:
                logger.warning(
                    "Échec de la recherche dans le corpus documentaire personnel (request_id=%s).",
                    request_id,
                    exc_info=True,
                )

        permanent_sources: list[dict] = []
        permanent_issue = None
        if conn is not None:
            try:
                stored_by_query = []
                stored_search_failed = False
                # One asyncpg connection cannot run concurrent queries; keep the
                # independent corpus searches sequential on this tenant-safe connection.
                for query in research_queries:
                    try:
                        result = await search_legal_corpus(
                            conn, query, effective_date, limit=LEGAL_CORPUS_CANDIDATE_LIMIT,
                        )
                    except Exception as exc:
                        logger.warning("Recherche du corpus juridique en échec (%s) : %r", query[:100], exc)
                        stored_search_failed = True
                        stored_by_query.append([])
                    else:
                        stored_by_query.append(result if isinstance(result, list) else [])
                        if not isinstance(result, list):
                            stored_search_failed = True
                # The client computes the user's original-question embedding locally.
                # Generated research axes remain lexical so no server-side model is loaded.
                if settings.vector_search_enabled and request.query_embedding is not None:
                    try:
                        vector_results = await search_legal_corpus(
                            conn, request.question, effective_date, limit=LEGAL_CORPUS_CANDIDATE_LIMIT,
                            query_embedding=request.query_embedding,
                        )
                    except Exception as exc:
                        logger.warning("Recherche vectorielle indisponible ; maintien du repli lexical : %r", exc)
                        stored_search_failed = True
                    else:
                        stored_by_query.insert(0, vector_results if isinstance(vector_results, list) else [])
                stored = select_multi_source_chunks(
                    stored_by_query, limit=LEGAL_CORPUS_INTERLEAVED_LIMIT,
                )
                if stored_search_failed:
                    permanent_issue = "La recherche dans le corpus juridique permanent a échoué pour au moins un axe ; les résultats disponibles sont partiels."
                for item in stored:
                    source_document_kind = item.get("document_kind")
                    source_decision_date = item.get("signature_date")
                    # Imported administrative decisions are searched in the
                    # permanent corpus through today. Reclassify their date
                    # against the facts period so later judgments remain
                    # available but are explicitly marked as interpretative.
                    source_temporal_status, source_temporal_explanation = (
                        _permanent_source_temporal_metadata(item, facts_reference_date)
                    )
                    official_source_id = item.get("source_id")
                    version_id = item.get("version_id")
                    permanent_sources.append({
                        "source_type": item.get("source_type"),
                        "source_id": corpus_version_citation_id(official_source_id, version_id),
                        "official_source_id": official_source_id,
                        "source_version_id": item.get("source_version_id"),
                        "version_id": str(version_id) if version_id is not None else None,
                        "version_key": item.get("version_key"),
                        "text_sha256": item.get("text_sha256"),
                        "title": item.get("title"), "official_number": item.get("official_number"),
                        "case_number": item.get("official_number"),
                        "document_kind": source_document_kind, "jurisdiction": item.get("jurisdiction"),
                        "raw_metadata": item.get("raw_metadata") or {},
                        "jurisprudential_publication_code": _source_metadata(item).get("publication_code"),
                        "signature_date": source_decision_date, "decision_date": source_decision_date,
                        "publication_date": item.get("publication_date"),
                        "valid_from": item.get("valid_from"), "valid_to": item.get("valid_to"),
                        "temporal_status": source_temporal_status,
                        "temporal_explanation": source_temporal_explanation,
                        "source_status": item.get("source_status"),
                        "version_status": item.get("version_status"),
                        "content_kind": item.get("content_kind"), "excerpt": item.get("excerpt"),
                        "retrieval_scope": item.get("retrieval_scope"),
                        "text": item.get("excerpt") or "", "full_text": item.get("full_text") or "",
                        "official_url": item.get("official_url"),
                        "official_source": item.get("official_source"),
                        "citation_integrity": item.get("citation_integrity"),
                        # Current CGFP snapshot articles are usable for general questions
                        # when no repeal is explicitly recorded; never infer historical effect.
                        "general_info_eligible": parsed_date is None,
                        "reference_role": (
                            "CGFP_SNAPSHOT_FALLBACK_EVIDENCE"
                            if item.get("source_type") == "CGFP_SNAPSHOT" and parsed_date is None
                            else item.get("reference_role")
                        ),
                    })
            except Exception:
                logger.exception("Échec de la recherche dans le corpus juridique national.")
                permanent_issue = "Le corpus juridique permanent n'a pas pu être interrogé."
        else:
            permanent_issue = "Le corpus juridique permanent n'est pas connecté à cette analyse."

        # If the live CGFP article endpoint is unavailable, the indexed official
        # CGFP snapshot may support a bounded explanation for general questions.
        # It is never represented as a live Légifrance verification and is not
        # used to reconstruct the version applicable to historical facts.
        cgfp_snapshot_fallback = should_use_cgfp_snapshot_fallback(
            live_issue, found, research_queries,
            target_versant=request.public_service, live_sources=live_sources,
        )

        sources: list[dict] = []
        # Official API articles have priority, and are included only after a successful
        # search -> getArticle round-trip with matching LEGIARTI identifier and text.
        for item in live_sources:
            if item.get("requested_effective_date"):
                item["title"] = (
                    f"{item.get('title') or 'Article du CGFP'} — version consultée au "
                    f"{item['requested_effective_date']}"
                )
            scope_check = classify_public_service_scope(
                item, target_versant=request.public_service,
                agent_status=legal_context.get("agent_status"),
                        agent_working_time_status=legal_context.get("agent_working_time_status"),
            )
            item["public_service_scope"] = scope_check["scope"]
            item["scope_evidence"] = scope_check["evidence"]
            item["analysis_eligible"] = scope_check["analysis_eligible"]
            item["claim_eligible"] = scope_check.get("claim_eligible", scope_check["analysis_eligible"])
            item["research_axis_relevant"] = _source_relevant_for_target(research_queries, item, request.public_service)
            sources.append({**item, "source_status": "OFFICIAL_API_RESPONSE",
                "temporal_status": "VERSION_RETRIEVED_AT_REQUESTED_DATE",
                "version_matches_facts_date": bool(
                    parsed_date and item.get("requested_effective_date") == parsed_date.isoformat()
                ),
                "version_role": (
                    "FACTS_DATE_VERSION"
                    if parsed_date and item.get("requested_effective_date") == parsed_date.isoformat()
                    else "FACTS_PERIOD_START_VERSION"
                    if item.get("version_endpoint") == "START"
                    else "FACTS_PERIOD_END_VERSION"
                    if item.get("version_endpoint") == "END"
                    else "CURRENT_LAW_VERSION"
                ),
                "page_start": None, "page_end": None, "content_kind": "FULL_TEXT",
                "general_info_eligible": parsed_date is None,
                "citation_integrity": {
                    "valid": bool(item.get("source_id") and len(item.get("text") or "") >= 80),
                    "verification_scope": "PISTE_CODE_DATE_ID_AND_FULL_TEXT",
                }})

        for item in regulatory_sources:
            if item.get("requested_effective_date"):
                item["title"] = (
                    f"{item.get('title') or 'Texte réglementaire'} — version consultée au "
                    f"{item['requested_effective_date']}"
                )
            full_text = item.get("full_text") or ""
            scope_check = classify_public_service_scope(
                item, target_versant=request.public_service,
                agent_status=legal_context.get("agent_status"),
                        agent_working_time_status=legal_context.get("agent_working_time_status"),
            )
            item["public_service_scope"] = scope_check["scope"]
            item["scope_evidence"] = scope_check["evidence"]
            item["analysis_eligible"] = scope_check["analysis_eligible"]
            item["claim_eligible"] = scope_check.get("claim_eligible", scope_check["analysis_eligible"])
            item["research_axis_relevant"] = _source_relevant_for_target(research_queries, item, request.public_service)
            sources.append({
                **item,
                "excerpt": item.get("excerpt") or full_text[:1800],
                "text": full_text,
                "content_kind": "FULL_TEXT",
                "temporal_status": "VERSION_RETRIEVED_AT_REQUESTED_DATE",
                "version_matches_facts_date": bool(
                    parsed_date and item.get("requested_effective_date") == parsed_date.isoformat()
                ),
                "version_role": (
                    "FACTS_DATE_VERSION"
                    if parsed_date and item.get("requested_effective_date") == parsed_date.isoformat()
                    else "FACTS_PERIOD_START_VERSION"
                    if item.get("version_endpoint") == "START"
                    else "FACTS_PERIOD_END_VERSION"
                    if item.get("version_endpoint") == "END"
                    else "CURRENT_LAW_VERSION"
                ),
                "general_info_eligible": parsed_date is None,
                "citation_integrity": {
                    "valid": bool(item.get("source_id") and len(full_text) >= 80),
                    "verification_scope": "PISTE_LODA_DATE_CONSULT_ID_AND_FULL_TEXT",
                },
            })

        for item in permanent_sources:
            response_source = {**item, "source_url": item.get("official_url")}
            # Apply the same French public-service perimeter as live sources.
            scope_check = _classify_permanent_source_scope(response_source, request.public_service)
            response_source["public_service_scope"] = scope_check["scope"]
            response_source["scope_evidence"] = scope_check["evidence"]
            response_source["analysis_eligible"] = scope_check["analysis_eligible"]
            response_source["claim_eligible"] = scope_check.get("claim_eligible", scope_check["analysis_eligible"])
            response_source["research_axis_relevant"] = _source_relevant_for_target(research_queries, response_source, request.public_service)
            response_source["general_info_eligible"] = (
                parsed_date is None
                and response_source.get("version_status") not in {"REPEALED", "NOT_IN_FORCE"}
            )
            if response_source.get("source_type") in {"SERVICE_PUBLIC_PART", "INSTITUTIONAL_GUIDANCE"}:
                response_source["claim_eligible"] = False
                response_source["reference_role"] = "NON_NORMATIVE_CONTEXT_ONLY"
            if response_source.get("source_type") == "CGFP_SNAPSHOT":
                response_source["reference_role"] = "CGFP_SNAPSHOT_FALLBACK_EVIDENCE"
                response_source["snapshot_modified_at"] = (
                    _source_metadata(response_source).get("snapshot_modified_at")
                    or _source_metadata(response_source).get("generated_at")
                )
                response_source["snapshot_verification_status"] = (
                    _source_metadata(response_source).get("verification_status")
                )
            sources.append(response_source)

        sources.extend(local_sources)
        sources.extend(personal_sources)

        if found and cgfp_snapshot_fallback and parsed_date is None:
            for hit in found["results"]:
                if not _source_relevant_for_target(research_queries, hit, request.public_service):
                    continue
                article = get_cgfp_article(hit["article"])
                citation = {"source_id": hit["source_id"], "article": hit["article"],
                    "page_start": hit["page_start"], "page_end": hit["page_end"], "excerpt": hit["excerpt"]}
                integrity = validate_snapshot_citation(citation, article or {})
                if integrity["valid"] and _cgfp_article_fpt_eligible(hit["article"], request.public_service):
                    article_text = str((article or {}).get("text") or "")
                    article_ref = re.sub(r"\s+", "", str(hit["article"])).upper()
                    snapshot_title = f"Code général de la fonction publique — article {article_ref}"
                    snapshot_scope = classify_public_service_scope({
                        "title": snapshot_title,
                        "text": article_text,
                        "document_kind": "CODE",
                    }, target_versant=request.public_service)
                    sources.append({
                        "source_type": "CGFP_SNAPSHOT",
                        "source_id": f"{hit['source_id']}:{article_ref}",
                        "snapshot_document_id": hit["source_id"],
                        "title": snapshot_title,
                        "article": article_ref,
                        "page_start": hit["page_start"], "page_end": hit["page_end"],
                        "excerpt": article_text[:12000],
                        "text": article_text,
                        "content_kind": "SNAPSHOT_EXCERPT",
                        "snapshot_modified_at": found["source"]["snapshot_modified_at"],
                        "requested_effective_date": found["source"]["snapshot_modified_at"],
                        "source_status": found["source"]["verification_status"],
                        "public_service_scope": snapshot_scope["scope"],
                        "scope_evidence": snapshot_scope["evidence"],
                        "analysis_eligible": snapshot_scope["analysis_eligible"],
                        "claim_eligible": snapshot_scope.get(
                            "claim_eligible", snapshot_scope["analysis_eligible"]
                        ),
                        "research_axis_relevant": True,
                        "reference_role": "CGFP_SNAPSHOT_FALLBACK_EVIDENCE",
                        "general_info_eligible": parsed_date is None,
                        "temporal_status": "SNAPSHOT_ONLY_NOT_TEMPORALLY_VERIFIED",
                        "citation_integrity": integrity,
                        "document": found["source"]["source_file"],
                    })

        for decision in case_law_sources:
            # A CETAT search hit is metadata only; it is never passed as legal evidence to AI.
            sources.append({
                **decision,
                "page_start": None,
                "page_end": None,
                "content_kind": "METADATA",
                "citation_integrity": {
                    "valid": False,
                    "verification_scope": "OFFICIAL_SEARCH_RESULT_ID_ONLY_NOT_FULL_TEXT",
                },
            })

        for decision in case_law_full_text_sources:
            scope_check = classify_public_service_scope(
                decision, target_versant=request.public_service,
                agent_status=legal_context.get("agent_status"),
                        agent_working_time_status=legal_context.get("agent_working_time_status"),
            )
            decision["public_service_scope"] = scope_check["scope"]
            decision["scope_evidence"] = scope_check["evidence"]
            decision["analysis_eligible"] = scope_check["analysis_eligible"]
            decision["claim_eligible"] = scope_check.get("claim_eligible", scope_check["analysis_eligible"])
            decision["research_axis_relevant"] = _source_relevant_for_target(research_queries, decision, request.public_service)
            sources.append({**decision, "page_start": None, "page_end": None})

        # Gemini assesses document content after the lexical fallback. This is relevance
        # triage only; source, citation, temporal and FPT-scope controls remain authoritative.
        # Semantic source ranking is optional and previously caused an extra Gemini
        # request on every chat turn. Keep the deterministic topic/versant filter as
        # the baseline; reserve model calls for research planning and evidence analysis.
        for source in sources:
            source["research_axis_relevant"] = _source_relevant_for_target(
                research_queries, source, request.public_service,
            )


        # A direct request for the text/content of a numbered CGFP article is an
        # exact-reference lookup. If that article was not independently retrieved,
        # do not let lexical CGFP hits, unrelated decrees or CETAT metadata create
        # a misleading partially-verified answer.
        missing_article = missing_direct_article_reference(request.question, sources)
        if missing_article:
            return AskResponse(
                request_id=request_id,
                verification_status="NON_VERIFIE",
                answer=(
                    (
                        f"La recherche officielle n'a pas abouti : {live_issue} "
                        if live_issue else
                        f"Je n'ai pas retrouvé de source officielle vérifiable correspondant exactement "
                        f"à l'article {missing_article} du Code général de la fonction publique. "
                    )
                    + "Je ne peux donc ni en reproduire le contenu ni en déduire des conséquences juridiques. "
                    "Aucune conclusion juridique n'est formulée. Les résultats documentaires sans correspondance exacte sont écartés pour éviter toute confusion."
                ),
                sources=[],
                missing_information=[
                    (
                        f"Recherche officielle indisponible : la référence {missing_article} n'a pas pu être vérifiée."
                        if live_issue else
                        f"Référence exacte {missing_article} non retrouvée dans les sources CGFP vérifiées."
                    ),
                    *([live_issue] if live_issue else []),
                    "Vérifier la référence ou transmettre le lien officiel Légifrance de l'article recherché.",
                ],
            )

        # Classification is computed before the model call so the prompt receives
        # the legal-source family and the limitations attached to each document.
        sources = assess_source_set(sources)["sources"]
        # Hide topic-mismatched hits before early returns and user-facing rendering.
        sources = filter_irrelevant_sources_for_display(sources)
        permanent_source_ids = {s.get("source_id") for s in permanent_sources if s.get("source_id")}
        usable_permanent = [
            s for s in sources if _is_usable_permanent_source(s, permanent_source_ids)
        ]
        usable_official = [
            s for s in sources
            if s.get("source_type") in {
                "LEGIFRANCE_API", "LEGIFRANCE_LODA", "LEGIFRANCE_CETAT_FULL_TEXT",
            }
            and s.get("content_kind") != "METADATA"
            and _citation_is_valid(s)
            and s.get("analysis_eligible") is True
            and s.get("claim_eligible", True) is not False
            and s.get("research_axis_relevant", True) is not False
        ]
        usable_local = [s for s in local_sources
            if _citation_is_valid(s)
            and s.get("temporal_status") == "VERIFIED_APPLICABLE"
            and s.get("research_axis_relevant", True) is not False]
        usable_snapshot_fallback = [
            s for s in sources
            if s.get("source_type") == "CGFP_SNAPSHOT"
            and s.get("reference_role") == "CGFP_SNAPSHOT_FALLBACK_EVIDENCE"
            and s.get("general_info_eligible") is True
            and s.get("research_axis_relevant") is True
            and _citation_is_valid(s)
        ]
        if not usable_official and not usable_permanent and not usable_local and not usable_snapshot_fallback:
            missing = ["Aucune disposition législative ou réglementaire exploitable n'a été récupérée.",
                "Recherche officielle Légifrance/PISTE et vérification des textes réglementaires complémentaires.",
                "Recherche de jurisprudence pertinente et vérification des sources locales applicables."]
            if parsed_date is not None:
                missing.insert(0, f"Date des faits déclarée : {parsed_date.isoformat()}.")
            else:
                missing.insert(0, "La date exacte des faits n'a pas été fournie ; la recherche du droit actuel reste effectuée. La version applicable à une date passée sera vérifiée si cela devient déterminant.")
            if permanent_issue:
                missing.insert(0, permanent_issue)
            if cgfp_issue:
                missing.insert(0, cgfp_issue)
            if cgfp_partial_issue:
                missing.insert(0, cgfp_partial_issue)
            missing.extend(search_warnings)
            missing.insert(0, "Le snapshot CGFP seul, lorsqu'il existe, reste un repère documentaire et ne peut pas justifier une analyse IA contextualisée.")
            if local_issue:
                missing.insert(0, local_issue)
            elif _should_search_local_employer_documents(request.public_service, request.employer) and not local_sources:
                missing.insert(0, "Aucun document local correspondant n'a été trouvé pour cet employeur ; vérifier le code de collectivité et les pièces déposées.")
            if any(
                s.get("source_type") == "LOCAL_DOCUMENT"
                and (s.get("validation_status") != "VERIFIED_APPLICABLE"
                     or s.get("temporal_status") != "VERIFIED_APPLICABLE")
                for s in local_sources
            ):
                missing.insert(
                    0,
                    "Des documents locaux ont été retrouvés, mais leur validation humaine ou leur période d'effet ne permet pas de les utiliser pour une conclusion.",
                )
            if live_issue:
                missing.insert(0, live_issue)
            if regulatory_issue:
                missing.insert(0, regulatory_issue)
            if case_law_issue:
                missing.insert(0, case_law_issue)
            if case_law_fulltext_issue:
                missing.insert(0, case_law_fulltext_issue)
            if temporal_issue:
                missing.insert(0, temporal_issue)
            if (not found or not found.get("results")) and not cgfp_issue:
                missing.insert(0, "L'index CGFP a été interrogé mais aucun article pertinent n'a été retrouvé.")
            return AskResponse(
                request_id=request_id,
                verification_status="NON_VERIFIE",
                answer="Les textes officiels récupérés ne permettent pas de répondre avec certitude sur ce point précis. Aucune conclusion juridique n'est formulée.",
                sources=sources,
                missing_information=missing,
                clarification_question=None,
            )

        missing = ["Vérifier l'existence d'une abrogation ou d'un remplacement explicite du texte retenu.",
            "Vérifier les dispositions réglementaires, décrets et textes spéciaux liés à la question.",
            "Rechercher et vérifier la jurisprudence pertinente si elle peut modifier l'analyse.",
            "Vérifier les actes locaux, délibérations et accords applicables à l'employeur concerné."]
        if permanent_issue:
            missing.insert(0, permanent_issue)
        if cgfp_issue:
            missing.insert(0, cgfp_issue)
        if cgfp_partial_issue:
            missing.insert(0, cgfp_partial_issue)
        missing.extend(search_warnings)
        if local_issue:
            missing.insert(0, local_issue)
        elif _should_search_local_employer_documents(request.public_service, request.employer) and not local_sources:
            missing.insert(0, "Aucun document local correspondant n'a été trouvé pour cet employeur ; vérifier le code de collectivité et les pièces déposées.")
        if any(s.get("source_type") == "LOCAL_DOCUMENT" and s.get("temporal_status") != "VERIFIED_APPLICABLE"
               for s in local_sources):
            missing.insert(0, "Des documents locaux correspondent à la recherche mais leur validation humaine ou leur période d'effet ne permet pas de les utiliser pour une conclusion.")
        if any(s.get("content_kind") == "METADATA" for s in permanent_sources):
            missing.insert(0, "Certaines circulaires ou textes ne sont présents qu'au stade des métadonnées : ils ne sont pas utilisés pour produire une analyse IA.")
        if any(
            s.get("temporal_status") == "TEMPORAL_SCOPE_INCOMPLETE"
            and s.get("general_info_eligible") is not True
            for s in permanent_sources
        ):
            missing.insert(0, "Certaines sources ne permettent pas de vérifier une version applicable à la date demandée ; elles sont écartées des conclusions historiques.")
        if temporal_issue:
            missing.insert(0, temporal_issue)
        if live_issue:
            missing.insert(0, live_issue)
        if cgfp_snapshot_fallback:
            missing.insert(
                0,
                "Mode de secours CGFP activé : utilisation du PDF Légifrance local consolidé au 31 octobre 2026. "
                "Cette copie permet de consulter les articles et leur rédaction dans ce snapshot, "
                "mais ne confirme pas leur version applicable à la date des faits ni les modifications postérieures. "
                "Les décrets, textes complémentaires et la jurisprudence doivent toujours être vérifiés séparément.",
            )
        if regulatory_issue:
            missing.insert(0, regulatory_issue)
        if case_law_issue:
            missing.insert(0, case_law_issue)
        if case_law_fulltext_issue:
            missing.insert(0, case_law_fulltext_issue)
        if any(item.get("temporal_status") == "DECISION_POSTERIOR_TO_FACTS"
               for item in [*case_law_full_text_sources, *permanent_sources]):
            missing.insert(
                0,
                "Une décision postérieure aux faits a été conservée car elle peut éclairer l'interprétation du droit antérieur ; sa date et sa portée temporelle doivent être distinguées de la règle applicable au jour des faits.",
            )
        if case_law_sources and not case_law_full_text_sources:
            missing.insert(0, "Les résultats CETAT restent des métadonnées : aucun texte intégral de décision n'est utilisé pour l'analyse IA.")
        if not case_law_sources and not case_law_issue:
            missing.insert(0, "La recherche CETAT a été exécutée sans retrouver de décision pertinente pour cette requête.")
        if temporal_context["period_start"] or temporal_context["period_end"]:
            missing.insert(0, f"Période déclarée : du {temporal_context['period_start'] or 'début non précisé'} au {temporal_context['period_end'] or ('aujourd’hui' if temporal_context['ongoing'] else 'fin non précisée')}.")
        if temporal_context["ongoing"]:
            missing.insert(0, "Situation déclarée toujours en cours : les sources sont interrogées à la date actuelle. Si les règles ont changé pendant la période, une comparaison des versions successives reste nécessaire.")
            if not temporal_context["period_start"]:
                missing.insert(1, "Début de la situation non précisé : l'analyse porte sur les règles vérifiées à la date actuelle et ne permet pas de reconstituer toute l'histoire antérieure.")
        if period_version_comparison:
            missing.insert(0, (
                "Comparaison Légifrance aux deux bornes : "
                f"{period_version_comparison['changed_text_count']} rédaction(s) différente(s), "
                f"{period_version_comparison['same_text_count']} identique(s), "
                f"{period_version_comparison['start_only_search_count']} résultat(s) uniquement au début "
                f"et {period_version_comparison['end_only_search_count']} uniquement à la fin. "
                "Les résultats non retrouvés à une borne ne prouvent pas une abrogation. "
                "Cette comparaison ne reconstitue pas toutes les modifications intermédiaires ; "
                "les dates d'effet et éventuelles versions entre ces bornes restent à contrôler."
            ))
            missing.insert(1, (
                "La jurisprudence CETAT a été recherchée jusqu'à la date actuelle, y compris les décisions postérieures à la période des faits. "
                "Ces décisions peuvent éclairer l'interprétation du droit antérieur, mais ne prouvent pas à elles seules la règle applicable à chaque date de la période."
            ))

        ai_sources: list[dict] = []
        ai_usage = None
        if not (usable_official or usable_permanent or usable_local or usable_snapshot_fallback):
            ai_answer = None
            missing.insert(
                0,
                "Analyse IA suspendue : les trois piliers documentaires n'ont pas tous pu être interrogés avec succès. Aucune réponse juridique de mémoire n'est autorisée.",
            )
        else:
            provider_status = await check_provider_availability()
            if provider_status.get("status") != "AVAILABLE":
                ai_answer = None
                if provider_status.get("status") == "MODEL_DISABLED" and provider_status.get("reason") == "paid_plan_required":
                    missing.insert(
                        0,
                        "Le fournisseur IA configuré refuse actuellement l'accès au modèle (accès ou crédits non activés sur le compte). Aucune inférence n'a été envoyée ; la réponse reste documentaire. Vérifiez l'accès au fournisseur ou configurez un endpoint IA autorisé.",
                    )
                else:
                    status_label = str(provider_status.get("status") or "UNKNOWN")[:60]
                    missing.insert(
                        0,
                        f"Le fournisseur IA n'a pas confirmé la disponibilité du modèle (statut : {status_label}). Aucune inférence n'a été envoyée ; la réponse reste documentaire.",
                    )
            else:
                try:
                    eligible_temporal_statuses = {
                        "IN_FORCE_ON_REQUESTED_DATE",
                        "DECISION_AVAILABLE_BY_REQUESTED_DATE",
                        "VERSION_RETRIEVED_AT_REQUESTED_DATE",
                        "DECISION_ANTERIOR_OR_CONTEMPORANEOUS_TO_FACTS",
                        "DECISION_POSTERIOR_TO_FACTS",
                        "DECISION_DATE_VERIFIED_NO_FACTS_DATE",
                        "VERIFIED_APPLICABLE",
                    }
                    # A dated CGFP snapshot may support a bounded fallback explanation
                    # when PISTE cannot return a relevant article. It is never promoted
                    # to proof of current or historical applicability.
                    verified_sources = [
                        (
                            {
                                **s,
                                "reference_role": "GENERAL_PUBLIC_SERVICE_CONTEXT_ONLY",
                            }
                            if s.get("public_service_scope") == "GENERAL_PUBLIC_SERVICE"
                            else {
                                **s,
                                "reference_role": "INTERPRETIVE_CONTEXT_ONLY",
                            }
                            if (
                                s.get("source_type") == "LEGIFRANCE_CETAT_FULL_TEXT"
                                and s.get("temporal_status") == "DECISION_POSTERIOR_TO_FACTS"
                            )
                            else s
                        )
                        for s in sources
                        if s.get("source_type") not in {"LEGIFRANCE_CETAT_SEARCH", "CGFP_SNAPSHOT"}
                        and s.get("research_axis_relevant", True) is not False
                        and s.get("content_kind") != "METADATA"
                        and _citation_is_valid(s)
                        and (
                            s.get("temporal_status") in eligible_temporal_statuses
                            or (
                                s.get("temporal_status") == "TEMPORAL_SCOPE_INCOMPLETE"
                                and s.get("general_info_eligible") is True
                            )
                        )
                        # FPT and explicitly common sources can support claims.
                        # Generic public-service sources may accompany the prompt
                        # as context, but are marked context-only and cannot ground claims.
                        and (
                            s.get("analysis_eligible") is True
                            or (
                                s.get("source_type") == "LOCAL_DOCUMENT"
                                and s.get("validation_status") in {"VERIFIED_APPLICABLE", "VERIFIED_HISTORICAL"}
                            )
                        )
                        and s.get("research_axis_relevant", True) is not False
                        and _source_allowed_for_period_analysis(
                            s, bool(period_version_comparison), period_start,
                            comparison_end_date,
                        )
                    ]
                    cgfp_fallback_sources = [
                        s for s in sources
                        if s.get("source_type") == "CGFP_SNAPSHOT"
                        and s.get("reference_role") == "CGFP_SNAPSHOT_FALLBACK_EVIDENCE"
                        and s.get("general_info_eligible") is True
                        and s.get("research_axis_relevant") is True
                        and _citation_is_valid(s)
                    ]
                    context_guidance_sources = [
                        s for s in sources
                        if s.get("source_type") in {"SERVICE_PUBLIC_PART", "INSTITUTIONAL_GUIDANCE"}
                        and s.get("reference_role") == "NON_NORMATIVE_CONTEXT_ONLY"
                        and (s.get("legal_assurance") if isinstance(s.get("legal_assurance"), dict) else {}).get("usable_for_interpretation") is True
                        and s.get("content_kind") == "FULL_TEXT"
                        and _citation_is_valid(s)
                        and s.get("research_axis_relevant", True) is not False
                    ]
                    base_ai_sources = (
                        cgfp_fallback_sources + verified_sources + context_guidance_sources
                        if verified_sources or cgfp_fallback_sources or context_guidance_sources else []
                    )
                    personal_context_sources = [
                        source for source in personal_sources
                        if allow_local_documents
                        and source.get("transfer_status") == "TRANSMITTED_FOR_THIS_REQUEST"
                    ]
                    # Personal files can supply local factual context only. They
                    # remain explicitly ineligible as legal claim evidence.
                    ai_sources = base_ai_sources + personal_context_sources if base_ai_sources else []
                    if ai_sources:
                        answer_started_at = time.perf_counter()
                        ai_result = await analyze_question(
                            question=contextual_question,
                            employer=_effective_employer_for_versant(request.public_service, request.employer),
                            facts_date=effective_date.isoformat(),
                            facts_period=temporal_context,
                            sources=ai_sources,
                            conversation_history=provider_history,
                            legal_context=legal_context,
                            allow_local_documents=allow_local_documents,
                        )
                        if isinstance(ai_result, AIAnalysisResult):
                            raw_ai_content = ai_result.content
                            ai_usage = {
                                "provider": "gemini" if settings.ai_api_base_url and "generativelanguage.googleapis.com" in settings.ai_api_base_url else "openai_compatible",
                                "model": ai_result.model,
                                "operation": "answer_generation",
                                "latency_ms": max(0, round((time.perf_counter() - answer_started_at) * 1000)) if answer_started_at is not None else None,
                                "prompt_tokens": ai_result.prompt_tokens,
                                "completion_tokens": ai_result.completion_tokens,
                                "total_tokens": ai_result.total_tokens,
                                "outcome": "STRUCTURED_OUTPUT_RECEIVED",
                            }
                        else:
                            # All providers and test adapters must use the same strict JSON contract.
                            raw_ai_content = ai_result
                        structured_answer = parse_structured_answer(raw_ai_content)
                        claim_validation = validate_claim_evidence(
                            structured_answer, ai_sources,
                            required_axes=legal_context.get("axes_recherche_documentaire") or None,
                            facts_period=temporal_context,
                            public_service=request.public_service,
                        )
                        for uncovered_axis in claim_validation.get("uncovered_axes", []):
                            missing.append(f"Aucune source suffisamment pertinente n'a permis de répondre à cette sous-question : {uncovered_axis}")
                        if claim_validation.get("invalid_claims"):
                            missing.append(
                                "Certaines propositions générées ont été écartées car leur source, leur citation ou leur correspondance documentaire n'a pas satisfait les contrôles."
                            )
                        if not claim_validation["valid"]:
                            ai_answer = None
                            if ai_usage is not None:
                                ai_usage["outcome"] = "REJECTED_UNSUPPORTED_CLAIMS"
                            missing.insert(
                                0,
                                "La réponse IA a été bloquée : sortie structurée absente, sous-question documentaire non couverte ou affirmation sans citation exacte dans une source officielle applicable.",
                            )
                        elif not claim_validation["claims"]:
                            ai_answer = None
                            if ai_usage is not None:
                                ai_usage["outcome"] = "ABSTAINED_NO_SUPPORTED_CLAIMS"
                            missing.insert(
                                0,
                                "Le moteur IA n'a produit aucune affirmation pouvant être reliée à un extrait documentaire exact. Aucune conclusion n'est formulée.",
                            )
                        else:
                            entailment_validation = await verify_claim_entailment(
                                question=contextual_question,
                                claims=claim_validation["claims"], sources=ai_sources,
                                public_service=request.public_service,
                                allow_local_documents=allow_local_documents,
                                facts_period=temporal_context,
                                **_provider_usage_kwargs(verify_claim_entailment, ai_usage_events),
                            )
                            supported_indices = entailment_validation.get("supported_claim_indices", [])
                            if not entailment_validation.get("valid") and not supported_indices:
                                ai_answer = None
                                if ai_usage is not None:
                                    ai_usage["outcome"] = "REJECTED_UNSUPPORTED_ENTAILMENT"
                                missing.insert(
                                    0,
                                    "La réponse IA a été bloquée : aucune proposition n'a passé le contrôle contradictoire de son appui documentaire. Aucune conclusion n'est formulée.",
                                )
                            else:
                                claims = (
                                    claim_validation["claims"]
                                    if entailment_validation.get("valid")
                                    else [
                                        claim for index, claim in enumerate(claim_validation["claims"])
                                        if index in supported_indices
                                    ]
                                )
                                if len(claims) < len(claim_validation["claims"]):
                                    missing.append(
                                        "Certaines propositions ont été écartées après le contrôle contradictoire ; seules les propositions confirmées sont conservées."
                                    )
                                # The model is instructed to put the direct answer first.
                                # Render it immediately instead of prefacing it with legal boilerplate.
                                rendered_claims = []
                                unique_sources = {}
                                for claim in claims:
                                    source_id = claim["source_id"]
                                    source_title = " ".join(str(claim["source_title"]).split())[:300]
                                    unique_sources[source_id] = source_title
                                    # Lead with the plain-language explanation. The exact
                                    # supporting quote remains available in the source panel,
                                    # rather than overwhelming the agent's conversational answer.
                                    rendered_claims.append(f"{claim['text']} [source:{source_id}]")
                                    rendered_claims.append("")
                                rendered_claims.append("Textes et références à consulter :")
                                for source_id, source_title in unique_sources.items():
                                    rendered_claims.append(f"• {source_title} [source:{source_id}]")
                                rendered_claims.extend([""])
                                if any(
                                    source.get("source_type") == "CGFP_SNAPSHOT"
                                    and source.get("reference_role") == "CGFP_SNAPSHOT_FALLBACK_EVIDENCE"
                                    for source in ai_sources
                                    if source.get("source_id") in unique_sources
                                ):
                                    snapshot_date = next(
                                        (source.get("snapshot_modified_at") for source in ai_sources
                                         if source.get("source_type") == "CGFP_SNAPSHOT"),
                                        "date non précisée",
                                    )
                                    rendered_claims.append(
                                        f"Réserve importante : PISTE n'a pas permis de vérifier ces dispositions. "
                                        f"Cette explication s'appuie sur le snapshot local du CGFP daté du {snapshot_date}. "
                                        "Elle ne confirme pas que cette rédaction est toujours en vigueur ni qu'elle était applicable à une date antérieure. "
                                        "Les décrets et autres textes complémentaires doivent être vérifiés séparément."
                                    )
                                else:
                                    rendered_claims.append(
                                        f"Cette réponse porte sur les règles consultées au {effective_date.isoformat()} ; "
                                        + ("elle ne constitue pas une conclusion sur une situation individuelle."
                                           if parsed_date is None else
                                           "son application dépend aussi des faits établis et des éventuels actes locaux applicables.")
                                    )
                                if rendered_claims and claims:
                                    ai_answer = "\n".join(rendered_claims).strip()
                                    if ai_usage is not None:
                                        ai_usage["outcome"] = (
                                            "ANSWERED_WITH_PARTIAL_VERIFIED_CLAIMS"
                                            if claim_validation.get("partial")
                                            or len(claims) < claim_validation.get("claim_count", len(claims))
                                            else "ANSWERED_WITH_VERIFIED_QUOTES_AND_ENTAILMENT_CHECK"
                                        )
                                else:
                                    ai_answer = None
                                    if ai_usage is not None:
                                        ai_usage["outcome"] = "REJECTED_AMBIGUOUS_SOURCE"
                                    missing.insert(0, "Une source citée n'a pas pu être retrouvée de façon univoque après validation.")
                    else:
                        ai_answer = None
                        missing.insert(
                            0,
                            "Analyse IA suspendue : aucune source juridique exploitable, y compris dans le corpus CGFP local, n'est disponible.",
                        )
                except AIAnalysisRefusedNoSources:
                    ai_answer = None
                    missing.insert(
                        0,
                        "Analyse IA suspendue : aucune source documentaire contenant un extrait non vide n'est disponible. Aucune génération n'a été envoyée au fournisseur.",
                    )
                except AIProviderUnavailable:
                    ai_answer = None
                    # Record a provider attempt even when it fails; token usage remains unknown.
                    if ai_usage is None and settings.ai_api_base_url and settings.ai_model:
                        # The answer-generation event already exists when the later
                        # entailment call fails; its own PROVIDER_ERROR event is
                        # recorded by verify_claim_entailment. Do not overwrite it.
                        ai_usage = {
                            "provider": "gemini" if settings.ai_api_base_url and "generativelanguage.googleapis.com" in settings.ai_api_base_url else "openai_compatible",
                            "model": settings.ai_model[:160],
                            "operation": "answer_generation",
                            "latency_ms": max(0, round((time.perf_counter() - answer_started_at) * 1000)) if answer_started_at is not None else None,
                            "prompt_tokens": None, "completion_tokens": None,
                            "total_tokens": None, "outcome": "PROVIDER_ERROR",
                        }
        # Context-only sources may inform retrieval context, but they cannot
        # ground legal assertions or citations in the final answer.
        claim_sources = [
            source for source in ai_sources
            if source.get("claim_eligible", True) is not False
            and source.get("reference_role") not in {
                "BASELINE_CONTEXT_ONLY", "INTERPRETIVE_CONTEXT_ONLY",
                "GENERAL_PUBLIC_SERVICE_CONTEXT_ONLY", "NON_NORMATIVE_CONTEXT_ONLY",
            }
        ]
        allowed_refs = {s.get("article") for s in claim_sources if s.get("article")}
        allowed_authorities = {
            value for s in claim_sources
            for value in (s.get("official_number"), s.get("source_id"), s.get("case_number"))
            if value
        }
        citation_validation = validate_answer_citations(ai_answer or "", claim_sources)
        if ai_answer and (
            not answer_references_are_grounded(ai_answer, allowed_refs, allowed_authorities)
            or not citation_validation["valid"]
        ):
            ai_answer = None
            if ai_usage is not None:
                ai_usage["outcome"] = "REJECTED_UNGROUNDED"
            missing.insert(
                0,
                "La réponse IA a été bloquée : au moins une référence juridique n'est pas retrouvée à l'identique dans les sources injectées, ou une citation explicite manque.",
            )

        if ai_answer and parsed_date is None and is_ihts_question(request.question):
            missing.append("La délibération de la collectivité et le dispositif local de compensation restent à vérifier.")

        if ai_answer:
            answer = (ai_answer + "\n\n---\nStatut : analyse assistée à partir des sources affichées. "
                "Le snapshot du CGFP est une consolidation documentaire datée du 31 octobre 2026, non une consultation en direct de Légifrance ; il sert aux questions générales et ne reconstitue pas une version historique. Les ressources Service-Public, institutionnelles et professionnelles sont uniquement informatives et ne fondent pas les affirmations juridiques. Les actes locaux restent à vérifier. Le contrôle automatique vérifie l'identifiant de source, la citation et la présence exacte de l'extrait ; il ne certifie pas à lui seul la justesse de l'interprétation juridique. Une validation juridique humaine reste nécessaire.")
        else:
            lines = [
                "Je n'ai pas pu établir une réponse suffisamment fiable à la question précise à partir des éléments retrouvés.",
                "Je préfère vous le signaler plutôt que de recopier des articles de loi ou de présenter une source simplement voisine comme une réponse.",
            ]
            if parsed_date is None:
                if question_intent == "PERSONAL_CASE":
                    lines.append(
                        "L'absence de date des faits n'empêche pas de présenter les règles actuellement documentées. "
                        "Une version historique sera distinguée uniquement si la période concernée est nécessaire pour identifier la rédaction applicable."
                    )
                else:
                    lines.append(
                        "Une date personnelle n'est pas nécessaire pour cette question générale. "
                        "La recherche porte sur les règles actuelles ; une version historique ne sera vérifiée que si elle devient déterminante."
                    )
            if sources:
                lines.append("\nSources retrouvées, à examiner (elles ne constituent pas à elles seules une réponse) :")
                seen_source_ids = set()
                for source in sources[:8]:
                    source_id = str(source.get("source_id") or "")
                    if source_id and source_id in seen_source_ids:
                        continue
                    if source_id:
                        seen_source_ids.add(source_id)
                    title = " ".join(str(source.get("title") or "Source juridique").split())[:250]
                    reference = source.get("article") or source.get("official_number")
                    if reference and str(reference) not in title:
                        title += f" — réf. {reference}"
                    lines.append(f"• {title}")
            else:
                lines.append("Aucune source exploitable n'a été retrouvée pour cette recherche.")
            lines.append(
                "\nAucune conclusion juridique n'est formulée. Vous pouvez préciser le mécanisme ou le point exact "
                "qui vous intéresse ; les sources doivent ensuite être vérifiées au regard de leur version, "
                "de leur champ d'application et, si nécessaire, des règles locales."
            )
            answer = "\n".join(lines)

        # Apply the display filter after legal analysis and validation. The
        # earlier relevance guard already excluded explicitly unrelated sources
        # from the AI evidence set; this final pass controls returned source cards.
        sources = filter_irrelevant_sources_for_display(sources)

        # Keep full texts server-side for checks/analysis, but return only bounded
        # excerpts to the browser and conversation history.
        for source in sources:
            source.pop("full_text", None)
            if isinstance(source.get("text"), str):
                source["text"] = source.get("excerpt") or source["text"][:1800]
        if ai_usage is not None:
            ai_usage_events.append(dict(ai_usage))
        return AskResponse(
            request_id=request_id,
            verification_status="PARTIELLEMENT_VERIFIE" if ai_answer else "NON_VERIFIE",
            answer=answer, sources=sources, missing_information=missing, ai_usage=ai_usage,
            ai_usage_events=ai_usage_events,
            clarification_question=None,
        )
