import asyncio
from datetime import date
from uuid import uuid4
import logging

from .schemas import AskRequest, AskResponse
from .config import settings
from .cgfp import get_cgfp_article
from .cgfp_relevance import search_cgfp
from .fpt_scope import classify_public_service_scope, is_ihts_relevant_source
from .legal_validation import validate_snapshot_citation, parse_facts_date
from .ai_provider import analyze_question, AIAnalysisResult, AIProviderUnavailable, answer_references_are_grounded
from .legifrance import connector as legifrance, LegifranceUnavailable
from .jurisprudence import AdministrativeCaseLawConnector
from .legal_corpus import search_legal_corpus
from .legal_assurance import assess_source_set, validate_answer_citations
from .local_corpus import search_local_documents


case_law_connector = AdministrativeCaseLawConnector(legifrance)
logger = logging.getLogger(__name__)


class LegalOrchestrator:
    async def ask(self, request: AskRequest, organization_id: str, conn=None, conversation_history: list[dict] | None = None) -> AskResponse:
        request_id = str(uuid4())
        try:
            parsed_date = parse_facts_date(request.facts_date)
            effective_date = parsed_date or date.today()
        except ValueError as exc:
            return AskResponse(request_id=request_id, verification_status="NON_VERIFIE",
                answer="La date des faits n'a pas pu être interprétée. Aucune analyse juridique n'est produite.",
                missing_information=[str(exc)])

        history = (conversation_history or [])[-12:]
        prior_user_questions = [str(m.get("content", ""))[:1200] for m in history if m.get("role") == "user"][-3:]
        current_question = request.question.strip()
        contextual_question = current_question[:500]
        # A short follow-up may depend on the immediately preceding question,
        # but older exchanges must never displace the current request.
        if prior_user_questions and len(current_question) < 220:
            contextual_question = current_question[:350] + "\n" + prior_user_questions[-1][:150]
        # PISTE search methods cap their query at 500 characters. The current
        # question must take precedence over older conversational context.
        live_query = current_question[:500]
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
                return result, None
            except (FileNotFoundError, OSError, ValueError):
                logger.exception("Échec de la recherche dans l'index structuré du CGFP.")
                return None, "Index documentaire CGFP indisponible ou invalide."

        async def search_official_pillars():
            if not legifrance.configured:
                return (
                    [], [], [],
                    "Identifiants PISTE non configurés : la recherche officielle d'articles du CGFP n'a pas été exécutée.",
                    "Identifiants PISTE non configurés : la recherche des textes réglementaires n'a pas été exécutée.",
                    "Identifiants PISTE non configurés : la recherche de jurisprudence CETAT n'a pas été exécutée.",
                )
            try:
                # Obtain one OAuth token before launching the three independent searches.
                # This avoids concurrent token refresh races while keeping the searches parallel.
                await legifrance._get_token()
            except LegifranceUnavailable:
                logger.exception("Authentification PISTE indisponible avant la recherche multi-sources.")
                issue = "Authentification PISTE impossible : les trois recherches officielles n'ont pas pu être exécutées."
                return [], [], [], issue, issue, issue

            results = await asyncio.gather(
                legifrance.search_code_articles(live_query, effective_date),
                legifrance.search_regulatory_texts(live_query, effective_date, limit=3),
                case_law_connector.search(live_query, effective_date),
                return_exceptions=True,
            )
            code_result, regulatory_result, case_result = results
            code_issue = None
            regulatory_search_issue = None
            case_search_issue = None
            if isinstance(code_result, BaseException):
                logger.error("Recherche Légifrance CGFP en échec.", exc_info=code_result)
                code_issue = "La recherche d'articles du CGFP sur Légifrance a échoué."
                code_result = []
            if isinstance(regulatory_result, BaseException):
                logger.error("Recherche Légifrance des textes réglementaires en échec.", exc_info=regulatory_result)
                regulatory_search_issue = "La recherche des lois, décrets et arrêtés complémentaires sur Légifrance a échoué."
                regulatory_result = []
            if isinstance(case_result, BaseException):
                logger.error("Recherche de jurisprudence CETAT en échec.", exc_info=case_result)
                case_search_issue = "La recherche de jurisprudence administrative (fonds CETAT) n'a pas abouti."
                case_result = []
            return (
                code_result, regulatory_result, case_result,
                code_issue, regulatory_search_issue, case_search_issue,
            )

        # CGFP index + the three official search pillars are launched together.
        cgfp_result, official_result = await asyncio.gather(
            search_cgfp_index(),
            search_official_pillars(),
        )
        found, cgfp_issue = cgfp_result
        (
            live_sources, regulatory_sources, case_law_sources,
            live_issue, regulatory_issue, case_law_issue,
        ) = official_result

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
                        logger.warning("Consultation intégrale CETAT indisponible.", exc_info=result)
                        case_law_fulltext_issue = (
                            "Au moins une décision CETAT n'a pas pu être consultée en texte intégral ; "
                            "son résultat de recherche reste une métadonnée non probante."
                        )
                        continue
                    try:
                        decision_date = date.fromisoformat(str(result.get("decision_date") or "")[:10])
                    except ValueError:
                        decision_date = None
                    result["temporal_status"] = (
                        "DECISION_AVAILABLE_BY_REQUESTED_DATE"
                        if decision_date is not None and decision_date <= effective_date
                        else "TEMPORAL_SCOPE_INCOMPLETE"
                    )
                    result["content_kind"] = "FULL_TEXT"
                    result["citation_integrity"] = {
                        "valid": bool(result.get("source_id") and len(result.get("text") or "") >= 80),
                        "verification_scope": "PISTE_CETAT_CONSULT_ID_AND_FULL_TEXT",
                    }
                    if result["citation_integrity"]["valid"]:
                        case_law_full_text_sources.append(result)
                    else:
                        case_law_fulltext_issue = (
                            "Une décision CETAT consultée n'a pas satisfait le contrôle d'identifiant et de texte intégral."
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
                        contextual_question[:500], effective_date, limit=5,
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
                stored = await search_legal_corpus(conn, contextual_question, effective_date, limit=12)
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

        sources: list[dict] = []
        # Official API articles have priority, and are included only after a successful
        # search -> getArticle round-trip with matching LEGIARTI identifier and text.
        for item in live_sources:
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
                "page_start": None, "page_end": None,
                "citation_integrity": {"valid": True, "verification_scope": "PISTE_CODE_DATE_ID_AND_TEXT_PRESENT"}})

        for item in regulatory_sources:
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
                "citation_integrity": {
                    "valid": bool(item.get("source_id") and len(full_text) >= 80),
                    "verification_scope": "PISTE_LODA_DATE_CONSULT_ID_AND_FULL_TEXT",
                },
            })

        for item in permanent_sources:
            response_source = {**item, "source_url": item.get("official_url")}
            if parsed_date is None:
                response_source["temporal_status"] = "TEMPORAL_SCOPE_INCOMPLETE"
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
                        "snapshot_modified_at": found["source"]["snapshot_modified_at"],
                        "source_status": found["source"]["verification_status"],
                        "citation_integrity": integrity, "document": found["source"]["source_file"]})

        for decision in case_law_sources:
            sources.append({
                **decision,
                "page_start": None,
                "page_end": None,
                "citation_integrity": {
                    "valid": True,
                    "verification_scope": "OFFICIAL_SEARCH_RESULT_ID_ONLY",
                },
            })

        usable_permanent = [s for s in permanent_sources if s.get("content_kind") == "FULL_TEXT"
            and (s.get("citation_integrity") or {}).get("valid")
            and s.get("temporal_status") in {"IN_FORCE_ON_REQUESTED_DATE", "DECISION_AVAILABLE_BY_REQUESTED_DATE"}]
        usable_local = [s for s in local_sources
            if (s.get("citation_integrity") or {}).get("valid") is True
            and s.get("temporal_status") == "VERIFIED_APPLICABLE"]
        if not any(s.get("source_type") in {"LEGIFRANCE_API", "LEGIFRANCE_LODA", "CGFP_SNAPSHOT"} for s in sources) and not usable_permanent and not usable_local:
            missing = ["Aucune disposition législative ou réglementaire exploitable n'a été récupérée.",
                "Recherche officielle Légifrance/PISTE et vérification des textes réglementaires complémentaires.",
                "Recherche de jurisprudence pertinente et vérification des sources locales applicables."]
            if permanent_issue:
                missing.insert(0, permanent_issue)
            if local_issue:
                missing.insert(0, local_issue)
            elif request.employer != "NATIONAL" and not local_sources:
                missing.insert(0, "Aucun document local correspondant n'a été trouvé pour cet employeur ; vérifier le code de collectivité et les pièces déposées.")
            if live_issue:
                missing.insert(0, live_issue)
            if regulatory_issue:
                missing.insert(0, regulatory_issue)
            if case_law_issue:
                missing.insert(0, case_law_issue)
            if not found:
                missing.insert(0, "Index documentaire CGFP indisponible ou invalide.")
            return AskResponse(request_id=request_id, verification_status="NON_VERIFIE",
                answer="Aucune source exploitable n'a été récupérée et contrôlée pour cette question. JURIS ne formule donc pas de conclusion juridique.",
                sources=sources, missing_information=missing)

        missing = ["Vérifier les dates d'effet et la rédaction exacte applicable à la date des faits.",
            "Vérifier les dispositions réglementaires, décrets et textes spéciaux liés à la question.",
            "Rechercher et vérifier la jurisprudence pertinente si elle peut modifier l'analyse.",
            "Vérifier les actes locaux, délibérations et accords applicables à l'employeur concerné."]
        if permanent_issue:
            missing.insert(0, permanent_issue)
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
        if live_issue:
            missing.insert(0, live_issue)
        if regulatory_issue:
            missing.insert(0, regulatory_issue)
        if case_law_issue:
            missing.insert(0, case_law_issue)
        if case_law_sources:
            missing.insert(0, "Les résultats CETAT sont des métadonnées/extraits de recherche ; le texte intégral des décisions n'a pas été récupéré ni contrôlé.")
        if request.facts_date:
            missing.insert(0, f"Date des faits demandée : {request.facts_date}.")
        else:
            missing.insert(0, f"Date des faits absente : interrogation Légifrance effectuée au {effective_date.isoformat()} à titre de repérage seulement.")

        # A search performed at today's date is not a substitute for the date of
        # the facts. Without facts_date, keep the response at documentary-triage
        # level and do not ask the model to produce a case-specific legal analysis.
        # This prevents a current API result or a consolidated PDF snapshot from
        # being silently treated as the law applicable to an undated situation.
        ai_sources: list[dict] = []
        ai_usage = None
        if parsed_date is None:
            ai_answer = None
            missing.insert(0, "Analyse juridique contextualisée suspendue : préciser la date des faits pour vérifier la version applicable. La date du jour n'est utilisée que pour le repérage documentaire.")
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
                    and s.get("content_kind") != "METADATA"
                    and (s.get("citation_integrity") or {}).get("valid") is True
                    and s.get("temporal_status") in eligible_temporal_statuses
                    # Unknown scope is retained as a review lead; only
                    # explicitly identified FPE/FPH sources are excluded.
                    # The AI prompt receives this scope and must not infer
                    # territorial applicability from an unknown classification.
                    and (
                        s.get("analysis_eligible") is not False
                        or s.get("public_service_scope") == "SCOPE_TO_VERIFY"
                    )
                    and s.get("ihts_relevant") is not False
                ]
                cgfp_context_sources = [
                    {**s, "reference_role": "BASELINE_CONTEXT_ONLY",
                     "temporal_status": "SNAPSHOT_ONLY_NOT_TEMPORALLY_VERIFIED"}
                    for s in sources
                    if s.get("source_type") == "CGFP_SNAPSHOT"
                    and (s.get("citation_integrity") or {}).get("valid") is True
                ]
                ai_sources = cgfp_context_sources + verified_sources if verified_sources else []
                if ai_sources:
                    ai_result = await analyze_question(
                        question=request.question,
                        employer=request.employer,
                        facts_date=request.facts_date,
                        sources=ai_sources,
                        conversation_history=history,
                    )
                    if isinstance(ai_result, AIAnalysisResult):
                        ai_answer = ai_result.content
                        ai_usage = {
                            "provider": "openai_compatible", "model": ai_result.model,
                            "prompt_tokens": ai_result.prompt_tokens,
                            "completion_tokens": ai_result.completion_tokens,
                            "total_tokens": ai_result.total_tokens,
                            "outcome": "ANSWERED",
                        }
                    else:
                        # Keep test doubles and alternate adapters returning plain strings compatible.
                        ai_answer = ai_result
                else:
                    ai_answer = None
                    missing.insert(
                        0,
                        "Analyse IA suspendue : aucune source officielle datée et exploitable n'est disponible. Le snapshot CGFP seul reste une piste documentaire.",
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
        if ai_answer and not answer_references_are_grounded(ai_answer, allowed_refs, allowed_authorities):
            ai_answer = None
            if ai_usage is not None:
                ai_usage["outcome"] = "REJECTED_UNGROUNDED"
            missing.insert(0, "Une référence d'article générée n'était pas présente dans les sources récupérées ; la réponse IA a été écartée.")

        if ai_answer:
            answer = (ai_answer + "\n\n---\nStatut : analyse assistée à partir des sources affichées. "
                "Les extraits du snapshot PDF ne certifient pas l'authenticité officielle. Les versions du corpus dont les dates d'effet sont incomplètes ne sont pas utilisées pour les conclusions IA. Les actes locaux restent à vérifier. Une validation juridique humaine reste nécessaire.")
        else:
            lines = ["Recherche documentaire effectuée. Les résultats ci-dessous sont des sources à examiner, pas une qualification juridique définitive."]
            if parsed_date is None:
                lines.append("Date des faits non fournie : la date du jour sert uniquement au repérage documentaire. Aucune analyse juridique contextualisée n'est produite avant clarification de cette date.")
            for source in sources[:8]:
                excerpt = source.get("excerpt") or source.get("text", "")[:1800]
                location = (f"pages PDF {source['page_start']}–{source['page_end']}" if source.get("page_start") else "réponse API Légifrance")
                lines.append(f"\n{source.get('title', 'Source juridique')} ({location}) :\n{excerpt}")
            lines.append("\nAucune conclusion définitive n'est formulée. Vérifier les versions, les textes d'application, la jurisprudence et les règles locales avant toute utilisation syndicale ou administrative.")
            answer = "\n".join(lines)

        sources = assess_source_set(sources)["sources"]
        # Keep full texts server-side for checks/analysis, but return only bounded
        # excerpts to the browser and conversation history.
        for source in sources:
            source.pop("full_text", None)
            if isinstance(source.get("text"), str):
                source["text"] = source.get("excerpt") or source["text"][:1800]
        return AskResponse(request_id=request_id, verification_status="PARTIELLEMENT_VERIFIE",
            answer=answer, sources=sources, missing_information=missing, ai_usage=ai_usage)
