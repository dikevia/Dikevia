import asyncio
import json
from datetime import date, datetime
from zoneinfo import ZoneInfo
from uuid import uuid4
import logging
import re

from .schemas import AskRequest, AskResponse
from .config import settings
from .cgfp import get_cgfp_article
from .cgfp_relevance import search_cgfp
from .fpt_scope import classify_public_service_scope, is_ihts_relevant_source, is_ihts_question, is_topic_relevant_source
from .legal_validation import validate_snapshot_citation, parse_facts_date
from .ai_provider import analyze_question, verify_claim_entailment, AIAnalysisResult, AIProviderUnavailable, AIAnalysisRefusedNoSources, answer_references_are_grounded, check_provider_availability
from .legifrance import connector as legifrance, LegifranceUnavailable
from .jurisprudence import AdministrativeCaseLawConnector, decision_temporal_status
from .legal_corpus import search_legal_corpus
from .legal_assurance import assess_source_set, validate_answer_citations, validate_claim_evidence
from .local_corpus import search_local_documents
from .article_lookup import missing_direct_article_reference
from .legal_search_plan import build_official_search_query, build_official_search_queries
from .legal_qualification import qualify_legal_question


def should_use_cgfp_snapshot_fallback(
    live_issue: str | None,
    found: dict | None,
    question: str,
) -> bool:
    """Use the bundled dated CGFP snapshot only when live CGFP lookup failed."""
    return bool(
        live_issue and isinstance(found, dict) and found.get("results")
        and any(
            is_ihts_relevant_source(question, hit)
            for hit in found["results"]
        )
    )


case_law_connector = AdministrativeCaseLawConnector(legifrance)
logger = logging.getLogger(__name__)


def _france_today() -> date:
    return datetime.now(ZoneInfo("Europe/Paris")).date()


def classify_question_intent(question: str) -> str:
    """Classify whether the current turn describes an individual event or asks for general rules.

    This is a conservative routing heuristic, not a legal or semantic judgement.
    Only explicit first-person events, decisions or disputes trigger case-date
    clarification; hypothetical employer powers remain general questions.
    """
    text = " ".join(str(question or "").casefold().split())
    if not text:
        return "GENERAL_INFORMATION"

    general_hypothetical_patterns = (
        r"^(?:quels sont|quels seraient|comment connaitre|comment connaître)\s+mes droits\b",
        r"\bsi\s+(?:mon employeur|ma collectivité|un employeur)\s+(?:refuse|rejette|sanctionne|impose)\b",
        r"\b(?:peut-il|peut-elle|est-il possible|dans quels cas)\b",
    )
    if any(re.search(pattern, text) for pattern in general_hypothetical_patterns):
        return "GENERAL_INFORMATION"

    personal_event_patterns = (
        r"\bon ne me (?:paie|paye|compense|donne)\b",
        r"\bon m['’]a (?:refusé|sanctionné|notifié|imposé|retiré|placé|licencié|convoqué)\b",
        r"\bje (?:n['’]ai pas (?:été payé|reçu|touché|obtenu)|ne suis pas payé|ne touche pas|subis)\b",
        r"\bj['’]ai (?:été sanctionné|été licencié|été convoqué|été refusé|reçu|déposé|contesté|effectué)\b",
        r"\b(?:mon employeur|ma collectivité) (?:refuse|ne me paie|ne me paye|m['’]a refusé|m['’]a sanctionné)\b",
        r"\b(?:mon|ma|mes)\s+[\wÀ-ÿ'’-]{2,40}\s+(?:a été|ont été)\s+(?:refusé|refusée|refusés|refusées|retiré|retirée|supprimé|supprimée|notifié|notifiée|rejeté|rejetée|suspendu|suspendue)\b",
        r"\b(?:ma demande|mon congé|mon arrêt|ma rémunération|mon dossier)\b.{0,80}\b(?:refusé|refusée|refusés|refusées|rejeté|rejetée|suspendu|suspendue)\b",
        r"\b(?:j['’]ai reçu|on m['’]a notifié|on m['’]a adressé)\b.{0,80}\b(?:refus|décision|sanction|notification|convocation)\b",
        r"\b(?:dans mon cas|dans ma situation|concernant mon dossier)\b",
        r"\b(?:depuis|à compter du)\s+(?:le\s+)?\d{1,2}[ /-]\d{1,2}\b",
    )
    if any(re.search(pattern, text) for pattern in personal_event_patterns):
        return "PERSONAL_CASE"

    # A question about what an employer may generally do is not evidence that
    # the user has personally received a refusal or decision.
    return "GENERAL_INFORMATION"


def question_needs_case_date(question: str) -> bool:
    """Compatibility wrapper: ask for dates only for explicitly personal cases."""
    return classify_question_intent(question) == "PERSONAL_CASE"

def filter_irrelevant_sources_for_display(sources: list[dict]) -> list[dict]:
    """Exclude sources explicitly classified as unrelated from analysis and display."""
    return [source for source in sources if source.get("ihts_relevant") is not False and source.get("topic_relevant") is not False]


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



class LegalOrchestrator:
    async def ask(self, request: AskRequest, organization_id: str, conn=None, conversation_history: list[dict] | None = None) -> AskResponse:
        request_id = str(uuid4())
        needs_case_date = question_needs_case_date(request.question)
        try:
            legacy_date = parse_facts_date(request.facts_date)
            period_start = parse_facts_date(request.facts_start_date) or legacy_date
            period_end = parse_facts_date(request.facts_end_date)
            if legacy_date and not request.facts_start_date and not request.facts_end_date:
                # Compatibility: the former single-date field describes one exact day.
                period_end = legacy_date
            if request.situation_ongoing and period_end:
                raise ValueError("Une situation déclarée toujours en cours ne peut pas avoir de date de fin.")
            if request.facts_start_date and not request.situation_ongoing and not request.facts_end_date:
                raise ValueError("Indiquez la date de fin de la situation ou cochez « Situation toujours en cours ».")
            if request.facts_end_date and not request.facts_start_date:
                raise ValueError("Indiquez également le début de la situation pour vérifier toute la période.")
            if period_start and period_end and period_end < period_start:
                raise ValueError("La fin de la période ne peut pas précéder son début.")
            effective_date = (
                _france_today() if request.situation_ongoing or not (period_start or period_end)
                else (period_end or period_start)
            )
            # Only an explicitly described situation period authorizes a case-specific
            # temporal conclusion. Today's date without facts is retrieval-only.
            parsed_date = effective_date if (period_start or period_end or request.situation_ongoing) else None
            temporal_context = {
                "period_start": period_start.isoformat() if period_start else None,
                "period_end": period_end.isoformat() if period_end else None,
                "ongoing": bool(request.situation_ongoing),
                "facts_date_provided": parsed_date is not None,
                "analysis_mode": "CASE_SPECIFIC" if parsed_date is not None else "GENERAL_CURRENT_LAW_ONLY",
                "reference_date_for_retrieval": effective_date.isoformat(),
                "legacy_exact_date": bool(legacy_date and not request.facts_start_date and not request.facts_end_date),
            }
        except ValueError as exc:
            return AskResponse(request_id=request_id, verification_status="NON_VERIFIE",
                answer="La période de la situation n'a pas pu être interprétée. Aucune analyse juridique n'est produite.",
                missing_information=[str(exc)])

        history = (conversation_history or [])[-12:]
        prior_user_questions = [str(m.get("content", ""))[:1200] for m in history if m.get("role") == "user"][-3:]
        current_question = request.question.strip()
        legal_context = qualify_legal_question(current_question, request.employer)
        contextual_question = current_question[:500]
        # A short follow-up may depend on the immediately preceding question,
        # but older exchanges must never displace the current request.
        if prior_user_questions and len(current_question) < 220:
            contextual_question = current_question[:350] + "\n" + prior_user_questions[-1][:150]
        # PISTE search methods cap their query at 500 characters. The current
        # question must take precedence over older conversational context.
        research_queries = build_official_search_queries(contextual_question)
        contextual_search_query = build_official_search_query(contextual_question)
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
            try:
                result = await asyncio.to_thread(search_cgfp, contextual_question, limit=8)
                if not isinstance(result, dict):
                    return None, "Index documentaire CGFP indisponible : résultat de recherche non conforme."
                return result, None
            except Exception:
                logger.exception("Échec de la recherche dans l'index structuré du CGFP.")
                return None, "Index documentaire CGFP indisponible ou invalide."

        async def search_official_pillars():
            if not legifrance.configured:
                issue = "Identifiants PISTE non configurés : les recherches officielles Légifrance n'ont pas été exécutées."
                return [], [], [], issue, issue, issue, issue
            try:
                # Refresh OAuth once before the date-scoped searches to avoid token races.
                await legifrance._get_token()
            except LegifranceUnavailable:
                logger.exception("Authentification PISTE indisponible avant la recherche multi-sources.")
                issue = "Authentification PISTE impossible : les recherches officielles n'ont pas pu être exécutées."
                return [], [], [], issue, issue, issue, issue

            comparison_dates = (
                [period_start, effective_date]
                if period_start and period_start < effective_date else [effective_date]
            )
            # Search a bounded set of independent legal axes. Each query is
            # evaluated at every required temporal endpoint; one failed axis
            # must not discard successful results from the others.
            endpoint_results = await asyncio.gather(*[
                asyncio.gather(*[
                    asyncio.gather(
                        legifrance.search_code_articles(query, requested_date),
                        legifrance.search_regulatory_texts(query, requested_date, limit=3),
                        return_exceptions=True,
                    )
                    for query in research_queries
                ])
                for requested_date in comparison_dates
            ])
            code_result, regulatory_result = [], []
            code_failures, regulatory_failures = [], []
            for requested_date, query_results in zip(comparison_dates, endpoint_results):
                endpoint = "START" if requested_date == comparison_dates[0] and len(comparison_dates) > 1 else "END"
                for query, pair in zip(research_queries, query_results):
                    code_at_date, regulatory_at_date = pair
                    if isinstance(code_at_date, BaseException) or not isinstance(code_at_date, list):
                        logger.warning("Recherche code Légifrance en échec (%s) à %s : %r", query[:100], requested_date, code_at_date)
                        code_failures.append((requested_date.isoformat(), query))
                    else:
                        code_result.extend(_tag_official_versions(code_at_date, requested_date, endpoint))
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

            # The broad LODA query can rank unrelated texts above the FPT
            # implementing instrument. For IHTS questions, retrieve decree 91-875
            # by its exact official number at every requested date as well.
            if is_ihts_question(current_question):
                for requested_date in comparison_dates:
                    try:
                        territorial_ihts = await legifrance.search_regulatory_texts(
                            "décret n° 91-875", requested_date, limit=3,
                        )
                        endpoint = "START" if requested_date == comparison_dates[0] and len(comparison_dates) > 1 else "END"
                        regulatory_result.extend(_tag_official_versions(territorial_ihts, requested_date, endpoint))
                    except Exception as exc:
                        logger.warning("Recherche ciblée du décret 91-875 indisponible à %s : %r", requested_date, exc)

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
            case_result = []
            case_search_failed = False
            for query, result in zip(research_queries, case_results):
                if isinstance(result, BaseException) or not isinstance(result, list):
                    logger.warning("Recherche CETAT en échec (%s) : %r", query[:100], result)
                    case_search_failed = True
                else:
                    case_result.extend(result)
            unique_cases = {}
            for source in case_result:
                unique_cases[source.get("source_id") or str(id(source))] = source
            case_result = list(unique_cases.values())
            code_issue = (
                "La recherche d'articles du CGFP sur Légifrance a échoué pour au moins un axe de recherche ou une date de référence."
                if code_failures else None
            )
            regulatory_search_issue = (
                "La recherche des lois, décrets et arrêtés sur Légifrance a échoué pour au moins un axe de recherche ou une date de référence."
                if regulatory_failures else None
            )
            case_search_issue = (
                "La recherche de jurisprudence administrative (fonds CETAT) n'a pas abouti pour au moins un axe."
                if case_search_failed else None
            )
            temporal_issue = None
            if len(comparison_dates) > 1 and (code_failures or regulatory_failures):
                temporal_issue = (
                    "Comparaison temporelle incomplète : Légifrance n'a pas répondu pour les deux bornes "
                    "de la période. Aucune conclusion couvrant toute la période n'est autorisée."
                )
            return (
                code_result, regulatory_result, case_result,
                code_issue, regulatory_search_issue, case_search_issue, temporal_issue,
            )

        # Primary path: query Légifrance/PISTE first for the CGFP, regulatory
        # texts and CETAT case law. Consult the bundled PDF snapshot only when
        # the live CGFP article search is unavailable or fails.
        official_result = await search_official_pillars()
        (
            live_sources, regulatory_sources, case_law_sources,
            live_issue, regulatory_issue, case_law_issue, temporal_issue,
        ) = official_result
        if live_issue:
            found, cgfp_issue = await search_cgfp_index()
        else:
            found, cgfp_issue = None, None
        period_version_comparison = None
        if period_start and period_start < effective_date:
            period_version_comparison = _compare_official_period_versions(
                live_sources, regulatory_sources, period_start, effective_date,
            )
            matched_version_ids = set(period_version_comparison["matched_source_ids"])
            for version_source in [*live_sources, *regulatory_sources]:
                version_source["period_endpoint_match"] = version_source.get("source_id") in matched_version_ids
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
                      for item in case_law_sources[:3] if item.get("source_id")),
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
                    temporal_status = decision_temporal_status(result.get("decision_date"), effective_date)
                    if temporal_status != "DECISION_AVAILABLE_BY_REQUESTED_DATE":
                        logger.warning(
                            "Décision CETAT écartée : date absente, invalide ou postérieure aux faits (source=%s, statut=%s)",
                            result.get("source_id"), temporal_status,
                        )
                        case_law_fulltext_issue = (
                            "Une décision CETAT a été écartée car sa date ne permet pas de vérifier qu'elle était disponible à la date des faits."
                        )
                        continue
                    result["temporal_status"] = temporal_status
                    result["content_kind"] = "FULL_TEXT"
                    scope = classify_public_service_scope(result)
                    result["public_service_scope"] = scope["scope"]
                    result["scope_evidence"] = scope["evidence"]
                    result["analysis_eligible"] = scope["analysis_eligible"]
                    if not scope["analysis_eligible"] or not is_topic_relevant_source(current_question, result):
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
        if request.employer != "NATIONAL":
            if conn is None:
                local_issue = "Les documents propres à l'employeur ne sont pas accessibles dans ce contexte."
            else:
                try:
                    local_sources = await search_local_documents(
                        conn, organization_id, request.employer,
                        contextual_search_query[:500], effective_date, limit=5,
                    )
                    if parsed_date is None:
                        for local_source in local_sources:
                            local_source["temporal_status"] = "TEMPORAL_SCOPE_INCOMPLETE"
                except Exception:
                    logger.exception("Échec de la recherche dans le corpus local tenant-scoped.")
                    local_issue = "La recherche dans les documents de l'employeur n'a pas pu être exécutée."

        permanent_sources: list[dict] = []
        permanent_issue = None
        if conn is not None:
            try:
                stored = await search_legal_corpus(conn, contextual_search_query, effective_date, limit=12)
                for item in stored:
                    permanent_sources.append({
                        "source_type": item.get("source_type"), "source_id": item.get("source_id"),
                        "title": item.get("title"), "official_number": item.get("official_number"),
                        "document_kind": item.get("document_kind"), "jurisdiction": item.get("jurisdiction"),
                        "signature_date": item.get("signature_date"), "publication_date": item.get("publication_date"),
                        "valid_from": item.get("valid_from"), "valid_to": item.get("valid_to"),
                        "temporal_status": item.get("temporal_status"), "source_status": item.get("source_status"),
                        "content_kind": item.get("content_kind"), "excerpt": item.get("excerpt"),
                        "text": item.get("excerpt") or "", "official_url": item.get("official_url"),
                        "official_source": item.get("official_source"),
                        "citation_integrity": item.get("citation_integrity"),
                    })
            except Exception:
                logger.exception("Échec de la recherche dans le corpus juridique national.")
                permanent_issue = "Le corpus juridique permanent n'a pas pu être interrogé."
        else:
            permanent_issue = "Le corpus juridique permanent n'est pas connecté à cette analyse."

        # If the live CGFP article endpoint is unavailable, use the bundled
        # Légifrance PDF/index as a clearly-labelled documentary fallback.
        # It remains a dated snapshot (not proof of the version applicable to
        # the facts); it may accompany independently verified decrees/case law,
        # but must never replace those sources or authorize a standalone opinion.
        cgfp_snapshot_fallback = should_use_cgfp_snapshot_fallback(
            live_issue, found, request.question,
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
            scope_check = classify_public_service_scope(item)
            item["public_service_scope"] = scope_check["scope"]
            item["scope_evidence"] = scope_check["evidence"]
            item["analysis_eligible"] = scope_check["analysis_eligible"]
            item["ihts_relevant"] = is_ihts_relevant_source(request.question, item)
            sources.append({**item, "source_status": "OFFICIAL_API_RESPONSE",
                "temporal_status": (
                    "IN_FORCE_ON_REQUESTED_DATE" if parsed_date is not None
                    else "TEMPORAL_SCOPE_INCOMPLETE"
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
            scope_check = classify_public_service_scope(item)
            item["public_service_scope"] = scope_check["scope"]
            item["scope_evidence"] = scope_check["evidence"]
            item["analysis_eligible"] = scope_check["analysis_eligible"]
            item["ihts_relevant"] = is_ihts_relevant_source(request.question, item)
            sources.append({
                **item,
                "excerpt": item.get("excerpt") or full_text[:1800],
                "text": full_text,
                "content_kind": "FULL_TEXT",
                "temporal_status": (
                    "IN_FORCE_ON_REQUESTED_DATE" if parsed_date is not None
                    else "TEMPORAL_SCOPE_INCOMPLETE"
                ),
                "general_info_eligible": parsed_date is None,
                "citation_integrity": {
                    "valid": bool(item.get("source_id") and len(full_text) >= 80),
                    "verification_scope": "PISTE_LODA_DATE_CONSULT_ID_AND_FULL_TEXT",
                },
            })

        for item in permanent_sources:
            response_source = {**item, "source_url": item.get("official_url")}
            if parsed_date is None:
                response_source["temporal_status"] = "TEMPORAL_SCOPE_INCOMPLETE"
            # Apply the same French FPT perimeter to the permanent corpus as
            # to live Légifrance and CETAT results. Otherwise a stored EU or
            # FPE/FPH document could bypass the live-source scope guard.
            scope_check = classify_public_service_scope(response_source)
            response_source["public_service_scope"] = scope_check["scope"]
            response_source["scope_evidence"] = scope_check["evidence"]
            response_source["analysis_eligible"] = scope_check["analysis_eligible"]
            response_source["ihts_relevant"] = is_ihts_relevant_source(request.question, response_source)
            sources.append(response_source)

        sources.extend(local_sources)

        if found:
            for hit in found["results"]:
                if not is_ihts_relevant_source(request.question, hit):
                    continue
                article = get_cgfp_article(hit["article"])
                citation = {"source_id": hit["source_id"], "article": hit["article"],
                    "page_start": hit["page_start"], "page_end": hit["page_end"], "excerpt": hit["excerpt"]}
                integrity = validate_snapshot_citation(citation, article or {})
                if integrity["valid"]:
                    sources.append({"source_type": "CGFP_SNAPSHOT", "source_id": hit["source_id"],
                        "title": f"Code général de la fonction publique — article {hit['article']}",
                        "article": hit["article"], "page_start": hit["page_start"], "page_end": hit["page_end"],
                        "excerpt": hit["excerpt"], "text": (article or {}).get("text", ""),
                        "content_kind": "SNAPSHOT_EXCERPT",
                        "snapshot_modified_at": found["source"]["snapshot_modified_at"],
                        "source_status": found["source"]["verification_status"],
                        "citation_integrity": integrity, "document": found["source"]["source_file"]})

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
            scope_check = classify_public_service_scope(decision)
            decision["public_service_scope"] = scope_check["scope"]
            decision["scope_evidence"] = scope_check["evidence"]
            decision["analysis_eligible"] = scope_check["analysis_eligible"]
            decision["ihts_relevant"] = is_ihts_relevant_source(request.question, decision)
            sources.append({**decision, "page_start": None, "page_end": None})

        # Apply the topic guard only after every source family (including the
        # CGFP snapshot and CETAT full text) has been collected.
        for source in sources:
            source["topic_relevant"] = is_topic_relevant_source(request.question, source)

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
            s for s in sources
            if s.get("source_id") in permanent_source_ids
            and s.get("content_kind") == "FULL_TEXT"
            and (s.get("citation_integrity") or {}).get("valid") is True
            and s.get("temporal_status") in {"IN_FORCE_ON_REQUESTED_DATE", "DECISION_AVAILABLE_BY_REQUESTED_DATE"}
            and s.get("analysis_eligible") is True
            and s.get("ihts_relevant") is not False
        ]
        usable_official = [
            s for s in sources
            if s.get("source_type") in {
                "LEGIFRANCE_API", "LEGIFRANCE_LODA", "LEGIFRANCE_CETAT_FULL_TEXT",
            }
            and s.get("content_kind") != "METADATA"
            and (s.get("citation_integrity") or {}).get("valid") is True
            and s.get("analysis_eligible") is True
            and s.get("ihts_relevant") is not False
        ]
        usable_local = [s for s in local_sources
            if (s.get("citation_integrity") or {}).get("valid") is True
            and s.get("temporal_status") == "VERIFIED_APPLICABLE"]
        if not usable_official and not usable_permanent and not usable_local:
            missing = ["Aucune disposition législative ou réglementaire exploitable n'a été récupérée.",
                "Recherche officielle Légifrance/PISTE et vérification des textes réglementaires complémentaires.",
                "Recherche de jurisprudence pertinente et vérification des sources locales applicables."]
            if parsed_date is not None:
                missing.insert(0, f"Date des faits déclarée : {effective_date.isoformat()}.")
            elif needs_case_date:
                missing.insert(0, "Date des faits / période non précisée : une analyse contextualisée ne peut pas déterminer la règle applicable.")
                missing.insert(1, "La date d'entrée en vigueur des dispositions applicables sera recherchée séparément dans les versions officielles de Légifrance ; elle n'est pas demandée à l'utilisateur.")
            if permanent_issue:
                missing.insert(0, permanent_issue)
            if cgfp_issue:
                missing.insert(0, cgfp_issue)
            missing.insert(0, "Le snapshot CGFP seul, lorsqu'il existe, reste un repère documentaire et ne peut pas justifier une analyse IA contextualisée.")
            if local_issue:
                missing.insert(0, local_issue)
            elif request.employer != "NATIONAL" and not local_sources:
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
                answer=(
                    "La date ou la période des faits n'est pas renseignée. La recherche au jour présent sert uniquement au repérage documentaire ; "
                    "les textes officiels récupérés ne permettent pas de répondre avec certitude et aucune conclusion juridique contextualisée n'est formulée."
                    if parsed_date is None and needs_case_date else
                    "Les textes officiels actuels ne me permettent pas de répondre avec certitude sur ce point précis. Aucune conclusion juridique n'est formulée."
                ),
                sources=sources,
                missing_information=missing,
                clarification_question=(
                    "À quelle date les faits se sont-ils produits, ou sur quelle période s'étendent-ils ?"
                    if parsed_date is None and needs_case_date else None
                ),
            )

        missing = ["Vérifier les dates d'effet et la rédaction exacte applicable à la date des faits.",
            "Vérifier les dispositions réglementaires, décrets et textes spéciaux liés à la question.",
            "Rechercher et vérifier la jurisprudence pertinente si elle peut modifier l'analyse.",
            "Vérifier les actes locaux, délibérations et accords applicables à l'employeur concerné."]
        if permanent_issue:
            missing.insert(0, permanent_issue)
        if cgfp_issue:
            missing.insert(0, cgfp_issue)
        if local_issue:
            missing.insert(0, local_issue)
        elif request.employer != "NATIONAL" and not local_sources:
            missing.insert(0, "Aucun document local correspondant n'a été trouvé pour cet employeur ; vérifier le code de collectivité et les pièces déposées.")
        if any(s.get("source_type") == "LOCAL_DOCUMENT" and s.get("temporal_status") != "VERIFIED_APPLICABLE"
               for s in local_sources):
            missing.insert(0, "Des documents locaux correspondent à la recherche mais leur validation humaine ou leur période d'effet ne permet pas de les utiliser pour une conclusion.")
        if any(s.get("content_kind") == "METADATA" for s in permanent_sources):
            missing.insert(0, "Certaines circulaires ou textes ne sont présents qu'au stade des métadonnées : ils ne sont pas utilisés pour produire une analyse IA.")
        if any(s.get("temporal_status") == "TEMPORAL_SCOPE_INCOMPLETE" for s in permanent_sources):
            missing.insert(0, "Des versions du corpus ont des dates d'effet incomplètes : elles sont signalées mais exclues des conclusions IA.")
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
        if case_law_sources and not case_law_full_text_sources:
            missing.insert(0, "Les résultats CETAT restent des métadonnées : aucun texte intégral de décision n'est utilisé pour l'analyse IA.")
        if not case_law_sources and not case_law_issue:
            missing.insert(0, "La recherche CETAT a été exécutée sans retrouver de décision pertinente pour cette requête.")
        if temporal_context["period_start"] or temporal_context["period_end"]:
            missing.insert(0, f"Période déclarée : du {temporal_context['period_start'] or 'début non précisé'} au {temporal_context['period_end'] or ('aujourd’hui' if temporal_context['ongoing'] else 'fin non précisée')}.")
        elif not temporal_context["ongoing"] and needs_case_date:
            missing.insert(0, f"Date des faits / période de la situation non précisée : Légifrance est interrogé au {effective_date.isoformat()} à titre de repérage documentaire uniquement.")
            missing.insert(1, "La date d'entrée en vigueur des dispositions applicables sera recherchée séparément dans les versions officielles de Légifrance ; elle n'est pas demandée à l'utilisateur.")
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
                "La jurisprudence CETAT a été recherchée à la date de référence de fin de période ; "
                "son évolution historique sur toute la période n'est pas établie par cette seule recherche."
            ))

        ai_sources: list[dict] = []
        ai_usage = None
        if cgfp_issue or (live_issue and not cgfp_snapshot_fallback) or regulatory_issue or case_law_issue or temporal_issue:
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
                        "Le modèle IA configuré est désactivé par le fournisseur : son activation exige une offre payante. Aucune inférence n'a été envoyée ; la réponse reste documentaire.",
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
                        "VERIFIED_APPLICABLE",
                    }
                    # The CGFP snapshot is the national baseline for explanation, but
                    # it is not temporally authoritative. Pass it to the model only
                    # alongside at least one independently verified, date-scoped
                    # source; never let the snapshot alone trigger an AI conclusion.
                    verified_sources = [
                        s for s in sources
                        if s.get("source_type") not in {"LEGIFRANCE_CETAT_SEARCH", "CGFP_SNAPSHOT"}
                        and s.get("topic_relevant") is not False
                        and s.get("content_kind") != "METADATA"
                        and (s.get("citation_integrity") or {}).get("valid") is True
                        and (
                            s.get("temporal_status") in eligible_temporal_statuses
                            or (
                                s.get("temporal_status") == "TEMPORAL_SCOPE_INCOMPLETE"
                                and s.get("general_info_eligible") is True
                            )
                        )
                        # Unknown scope is retained as a review lead; only
                        # explicitly identified FPE/FPH sources are excluded.
                        # The AI prompt receives this scope and must not infer
                        # territorial applicability from an unknown classification.
                        and (
                            s.get("analysis_eligible") is True
                            or (
                                s.get("source_type") == "LOCAL_DOCUMENT"
                                and s.get("validation_status") == "VERIFIED_APPLICABLE"
                            )
                        )
                        and s.get("ihts_relevant") is not False
                        and (
                            not period_version_comparison
                            or (
                                s.get("source_type") in {"LEGIFRANCE_API", "LEGIFRANCE_LODA"}
                                and s.get("period_endpoint_match") is True
                            )
                            or (
                                s.get("source_type") not in {
                                    "LEGIFRANCE_API", "LEGIFRANCE_LODA",
                                    "LEGIFRANCE_CETAT_FULL_TEXT", "LEGIFRANCE_CETAT_SEARCH",
                                }
                                and _source_covers_period(s, period_start, effective_date)
                            )
                        )
                    ]
                    cgfp_context_sources = [
                        {**s, "reference_role": "BASELINE_CONTEXT_ONLY",
                         "temporal_status": "SNAPSHOT_ONLY_NOT_TEMPORALLY_VERIFIED"}
                        for s in sources
                        if s.get("source_type") == "CGFP_SNAPSHOT"
                        and s.get("topic_relevant") is not False
                        and (s.get("citation_integrity") or {}).get("valid") is True
                    ]
                    ai_sources = cgfp_context_sources + verified_sources if verified_sources else []
                    if ai_sources:
                        ai_result = await analyze_question(
                            question=request.question,
                            employer=request.employer,
                            facts_date=effective_date.isoformat(),
                            facts_period=temporal_context,
                            sources=ai_sources,
                            conversation_history=history,
                            legal_context=legal_context,
                        )
                        if isinstance(ai_result, AIAnalysisResult):
                            raw_ai_content = ai_result.content
                            ai_usage = {
                                "provider": "openai_compatible", "model": ai_result.model,
                                "prompt_tokens": ai_result.prompt_tokens,
                                "completion_tokens": ai_result.completion_tokens,
                                "total_tokens": ai_result.total_tokens,
                                "outcome": "STRUCTURED_OUTPUT_RECEIVED",
                            }
                        else:
                            # All providers and test adapters must use the same strict JSON contract.
                            raw_ai_content = ai_result
                        try:
                            structured_answer = json.loads(raw_ai_content) if isinstance(raw_ai_content, str) else None
                        except (TypeError, ValueError):
                            structured_answer = None
                        claim_validation = validate_claim_evidence(structured_answer, ai_sources)
                        if not claim_validation["valid"]:
                            ai_answer = None
                            if ai_usage is not None:
                                ai_usage["outcome"] = "REJECTED_UNSUPPORTED_CLAIMS"
                            missing.insert(
                                0,
                                "La réponse IA a été bloquée : sortie structurée absente ou affirmation sans citation exacte dans une source officielle applicable.",
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
                                question=request.question,
                                claims=claim_validation["claims"], sources=ai_sources,
                            )
                            if not entailment_validation.get("valid"):
                                ai_answer = None
                                if ai_usage is not None:
                                    ai_usage["outcome"] = "REJECTED_UNSUPPORTED_ENTAILMENT"
                                missing.insert(
                                    0,
                                    "La réponse IA a été bloquée : le contrôle contradictoire n'a pas confirmé que chaque proposition découle directement de son passage officiel. Aucune conclusion n'est formulée.",
                                )
                            else:
                                claims = claim_validation["claims"]
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
                                rendered_claims.extend([
                                    "",
                                    (
                                        f"Cette réponse porte sur les règles consultées au {effective_date.isoformat()} ; elle ne constitue pas une conclusion sur une situation individuelle."
                                        if parsed_date is None
                                        else f"Cette analyse prend pour date de référence le {effective_date.isoformat()} ; son application dépend aussi des faits établis et des éventuels actes locaux applicables."
                                    ),
                                ])
                                if rendered_claims and claims:
                                    ai_answer = "\n".join(rendered_claims).strip()
                                    if ai_usage is not None:
                                        ai_usage["outcome"] = "ANSWERED_WITH_VERIFIED_QUOTES_AND_ENTAILMENT_CHECK"
                                else:
                                    ai_answer = None
                                    if ai_usage is not None:
                                        ai_usage["outcome"] = "REJECTED_AMBIGUOUS_SOURCE"
                                    missing.insert(0, "Une source citée n'a pas pu être retrouvée de façon univoque après validation.")
                    else:
                        ai_answer = None
                        missing.insert(
                            0,
                            "Analyse IA suspendue : aucune source officielle datée et exploitable n'est disponible. Le snapshot CGFP seul reste une piste documentaire.",
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
                    if settings.ai_api_base_url and settings.ai_model:
                        ai_usage = {
                            "provider": "openai_compatible", "model": settings.ai_model[:160],
                            "prompt_tokens": None, "completion_tokens": None,
                            "total_tokens": None, "outcome": "PROVIDER_ERROR",
                        }
        # Ground generated references only against sources actually supplied to
        # the model, never against excluded snapshot or metadata-only results.
        allowed_refs = {s.get("article") for s in ai_sources if s.get("article")}
        allowed_authorities = {
            value for s in ai_sources
            for value in (s.get("official_number"), s.get("source_id"), s.get("case_number"))
            if value
        }
        citation_validation = validate_answer_citations(ai_answer or "", ai_sources)
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

        if ai_answer and parsed_date is None and needs_case_date:
            if is_ihts_question(request.question):
                missing.extend([
                    "La date ou la période des heures effectuées reste à préciser pour vérifier la version applicable aux faits.",
                    "La délibération de la collectivité et le dispositif local de compensation restent à vérifier.",
                ])
            else:
                missing.append(
                    "La date ou la période des faits reste à préciser pour vérifier la version des règles applicable à votre situation personnelle."
                )

        if ai_answer:
            # Append practical guidance only after the legal-claim citation validator.
            # These are clearly framed as next steps, not legal claims requiring a
            # documentary quotation; they must not cause supported claims to be rejected.
            if any(source.get("ihts_relevant") is True for source in ai_sources):
                ai_answer += (
                    "\n\nDémarches utiles :"
                    "\n• Conservez le relevé des heures réellement effectuées et les éléments montrant qu'elles ont été demandées ou validées."
                    "\n• Demandez à votre service RH quel dispositif de compensation s'applique (indemnisation ou repos) et quelle délibération locale le prévoit."
                    "\n• Si la réponse ne correspond pas aux textes ou aux pièces de votre situation, faites examiner le dossier par un référent juridique ou un représentant syndical."
                )
            else:
                ai_answer += (
                    "\n\nPour aller plus loin, rassemblez les documents utiles à votre situation et demandez à votre service RH ou à votre référent compétent de préciser la règle appliquée. Vous pouvez me donner les éléments manquants et je poursuivrai l'analyse avec vous."
                )
            answer = (ai_answer + "\n\n---\nStatut : analyse assistée à partir des sources affichées. "
                "Les extraits du snapshot PDF ne certifient pas l'authenticité officielle. Les versions du corpus dont les dates d'effet sont incomplètes ne sont pas utilisées pour les conclusions IA. Les actes locaux restent à vérifier. Le contrôle automatique vérifie l'identifiant de source, la citation et la présence exacte de l'extrait ; il ne certifie pas à lui seul la justesse de l'interprétation juridique. Une validation juridique humaine reste nécessaire.")
        else:
            lines = [
                "Je n'ai pas pu établir une réponse suffisamment fiable à la question précise à partir des éléments retrouvés.",
                "Je préfère vous le signaler plutôt que de recopier des articles de loi ou de présenter une source simplement voisine comme une réponse.",
            ]
            if parsed_date is None and needs_case_date:
                lines.append(
                    "Pour poursuivre l'analyse de votre situation, indiquez la date ou la période des faits."
                )
            elif parsed_date is None:
                lines.append(
                    "Il s'agit ici d'une question générale : une date personnelle n'est pas nécessaire. "
                    "Le point à résoudre est l'identification d'une disposition qui répond directement à votre question."
                )
            if sources:
                lines.append("\\nSources retrouvées, à examiner (elles ne constituent pas à elles seules une réponse) :")
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
                "\\nAucune conclusion juridique n'est formulée. Vous pouvez préciser le mécanisme ou le point exact "
                "qui vous intéresse ; les sources doivent ensuite être vérifiées au regard de leur version, "
                "de leur champ d'application et, si nécessaire, des règles locales."
            )
            answer = "\n".join(lines)

        # Apply display-only filtering after legal analysis and validation. Keeping
        # every retrieved source available until this point prevents unrelated-topic
        # heuristics from changing the evidence set or verification status.
        sources = filter_irrelevant_sources_for_display(sources)

        # Keep full texts server-side for checks/analysis, but return only bounded
        # excerpts to the browser and conversation history.
        for source in sources:
            source.pop("full_text", None)
            if isinstance(source.get("text"), str):
                source["text"] = source.get("excerpt") or source["text"][:1800]
        return AskResponse(
            request_id=request_id,
            verification_status="PARTIELLEMENT_VERIFIE" if ai_answer else "NON_VERIFIE",
            answer=answer, sources=sources, missing_information=missing, ai_usage=ai_usage,
            clarification_question=(
                "Quand les faits se sont-ils produits ? Une date ou une période approximative suffit ; précisez aussi si la situation est toujours en cours."
                if parsed_date is None and needs_case_date else None
            ),
        )
