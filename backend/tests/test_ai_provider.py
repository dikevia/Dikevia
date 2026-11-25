import json

import pytest
from app.ai_provider import analyze_question, plan_legal_research, _parse_research_plan, SYSTEM_PROMPT, answer_references_are_grounded, _nonnegative_token_count, check_provider_availability, AIAnalysisRefusedNoSources
from app.config import settings

@pytest.mark.asyncio
async def test_ai_provider_is_disabled_without_credentials(monkeypatch):
    monkeypatch.setattr(settings, "ai_api_key", "")
    monkeypatch.setattr(settings, "ai_model", "")
    assert await analyze_question(question="Question suffisamment longue", employer="NATIONAL",
        facts_date=None, sources=[]) is None

def test_source_relevance_verdict_validation_accepts_only_known_ids_and_labels():
    from app.ai_provider import validate_source_relevance_verdicts

    sources = [{"source_id": "a"}, {"source_id": "b"}]
    parsed = {"items": [
        {"source_id": "a", "verdict": "DIRECT"},
        {"source_id": "b", "verdict": "IRRELEVANT"},
        {"source_id": "invented", "verdict": "DIRECT"},
        {"source_id": "a", "verdict": "IRRELEVANT"},
        {"source_id": "b", "verdict": "APPLICABLE"},
    ]}
    assert validate_source_relevance_verdicts(parsed, sources) == {
        "a": "DIRECT", "b": "IRRELEVANT"
    }


def test_source_relevance_verdict_validation_rejects_malformed_payloads():
    from app.ai_provider import validate_source_relevance_verdicts

    assert validate_source_relevance_verdicts(None, [{"source_id": "a"}]) == {}
    assert validate_source_relevance_verdicts(
        {"items": [{"source_id": "a", "verdict": "APPLICABLE"}]},
        [{"source_id": "a"}],
    ) == {}


def test_system_prompt_enforces_closed_book_sources_and_prompt_injection_defense():
    assert "POLITIQUE STRICTE DE FENÊTRE FERMÉE" in SYSTEM_PROMPT
    assert "ne dois jamais répondre de mémoire" in SYSTEM_PROMPT
    assert "extraits documentaires explicitement fournis" in SYSTEM_PROMPT
    assert "N'ajoute aucun fait" in SYSTEM_PROMPT
    assert "Une métadonnée ou un résultat de recherche de jurisprudence n'est jamais le texte d'une décision" in SYSTEM_PROMPT
    assert "Une pièce locale ne peut soutenir une conclusion que si elle est validée" in SYSTEM_PROMPT
    assert "CITATIONS OBLIGATOIRES" in SYSTEM_PROMPT
    assert "FORMAT DE SORTIE OBLIGATOIRE" in SYSTEM_PROMPT
    assert "MODE D'INFORMATION GÉNÉRALE" in SYSTEM_PROMPT
    assert "Ne bloque pas la recherche au seul motif que la date des faits manque" in SYSTEM_PROMPT
    assert "source_id" in SYSTEM_PROMPT and "quote" in SYSTEM_PROMPT
    assert "issues du plan de recherche IA ou du plan de secours" in SYSTEM_PROMPT
    assert "conserve néanmoins les affirmations indépendantes" in SYSTEM_PROMPT

def test_ai_generated_article_references_must_exist_in_sources():
    assert answer_references_are_grounded("L'article L. 123-4 prévoit…", {"L123-4"})
    assert not answer_references_are_grounded("L'article L. 999-9 prévoit…", {"L123-4"})
    assert answer_references_are_grounded("Aucune référence d'article n'est citée.", set())

def test_ai_answer_rejects_unretrieved_bare_article_numbers_and_other_authorities():
    assert not answer_references_are_grounded("L'article 12 de la loi prévoit…", {"L123-4"})
    assert not answer_references_are_grounded("Le décret n° 2024-123 prévoit…", {"L123-4"})


def test_provider_token_usage_parser_preserves_unknown_values():
    assert _nonnegative_token_count(12) == 12
    assert _nonnegative_token_count(0) == 0
    assert _nonnegative_token_count(None) is None
    assert _nonnegative_token_count(-1) is None
    assert _nonnegative_token_count(True) is None
    assert _nonnegative_token_count("12") is None


def test_internal_ai_usage_metadata_is_never_serialized_to_clients():
    from app.schemas import AskResponse

    response = AskResponse(
        request_id="d5d2d51a-98f0-4e16-a9df-b0cc10bdf9f0",
        verification_status="NON_VERIFIE",
        answer="Réponse de test",
        ai_usage={"provider": "openai_compatible", "model": "private-model", "total_tokens": 42},
    )
    assert "ai_usage" not in response.model_dump()
    assert "ai_usage" not in response.model_dump(mode="json")


def test_ai_analysis_result_exposes_text_for_grounding_checks():
    from app.ai_provider import AIAnalysisResult, extract_analysis_content

    result = AIAnalysisResult(
        content="L'article L. 123-4 prévoit une règle.",
        model="test-model",
        prompt_tokens=10,
        completion_tokens=8,
        total_tokens=18,
    )
    assert extract_analysis_content(result) == result.content
    assert extract_analysis_content("Réponse de test") == "Réponse de test"
    assert extract_analysis_content(None) is None

def test_legal_citation_validator_accepts_only_references_in_injected_sources():
    from app.legal_assurance import validate_answer_citations

    sources = [
        {
            "source_type": "LEGIFRANCE_API",
            "source_id": "LEGIARTI000012345678",
            "article": "L123-4",
            "title": "Code général de la fonction publique — article L. 123-4",
            "excerpt": "Article L. 123-4 : règle officielle vérifiée.",
            "citation_integrity": {"valid": True},
        },
        {
            "source_type": "LEGIFRANCE_LODA",
            "source_id": "LEGITEXT000012345678",
            "official_number": "84-53",
            "title": "Décret n° 84-53 du 26 janvier 1984",
            "excerpt": "Décret n° 84-53 : dispositions applicables.",
            "citation_integrity": {"valid": True},
        },
        {
            "source_type": "LEGIFRANCE_CETAT_FULL_TEXT",
            "source_id": "CETATEXT000012345678",
            "case_number": "123456",
            "title": "CE, 12 mai 2024, n° 123456",
            "excerpt": "Décision intégrale consultée et identifiant concordant.",
            "citation_integrity": {"valid": True},
        },
    ]
    answer = (
        "L'article L. 123-4 est complété par le décret n° 84-53. "
        "Le Conseil d'État, 12 mai 2024, n° 123456, a statué sur ce point."
    )
    result = validate_answer_citations(answer, sources)
    assert result["valid"] is True
    assert result["invalid_references"] == []


def test_legal_citation_validator_rejects_hallucinated_article_decree_and_case():
    from app.legal_assurance import validate_answer_citations

    sources = [{
        "source_type": "LEGIFRANCE_API",
        "source_id": "LEGIARTI000012345678",
        "article": "L123-4",
        "title": "Code général de la fonction publique — article L. 123-4",
        "excerpt": "Article L. 123-4 : règle officielle vérifiée.",
        "citation_integrity": {"valid": True},
    }]
    result = validate_answer_citations(
        "L'article L. 999-9 résulte du décret n° 2024-999 et de CE, 2 juin 2024, n° 999999.",
        sources,
    )
    assert result["valid"] is False
    assert any(item.startswith("article:") for item in result["invalid_references"])
    assert any(item.startswith("authority:") for item in result["invalid_references"])
    assert any(item.startswith("case:") for item in result["invalid_references"])


def test_legal_citation_validator_requires_an_explicit_source_reference():
    from app.legal_assurance import validate_answer_citations

    source = {
        "source_type": "LEGIFRANCE_API",
        "article": "L123-4",
        "citation_integrity": {"valid": True},
    }
    result = validate_answer_citations("La règle s'applique à cette situation.", [source])
    assert result["valid"] is False
    assert "missing_explicit_source_citation" in result["invalid_references"]

def test_legal_citation_validator_rejects_uncited_legal_claim_lines():
    from app.legal_assurance import validate_answer_citations

    source = {
        "source_type": "LEGIFRANCE_API",
        "source_id": "LEGIARTI000012345678",
        "article": "L123-4",
        "title": "Code général de la fonction publique — article L. 123-4",
        "excerpt": "Article L. 123-4 : règle officielle vérifiée.",
        "citation_integrity": {"valid": True},
    }
    answer = (
        "L'article L. 123-4 prévoit une règle documentée.\n"
        "L'administration doit respecter un délai non cité."
    )
    result = validate_answer_citations(answer, [source])
    assert result["valid"] is False
    assert any(item.startswith("uncited_legal_claim_line:") for item in result["invalid_references"])




def _claim_source(**overrides):
    source = {
        "source_type": "LEGIFRANCE_API",
        "source_id": "LEGIARTI000012345678",
        "article": "L123-4",
        "title": "Code général de la fonction publique — article L. 123-4",
        "excerpt": "L'agent peut bénéficier d'un repos compensateur selon les conditions fixées.",
        "text": "L'agent peut bénéficier d'un repos compensateur selon les conditions fixées.",
        "content_kind": "FULL_TEXT",
        "temporal_status": "IN_FORCE_ON_REQUESTED_DATE",
        "public_service_scope": "FPT",
        "analysis_eligible": True,
        "official_source": True,
        "citation_integrity": {"valid": True},
    }
    source.update(overrides)
    return source


def test_claim_evidence_requires_exact_quote_from_the_exact_eligible_source():
    from app.legal_assurance import validate_claim_evidence

    source = _claim_source()
    result = validate_claim_evidence({
        "claims": [{
            "text": "L'agent peut bénéficier d'un repos compensateur.",
            "source_id": source["source_id"],
            "quote": "L'agent peut bénéficier d'un repos compensateur selon les conditions fixées.",
        }]
    }, [source])
    assert result["valid"] is True
    assert result["claim_count"] == 1


def test_later_administrative_case_law_is_interpretative_but_not_claim_evidence():
    from app.legal_assurance import classify_legal_source, validate_claim_evidence

    source = _claim_source(
        source_type="LEGIFRANCE_CETAT_FULL_TEXT",
        source_id="CETATEXT000012345678",
        decision_date="2025-02-10",
        temporal_status="DECISION_POSTERIOR_TO_FACTS",
    )
    assurance = classify_legal_source(source)
    assert assurance["usable_for_interpretation"] is True
    assert assurance["usable_for_conclusion"] is False
    result = validate_claim_evidence({
        "claims": [{
            "text": "L'agent peut bénéficier d'un repos compensateur selon les conditions fixées.",
            "source_id": source["source_id"],
            "quote": source["excerpt"],
        }]
    }, [source])
    assert result["valid"] is False
    assert "claim_0:source_missing_ineligible_or_ambiguous" in result["invalid_claims"]


def test_claim_evidence_accepts_verified_historical_local_document():
    from app.legal_assurance import validate_claim_evidence

    source = _claim_source(
        source_type="LOCAL_DOCUMENT",
        source_id="LOCAL-DOC:123_V20240101",
        validation_status="VERIFIED_HISTORICAL",
        temporal_status="VERIFIED_APPLICABLE",
        official_source=False,
    )
    result = validate_claim_evidence({
        "claims": [{
            "text": "L'agent peut bénéficier d'un repos compensateur.",
            "source_id": source["source_id"],
            "quote": source["excerpt"],
        }]
    }, [source])
    assert result["valid"] is True


def test_claim_evidence_rejects_quote_not_present_in_source():
    from app.legal_assurance import validate_claim_evidence

    source = _claim_source()
    result = validate_claim_evidence({
        "claims": [{
            "text": "L'agent peut bénéficier d'un repos compensateur.",
            "source_id": source["source_id"],
            "quote": "L'administration doit payer une prime de 30 jours.",
        }]
    }, [source])
    assert result["valid"] is False
    assert "claim_0:quote_not_exactly_found_in_source" in result["invalid_claims"]


def test_claim_evidence_accepts_current_date_sources_for_general_information_only():
    from app.legal_assurance import validate_claim_evidence

    source = _claim_source(temporal_status="TEMPORAL_SCOPE_INCOMPLETE", general_info_eligible=True)
    result = validate_claim_evidence({
        "claims": [{
            "text": "L'agent peut bénéficier d'un repos compensateur selon les conditions fixées.",
            "source_id": source["source_id"],
            "quote": source["excerpt"],
        }]
    }, [source])
    assert result["valid"] is True


def test_claim_evidence_rejects_snapshot_and_temporally_incomplete_sources():
    from app.legal_assurance import validate_claim_evidence

    snapshot = _claim_source(
        source_type="CGFP_SNAPSHOT",
        temporal_status="TEMPORAL_SCOPE_INCOMPLETE",
        reference_role="BASELINE_CONTEXT_ONLY",
    )
    result = validate_claim_evidence({
        "claims": [{
            "text": "L'agent peut bénéficier d'un repos compensateur.",
            "source_id": snapshot["source_id"],
            "quote": snapshot["excerpt"],
        }]
    }, [snapshot])
    assert result["valid"] is False
    assert "claim_0:source_missing_ineligible_or_ambiguous" in result["invalid_claims"]


def test_claim_evidence_rejects_unsupported_numeric_or_date_details():
    from app.legal_assurance import validate_claim_evidence

    source = _claim_source()
    result = validate_claim_evidence({
        "claims": [{
            "text": "L'agent peut bénéficier de 30 jours de repos compensateur.",
            "source_id": source["source_id"],
            "quote": source["excerpt"],
        }]
    }, [source])
    assert result["valid"] is False
    assert "claim_0:unsupported_numeric_or_date_detail" in result["invalid_claims"]


def test_answer_citation_accepts_exact_local_or_official_source_id_tag():
    from app.legal_assurance import validate_answer_citations

    source = _claim_source()
    result = validate_answer_citations(
        "L'agent peut bénéficier d'un repos compensateur. [source:LEGIARTI000012345678]",
        [source],
    )
    assert result["valid"] is True



def test_claim_evidence_rejects_an_exact_but_unrelated_quote():
    from app.legal_assurance import validate_claim_evidence

    source = _claim_source()
    result = validate_claim_evidence({
        "claims": [{
            "text": "La collectivité doit payer une indemnité supplémentaire.",
            "source_id": source["source_id"],
            "quote": source["excerpt"],
        }]
    }, [source])
    assert result["valid"] is False
    assert "claim_0:quote_not_relevantly_aligned" in result["invalid_claims"]


def test_entailment_verifier_fails_closed_on_unsupported_or_mismatched_verdicts():
    from app.ai_provider import validate_entailment_verdicts

    claim = {"source_id": "LEGIARTI000012345678", "text": "L'agent peut bénéficier d'un repos compensateur."}
    source = {"source_id": claim["source_id"], "text": "L'agent peut bénéficier d'un repos compensateur selon les conditions fixées."}
    valid = {"verdicts": [{
        "claim_index": 0, "source_id": claim["source_id"], "verdict": "SUPPORTED",
        "support_quote": "L'agent peut bénéficier d'un repos compensateur selon les conditions fixées.",
    }]}
    assert validate_entailment_verdicts(valid, [claim], [source])["valid"] is True

    for verdict in ("CONTRADICTED", "INSUFFICIENT", "MAYBE"):
        invalid = {"verdicts": [{**valid["verdicts"][0], "verdict": verdict}]}
        assert validate_entailment_verdicts(invalid, [claim], [source])["valid"] is False

    wrong_source = {"verdicts": [{**valid["verdicts"][0], "source_id": "OTHER"}]}
    assert validate_entailment_verdicts(wrong_source, [claim], [source])["valid"] is False

    invented_quote = {"verdicts": [{**valid["verdicts"][0], "support_quote": "L'agent reçoit toujours une prime garantie."}]}
    assert validate_entailment_verdicts(invented_quote, [claim], [source])["valid"] is False


def test_entailment_verifier_rejects_exact_quote_from_unrelated_part_of_same_source():
    from app.ai_provider import validate_entailment_verdicts

    claim = {
        "source_id": "LEGIARTI000012345678",
        "text": "La collectivité doit accorder un repos compensateur aux agents.",
    }
    unrelated_quote = "La procédure disciplinaire prévoit une exclusion temporaire de fonctions."
    source = {
        "source_id": claim["source_id"],
        "text": (
            unrelated_quote
            + " Le temps de travail supplémentaire ouvre droit à un repos compensateur "
              "dans les conditions prévues par le présent décret."
        ),
    }
    result = validate_entailment_verdicts({
        "verdicts": [{
            "claim_index": 0,
            "source_id": claim["source_id"],
            "verdict": "SUPPORTED",
            "support_quote": unrelated_quote,
        }]
    }, [claim], [source])
    assert result["valid"] is False
    assert "verdict_0:support_quote_not_relevantly_aligned" in result["invalid"]


def test_entailment_verifier_rejects_unsupported_numeric_claim_details():
    from app.ai_provider import validate_entailment_verdicts

    claim = {
        "source_id": "LEGIARTI000012345678",
        "text": "L'agent bénéficie de 25 jours de congé annuel.",
    }
    quote = "Les agents bénéficient d'un congé annuel dans les conditions prévues."
    source = {"source_id": claim["source_id"], "text": quote}
    result = validate_entailment_verdicts({
        "verdicts": [{
            "claim_index": 0,
            "source_id": claim["source_id"],
            "verdict": "SUPPORTED",
            "support_quote": quote,
        }]
    }, [claim], [source])
    assert result["valid"] is False
    assert "verdict_0:support_quote_missing_claim_facts" in result["invalid"]


def test_entailment_verifier_rejects_missing_extra_or_reordered_verdicts():
    from app.ai_provider import validate_entailment_verdicts

    claims = [
        {"source_id": "SRC000001", "text": "Proposition juridique numéro un."},
        {"source_id": "SRC000002", "text": "Proposition juridique numéro deux."},
    ]
    sources = [
        {"source_id": "SRC000001", "text": "Le premier passage officiel confirme une proposition juridique numéro un."},
        {"source_id": "SRC000002", "text": "Le second passage officiel confirme une proposition juridique numéro deux."},
    ]
    one = {"verdicts": [{"claim_index": 0, "source_id": "SRC000001", "verdict": "SUPPORTED",
                         "support_quote": sources[0]["text"]}]}
    assert validate_entailment_verdicts(one, claims, sources)["valid"] is False
    reversed_verdicts = {"verdicts": [
        {"claim_index": 1, "source_id": "SRC000001", "verdict": "SUPPORTED", "support_quote": sources[0]["text"]},
        {"claim_index": 0, "source_id": "SRC000002", "verdict": "SUPPORTED", "support_quote": sources[1]["text"]},
    ]}
    assert validate_entailment_verdicts(reversed_verdicts, claims, sources)["valid"] is False


def test_ask_request_distinguishes_situation_period_from_legacy_exact_date():
    from app.schemas import AskRequest

    legacy = AskRequest(employer="NATIONAL", facts_date="2024-01-15",
                        question="Question juridique suffisamment longue")
    assert legacy.facts_date == "2024-01-15"
    period = AskRequest(employer="NATIONAL", facts_start_date="2024-01-01",
                        facts_end_date="2024-06-30", situation_ongoing=False,
                        question="Question juridique suffisamment longue")
    assert period.facts_start_date == "2024-01-01"
    assert period.facts_end_date == "2024-06-30"
    assert period.situation_ongoing is False


@pytest.mark.asyncio
async def test_orchestrator_does_not_require_a_facts_date_before_research():
    from app.schemas import AskRequest
    from app.orchestrator import LegalOrchestrator

    request = AskRequest(employer="NATIONAL", question="Mon employeur m'a refusé un congé maladie, que puis-je faire ?")
    response = await LegalOrchestrator().ask(request, organization_id="00000000-0000-0000-0000-000000000001")
    assert response.clarification_question is None
    assert not any("indiquez la date" in item.casefold() for item in response.missing_information)
    assert not any("date des faits non renseignée" in item.casefold() for item in response.missing_information)
    assert "recherche générale" not in response.answer.casefold()


@pytest.mark.asyncio
async def test_orchestrator_does_not_require_a_complete_period_when_only_start_is_known():
    from app.schemas import AskRequest
    from app.orchestrator import LegalOrchestrator

    request = AskRequest(employer="NATIONAL", facts_start_date="2024-01-01",
                         question="Question juridique suffisamment longue")
    response = await LegalOrchestrator().ask(request, organization_id="00000000-0000-0000-0000-000000000001")
    assert response.clarification_question is None
    assert not any("date de fin" in item.casefold() for item in response.missing_information)


@pytest.mark.asyncio
async def test_orchestrator_accepts_an_end_date_without_a_start_date():
    from app.schemas import AskRequest
    from app.orchestrator import LegalOrchestrator

    request = AskRequest(employer="NATIONAL", facts_end_date="2024-06-30",
                         question="Question juridique suffisamment longue")
    response = await LegalOrchestrator().ask(request, organization_id="00000000-0000-0000-0000-000000000001")
    assert response.clarification_question is None
    assert not any("début de la situation" in item.casefold() for item in response.missing_information)


@pytest.mark.asyncio
async def test_orchestrator_rejects_inverted_situation_period():
    from app.schemas import AskRequest
    from app.orchestrator import LegalOrchestrator

    request = AskRequest(employer="NATIONAL", facts_start_date="2024-06-30",
                         facts_end_date="2024-01-01",
                         question="Question juridique suffisamment longue")
    response = await LegalOrchestrator().ask(request, organization_id="00000000-0000-0000-0000-000000000001")
    assert response.verification_status == "NON_VERIFIE"
    assert "ne peut pas précéder" in response.missing_information[0]


def test_ai_prompt_distinguishes_fact_period_from_text_effective_date():
    assert "Distingue la période de la situation" in SYSTEM_PROMPT
    assert "compare explicitement les sources datées du début et de la fin" in SYSTEM_PROMPT
    assert "ne doit jamais servir de filtre général" in SYSTEM_PROMPT
    assert "peuvent pleinement éclairer ou protéger l'agent" in SYSTEM_PROMPT
    assert "Une décision administrative rendue après les faits ne doit pas être écartée automatiquement" in SYSTEM_PROMPT
    assert "La date des faits n'est pas un préalable à la recherche" in SYSTEM_PROMPT
    assert "Ne demande pas automatiquement la date des faits" in SYSTEM_PROMPT
    assert "GENERAL_CURRENT_LAW_WITHOUT_FACTS_DATE" in SYSTEM_PROMPT
    assert "PERSONAL_CASE_WITHOUT_FACTS_DATE" in SYSTEM_PROMPT
    assert "utilise les faits personnels uniquement pour identifier les textes à rechercher" in SYSTEM_PROMPT
    assert "sans qualifier la situation individuelle" in SYSTEM_PROMPT
    assert "FACTS_PERIOD_START_VERSION" in SYSTEM_PROMPT
    assert "CURRENT_LAW_VERSION" in SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_orchestrator_rejects_end_date_when_situation_is_ongoing():
    from app.schemas import AskRequest
    from app.orchestrator import LegalOrchestrator

    request = AskRequest(employer="NATIONAL", facts_start_date="2024-01-01",
                         facts_end_date="2024-06-30", situation_ongoing=True,
                         question="Question juridique suffisamment longue")
    response = await LegalOrchestrator().ask(request, organization_id="00000000-0000-0000-0000-000000000001")
    assert response.verification_status == "NON_VERIFIE"
    assert "toujours en cours" in response.missing_information[0]


@pytest.mark.asyncio
async def test_legacy_single_fact_date_remains_a_single_day():
    from app.schemas import AskRequest
    from app.orchestrator import LegalOrchestrator

    request = AskRequest(employer="NATIONAL", facts_date="2024-01-15",
                         question="Question juridique suffisamment longue")
    response = await LegalOrchestrator().ask(request, organization_id="00000000-0000-0000-0000-000000000001")
    assert response.clarification_question is None
    assert any("2024-01-15" in item for item in response.missing_information)


def test_period_scoped_official_source_id_remains_grounded_for_citation_validation():
    from app.legal_assurance import validate_answer_citations

    source = {
        "source_type": "LEGIFRANCE_API",
        "source_id": "LEGIARTI000012345678_V20240101",
        "official_source_id": "LEGIARTI000012345678",
        "article": "L123-4",
        "title": "Code général de la fonction publique — article L. 123-4",
        "excerpt": "Article L. 123-4 : règle officielle vérifiée.",
        "citation_integrity": {"valid": True},
    }
    result = validate_answer_citations(
        "L'article L. 123-4 prévoit une règle documentée. [source:LEGIARTI000012345678_V20240101]",
        [source],
    )
    assert result["valid"] is True


@pytest.mark.asyncio
async def test_ai_gateway_availability_check_uses_only_non_billable_model_catalog(monkeypatch):
    import httpx

    monkeypatch.setattr(settings, "ai_api_key", "test-token")
    monkeypatch.setattr(settings, "ai_model", "gpt-5-mini")
    monkeypatch.setattr(settings, "ai_api_base_url", "https://gateway.example/v1")

    def handler(request):
        assert request.method == "GET"
        assert request.url.path == "/v1/models"
        return httpx.Response(200, json={"data": [
            {"id": "gpt-5-mini", "enabled": True},
            {"id": "other-model", "enabled": False},
        ]})

    result = await check_provider_availability(transport=httpx.MockTransport(handler))
    assert result == {"status": "AVAILABLE"}


@pytest.mark.asyncio
async def test_ai_gateway_availability_reports_disabled_model_without_inference(monkeypatch):
    import httpx

    monkeypatch.setattr(settings, "ai_api_key", "test-token")
    monkeypatch.setattr(settings, "ai_model", "gpt-5-mini")
    monkeypatch.setattr(settings, "ai_api_base_url", "https://gateway.example/v1")

    def handler(request):
        assert request.method == "GET"
        return httpx.Response(200, json={"data": [
            {"id": "gpt-5-mini", "enabled": False, "unavailable_reason": "paid_plan_required"}
        ]})

    result = await check_provider_availability(transport=httpx.MockTransport(handler))
    assert result == {"status": "MODEL_DISABLED", "reason": "paid_plan_required"}


def test_neon_gateway_bare_host_is_normalized_to_openai_v1(monkeypatch):
    from app.ai_provider import _provider_api_base

    monkeypatch.setattr(
        settings, "ai_api_base_url",
        "https://br-example-api.ai.c-8.us-east-2.aws.neon.tech",
    )
    assert _provider_api_base() == "https://br-example-api.ai.c-8.us-east-2.aws.neon.tech/v1"


def test_non_neon_provider_base_url_is_preserved(monkeypatch):
    from app.ai_provider import _provider_api_base

    monkeypatch.setattr(settings, "ai_api_base_url", "https://api.example/v1")
    assert _provider_api_base() == "https://api.example/v1"


@pytest.mark.asyncio
async def test_gemini_model_availability_uses_read_only_models_get_and_header_key(monkeypatch):
    import httpx

    monkeypatch.setattr(settings, "ai_api_key", "test-gemini-key")
    monkeypatch.setattr(settings, "ai_model", "gemini-3.8-flash")
    monkeypatch.setattr(settings, "ai_api_base_url", "https://generativelanguage.googleapis.com/v1beta/openai")

    def handler(request):
        assert request.method == "GET"
        assert request.url.path == "/v1beta/models/gemini-3.8-flash"
        assert request.url.query == b""
        assert request.headers["x-goog-api-key"] == "test-gemini-key"
        assert "Authorization" not in request.headers
        return httpx.Response(200, json={
            "name": "models/gemini-3.8-flash",
            "supportedGenerationMethods": ["generateContent"],
        })

    result = await check_provider_availability(transport=httpx.MockTransport(handler))
    assert result == {"status": "AVAILABLE"}


@pytest.mark.asyncio
async def test_gemini_model_availability_fails_closed_when_model_is_missing(monkeypatch):
    import httpx

    monkeypatch.setattr(settings, "ai_api_key", "test-gemini-key")
    monkeypatch.setattr(settings, "ai_model", "missing-model")
    monkeypatch.setattr(settings, "ai_api_base_url", "https://generativelanguage.googleapis.com/v1beta/openai")

    def handler(request):
        assert request.method == "GET"
        return httpx.Response(404, json={"error": {"status": "NOT_FOUND"}})

    result = await check_provider_availability(transport=httpx.MockTransport(handler))
    assert result == {"status": "MODEL_NOT_FOUND"}


def test_gemini_openai_compatible_base_is_preserved(monkeypatch):
    from app.ai_provider import _provider_api_base, _is_gemini_provider

    monkeypatch.setattr(settings, "ai_api_base_url", "https://generativelanguage.googleapis.com/v1beta/openai/")
    assert _is_gemini_provider() is True
    assert _provider_api_base() == "https://generativelanguage.googleapis.com/v1beta/openai"


@pytest.mark.asyncio
async def test_gemini_chat_completion_uses_compatible_route_and_bearer_auth(monkeypatch):
    import httpx

    monkeypatch.setattr(settings, "ai_api_key", "test-gemini-key")
    monkeypatch.setattr(settings, "ai_model", "gemini-3.8-flash")
    monkeypatch.setattr(settings, "ai_api_base_url", "https://generativelanguage.googleapis.com/v1beta/openai")

    def handler(request):
        assert request.method == "POST"
        assert request.url.path == "/v1beta/openai/chat/completions"
        assert request.headers["Authorization"] == "Bearer test-gemini-key"
        assert "response_format" not in request.content.decode("utf-8")
        return httpx.Response(200, json={
            "model": "gemini-3.8-flash",
            "choices": [{"message": {"content": '{"claims": []}'}}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 4, "total_tokens": 16},
        })

    original_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: original_client(
        *args, transport=httpx.MockTransport(handler), **kwargs
    ))
    result = await analyze_question(
        question="Question de test suffisamment longue", employer="NATIONAL",
        facts_date="2026-01-01", sources=[{
            "source_type": "LEGIFRANCE_API",
            "source_id": "LEGIARTI000012345678_V20260101",
            "title": "Code général de la fonction publique",
            "article": "L111-1",
            "valid_from": "2022-03-01",
            "valid_to": "2999-01-01",
            "requested_effective_date": "2026-01-01",
            "excerpt": "Extrait officiel daté de test suffisamment long.",
        }],
    )
    assert result.content == '{"claims": []}'
    assert result.total_tokens == 16


@pytest.mark.asyncio
@pytest.mark.parametrize("sources", [None, [], [{}], [{"excerpt": ""}], [{"excerpt": "  ", "text": ""}], [{"text": "   "}], [{"text": "!!!"}], [{"text": "...", "source_id": "LEGI123", "requested_effective_date": "2026-01-01"}], [{"text": "Texte utile", "source_id": "LEGI123"}], [{"text": "Texte utile", "requested_effective_date": "2026-01-01"}], [{"text": "Texte utile", "source_id": "LEGI123", "requested_effective_date": "date-invalide"}], ["not-a-document"]])
async def test_ai_provider_refuses_missing_or_empty_source_text_without_http(monkeypatch, sources):
    import httpx

    monkeypatch.setattr(settings, "ai_api_key", "test-gemini-key")
    monkeypatch.setattr(settings, "ai_model", "gemini-3.8-flash")
    monkeypatch.setattr(settings, "ai_api_base_url", "https://generativelanguage.googleapis.com/v1beta/openai")

    class ForbiddenClient:
        def __init__(self, *args, **kwargs):
            raise AssertionError("Aucune requête HTTP ne doit partir sans extrait non vide.")

    monkeypatch.setattr(httpx, "AsyncClient", ForbiddenClient)
    with pytest.raises(AIAnalysisRefusedNoSources):
        await analyze_question(
            question="Question de test suffisamment longue",
            employer="NATIONAL",
            facts_date="2026-01-01",
            sources=sources,
        )


def test_usable_sources_accept_text_fallback_and_preserve_official_provenance():
    from app.ai_provider import _usable_document_sources

    source = {
        "source_type": "LEGIFRANCE_API",
        "source_id": "LEGIARTI000044427983_V20261119",
        "official_source_id": "LEGIARTI000044427983",
        "article": "L111-1",
        "reference": "CGFP, article L111-1",
        "valid_from": "2022-03-01",
        "valid_to": "2999-01-01",
        "requested_effective_date": "2026-11-19",
        "text": "Extrait officiel de l'article.",
    }
    accepted = _usable_document_sources([source])
    assert accepted == [{**source, "excerpt": "Extrait officiel de l'article."}]
    assert accepted[0]["source_id"] == source["source_id"]
    assert accepted[0]["reference"] == source["reference"]
    assert accepted[0]["requested_effective_date"] == source["requested_effective_date"]

def test_runtime_configuration_accepts_gemini_openai_compatible_endpoint():
    from app.config import Settings, validate_runtime_configuration

    cfg = Settings(
        app_env="test",
        ai_api_base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        ai_api_key="test-gemini-key",
        ai_model="gemini-3.8-flash",
    )
    validate_runtime_configuration(cfg)

@pytest.mark.asyncio
async def test_gemini_openai_compatible_request_uses_fake_transport_and_keeps_source_provenance(monkeypatch):
    import httpx
    from app import ai_provider

    captured = {}

    def handler(request):
        captured["url"] = str(request.url)
        captured["payload"] = __import__("json").loads(request.content)
        return httpx.Response(200, json={
            "model": "gemini-test",
            "choices": [{"message": {"content": '{"claims": []}'}}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 3, "total_tokens": 14},
        }, request=request)

    real_async_client = httpx.AsyncClient

    def fake_async_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(ai_provider.httpx, "AsyncClient", fake_async_client)
    monkeypatch.setattr(settings, "ai_api_base_url", "https://generativelanguage.googleapis.com/v1beta/openai")
    monkeypatch.setattr(settings, "ai_api_key", "test-key-not-a-real-secret")
    monkeypatch.setattr(settings, "ai_model", "gemini-test")
    source = {
        "source_type": "LEGIFRANCE_API",
        "source_id": "LEGIARTI000012345678",
        "official_source_id": "LEGIARTI000012345678",
        "article": "L123-4",
        "requested_effective_date": "2026-11-19",
        "excerpt": "Extrait officiel de test suffisamment explicite.",
        "valid_from": "2020-01-01",
        "valid_to": "2999-01-01",
        "legal_assurance": {
            "source_family": "CODE",
            "source_family_label": "Disposition codifiée",
            "authority_level": "PRIMARY_LEGAL",
            "authority_label": "Texte juridique primaire",
            "publisher": "Légifrance",
            "publisher_type": "PUBLIC_ADMINISTRATION",
            "normative": True,
        },
    }
    decision = {
        "source_type": "LEGIFRANCE_CETAT_FULL_TEXT",
        "source_id": "CETATEXT000012345678",
        "decision_date": "2024-05-10",
        "case_number": "123456",
        "jurisdiction": "Conseil d'État",
        "content_kind": "FULL_TEXT",
        "excerpt": "Texte intégral officiel de la décision administrative suffisamment long.",
    }

    result = await ai_provider.analyze_question(
        question="Question de test sur le texte officiel",
        employer="NATIONAL",
        facts_date="2026-11-19",
        sources=[source, decision],
        legal_context={"topic": "UNION_RIGHTS", "agent_status": "NOT_SPECIFIED"},
    )

    assert result.content == '{"claims": []}'
    assert result.model == "gemini-test"
    assert captured["url"].endswith("/v1beta/openai/chat/completions")
    serialized = captured["payload"]["messages"][1]["content"]
    assert "LEGIARTI000012345678" in serialized
    assert "2026-11-19" in serialized
    assert "Extrait officiel de test suffisamment explicite." in serialized
    payload_data = json.loads(serialized)
    legal_source_payload = next(
        item for item in payload_data["extraits_documentaires_valides"]
        if item["identifiant_source"] == "LEGIARTI000012345678"
    )
    assert legal_source_payload["niveau_autorite"] == "PRIMARY_LEGAL"
    assert legal_source_payload["libelle_autorite"] == "Texte juridique primaire"
    assert legal_source_payload["editeur"] == "Légifrance"
    assert legal_source_payload["source_normative"] is True
    assert "CETATEXT000012345678" in serialized
    assert '"date_decision": "2024-05-10"' in serialized
    assert '"qualification_juridique_pre_recherche": {"topic": "UNION_RIGHTS", "agent_status": "NOT_SPECIFIED"}' in serialized



def test_usable_sources_accept_dated_cetat_full_text_but_reject_search_metadata():
    from app.ai_provider import _usable_document_sources

    full_text = {
        "source_type": "LEGIFRANCE_CETAT_FULL_TEXT",
        "source_id": "CETATEXT000012345678",
        "decision_date": "2024-05-10",
        "content_kind": "FULL_TEXT",
        "citation_integrity": {"valid": True},
        "text": "Décision officielle intégrale relative à un agent territorial. " * 3,
    }
    accepted = _usable_document_sources([full_text])
    assert len(accepted) == 1
    assert accepted[0]["source_id"] == "CETATEXT000012345678"
    assert accepted[0]["excerpt"] == full_text["text"].strip()

    metadata = {
        **full_text,
        "source_type": "LEGIFRANCE_CETAT_SEARCH",
        "content_kind": "METADATA",
        "excerpt": "Simple extrait de recherche non probant.",
    }
    assert _usable_document_sources([metadata]) == []


def test_system_prompt_treats_fpt_reference_sources_as_non_applicable_without_local_bridge():
    from app.ai_provider import SYSTEM_PROMPT

    assert "FPT_REFERENCE" in SYSTEM_PROMPT
    assert "décret 91-875" in SYSTEM_PROMPT
    assert "délibération locale" in SYSTEM_PROMPT
    assert "ne conclus pas au droit individuel" in SYSTEM_PROMPT


def test_system_prompt_requires_neutral_documentary_explanations_without_case_advice():
    assert "Tu peux reformuler un passage en langage clair" in SYSTEM_PROMPT
    assert "strictement fidèle au texte ou à la décision citée" in SYSTEM_PROMPT
    assert "Ne donne aucun avis personnel" in SYSTEM_PROMPT
    assert "Ne transforme pas la restitution des textes en consultation juridique" in SYSTEM_PROMPT
    assert "Présente ces éléments comme une explication documentaire générale" in SYSTEM_PROMPT
    assert "Ne suggère aucune action individuelle, aucun recours à engager ni aucune stratégie personnelle" in SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_entailment_verifier_receives_current_question_for_relevance_check(monkeypatch):
    import httpx
    import json
    from app.ai_provider import verify_claim_entailment

    monkeypatch.setattr(settings, "ai_api_key", "test-token")
    monkeypatch.setattr(settings, "ai_model", "test-model")
    monkeypatch.setattr(settings, "ai_api_base_url", "https://gateway.example/v1")
    source_text = "Les heures supplémentaires peuvent ouvrir droit à compensation selon les règles applicables."
    source = {
        "source_id": "SRC-IHTS-1",
        "title": "Règles relatives aux heures supplémentaires",
        "text": source_text,
        "public_service_scope": "FPT",
        "analysis_eligible": True,
        "claim_eligible": True,
        "version_status": "IN_FORCE",
        "temporal_status": "IN_FORCE_ON_REQUESTED_DATE",
    }
    claim = {
        "source_id": "SRC-IHTS-1",
        "text": "Les heures supplémentaires peuvent ouvrir droit à une compensation.",
    }
    captured = {}

    def handler(request):
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json={
            "choices": [{"message": {"content": json.dumps({
                "verdicts": [{
                    "claim_index": 0,
                    "source_id": "SRC-IHTS-1",
                    "verdict": "INSUFFICIENT",
                    "support_quote": "",
                }]
            })}}]
        })

    real_async_client = httpx.AsyncClient

    def fake_async_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", fake_async_client)
    result = await verify_claim_entailment(
        question="Mon employeur peut-il refuser de compenser mes heures supplémentaires ?",
        claims=[claim],
        sources=[source],
    )

    verifier_payload = json.loads(captured["payload"]["messages"][1]["content"])
    verifier_question = verifier_payload["question_actuelle"]
    assert verifier_question == "Mon employeur peut-il refuser de compenser mes heures supplémentaires ?"
    evidence = verifier_payload["items_to_verify"][0]
    assert evidence["public_service_scope"] == "FPT"
    assert evidence["analysis_eligible"] is True
    assert evidence["claim_eligible"] is True
    assert evidence["version_status"] == "IN_FORCE"
    assert evidence["temporal_status"] == "IN_FORCE_ON_REQUESTED_DATE"
    # A source that only says compensation may be possible does not answer
    # whether the employer may refuse in this agent's specific question.
    assert result["valid"] is False
    assert "verdict_0:not_supported" in result["invalid"]


@pytest.mark.asyncio
async def test_ai_payload_preserves_official_administrative_publication_metadata(monkeypatch):
    import json
    import httpx
    from app.ai_provider import analyze_question

    monkeypatch.setattr(settings, "ai_api_key", "test-key")
    monkeypatch.setattr(settings, "ai_model", "test-model")
    monkeypatch.setattr(settings, "ai_api_base_url", "https://example.test/v1")
    captured = {}

    def handler(request):
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({"claims": []})}}], "usage": {}})

    real_async_client = httpx.AsyncClient
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr("app.ai_provider.httpx.AsyncClient", lambda **kwargs: real_async_client(transport=transport, **kwargs))

    await analyze_question(
        question="Question sur un agent territorial",
        employer="NATIONAL", facts_date="2025-01-01",
        sources=[{
            "source_type": "OTHER_OFFICIAL", "source_id": "OPEN_DATA_JA_1234567890123456",
            "title": "Décision administrative", "signature_date": "2024-05-10",
            "jurisdiction": "Tribunal administratif de Grenoble", "official_number": "2400001",
            "source_status": "OFFICIAL_XML_IMPORTED", "content_kind": "FULL_TEXT",
            "retrieval_scope": "TOP_RELEVANT_PASSAGE_AND_FINAL_CHUNK_FROM_HASH_VERIFIED_FULL_TEXT",
            "excerpt": "Texte intégral officiel suffisamment long pour être transmis au modèle.",
            "raw_metadata": {"publication_code": "B", "ecli": "ECLI:FR:TA38:2024:2400001", "decision_type": "ordonnance", "solution": "Rejet pour irrecevabilité", "recourse_type": "Excès de pouvoir"},
        }],
    )
    payload_sources = json.loads(captured["payload"]["messages"][1]["content"])["extraits_documentaires_valides"]
    assert payload_sources[0]["code_publication_jurisprudentielle"] == "B"
    assert payload_sources[0]["numero_ecli"] == "ECLI:FR:TA38:2024:2400001"
    assert payload_sources[0]["type_decision"] == "ordonnance"
    assert payload_sources[0]["solution_decision"] == "Rejet pour irrecevabilité"
    assert payload_sources[0]["portee_extrait"] == "TOP_RELEVANT_PASSAGE_AND_FINAL_CHUNK_FROM_HASH_VERIFIED_FULL_TEXT"



def test_usable_sources_reject_explicitly_failed_integrity_and_out_of_scope_records():
    from app.ai_provider import _usable_document_sources

    base = {
        "source_type": "LEGIFRANCE_API",
        "source_id": "LEGIARTI000012345678",
        "requested_effective_date": "2026-11-21",
        "excerpt": "Extrait officiel daté suffisamment long pour une analyse documentaire.",
    }
    invalid_integrity = {**base, "citation_integrity": {"valid": False}}
    out_of_scope = {**base, "analysis_eligible": False, "public_service_scope": "FPH"}
    assert _usable_document_sources([invalid_integrity, out_of_scope]) == []

def test_shared_evidence_normalization_handles_typography_without_erasing_legal_differences():
    from app.ai_provider import _normalize_entailment_text
    from app.legal_assurance import _normalized_evidence_text

    source = "L’agent – ne peut pas – bénéficier de « 10 000 euros »…"
    quote = "L'agent - ne peut pas - bénéficier de \" 10 000 euros \"..."
    normalized_source = _normalized_evidence_text(source)
    normalized_quote = _normalize_entailment_text(quote)

    assert normalized_source == normalized_quote
    assert normalized_quote in normalized_source
    assert _normalized_evidence_text("1\u00a0000 euros") == "1 000 euros"

    # Typographic normalization must not remove negation, merge references,
    # or change the numeric value of an amount.
    assert "L. 1234" not in _normalized_evidence_text("L. 123-4")
    assert "10000 euros" not in _normalize_entailment_text("10 000 euros")
    assert "L'agent peut bénéficier" not in _normalized_evidence_text(
        "L'agent ne peut pas bénéficier"
    )


def test_structured_answer_parser_accepts_only_pure_or_fenced_json_objects():
    from app.ai_provider import parse_structured_answer

    valid = '{"claims": []}'
    assert parse_structured_answer(valid) == {"claims": []}
    assert parse_structured_answer("```json\n" + valid + "\n```") == {"claims": []}
    assert parse_structured_answer("```\n" + valid + "\n```") == {"claims": []}

    for invalid in (
        "Voici la réponse : " + valid,
        valid + "\nVoici la réponse.",
        "```json\n" + valid,
        "[1, 2, 3]",
        "{claims: []}",
        "",
        None,
    ):
        assert parse_structured_answer(invalid) is None


def test_research_plan_parser_accepts_bounded_dynamic_queries_and_subquestions():
    plan = _parse_research_plan("""{
        "queries": [
            "régime juridique des autorisations spéciales d'absence des agents territoriaux",
            "conditions et procédure de refus d'une autorisation spéciale d'absence syndicale"
        ],
        "legal_issues": ["Fondement juridique et champ des ASA syndicales", "Conditions de refus et voies de contestation"],
        "clarification_needed": null
    }""")
    assert plan is not None
    assert len(plan.queries) == 2
    assert "autorisations spéciales d'absence" in plan.queries[0]
    assert len(plan.legal_issues) == 2


def test_research_plan_parser_rejects_empty_or_malformed_model_output():
    assert _parse_research_plan("not json") is None
    assert _parse_research_plan('{"queries": [], "legal_issues": []}') is None
    assert _parse_research_plan('{"queries": ["x"], "legal_issues": []}') is None


@pytest.mark.asyncio
async def test_research_planner_is_disabled_without_provider_credentials(monkeypatch):
    monkeypatch.setattr(settings, "ai_api_key", "")
    monkeypatch.setattr(settings, "ai_model", "")
    monkeypatch.setattr(settings, "ai_api_base_url", "")
    assert await plan_legal_research(
        question="Question juridique inédite",
        employer="NATIONAL",
    ) is None


def test_research_planner_is_not_an_article_or_problem_template_catalog():
    from app.ai_provider import plan_legal_research
    import inspect

    source = inspect.getsource(plan_legal_research)
    assert "Ne pars d'aucune liste prédéfinie" in source
    assert "N'invente pas de références" in source
    assert "3 à 5 axes de recherche réellement distincts" in source
    assert "2 à 6 termes juridiques ou factuels discriminants" in source


@pytest.mark.parametrize("versant", ["FPT", "FPE", "FPH"])
def test_research_planner_system_prompt_forbids_cross_branch_transposition(versant):
    from app.ai_provider import _PUBLIC_SERVICE_LABELS, plan_legal_research
    import inspect
    selected_label = _PUBLIC_SERVICE_LABELS[versant]
    source = inspect.getsource(plan_legal_research)
    assert "CONTRAINTE DE VERSANT" in source
    assert "N'utilise aucune requête-type" in source
    assert "({selected_label})" in source
    assert selected_label in _PUBLIC_SERVICE_LABELS.values()

def test_research_plan_parser_accepts_empty_queries_only_for_refinement():
    assert _parse_research_plan('{"queries": [], "legal_issues": []}') is None
    refined = _parse_research_plan('{"queries": [], "legal_issues": ["Question juridique couverte"]}', allow_empty=True)
    assert refined is not None
    assert refined.queries == []
    assert refined.legal_issues == ["Question juridique couverte"]


@pytest.mark.asyncio
async def test_source_relevance_evaluator_sends_document_text_and_validates_ids(monkeypatch):
    import json
    import httpx
    from app.ai_provider import evaluate_source_relevance

    monkeypatch.setattr(settings, "ai_api_key", "test-key")
    monkeypatch.setattr(settings, "ai_model", "test-model")
    monkeypatch.setattr(settings, "ai_api_base_url", "https://example.test/v1")
    captured = {}

    def handler(request):
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{
            "message": {"content": json.dumps({"items": [
                {"source_id": "DOC-1", "verdict": "DIRECT"},
                {"source_id": "FORGED", "verdict": "IRRELEVANT"},
                {"source_id": "META-1", "verdict": "IRRELEVANT"},
            ]})}
        }]})

    real_async_client = httpx.AsyncClient

    def fake_async_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", fake_async_client)
    result = await evaluate_source_relevance(
        question="Puis-je percevoir une indemnité pour les fonctions supplémentaires ?",
        research_axes=["régime indemnitaire et fonctions exercées"],
        sources=[
            {"source_id": "DOC-1", "source_type": "LEGIFRANCE_API",
             "title": "Régime indemnitaire", "excerpt": "Le régime indemnitaire tient compte des fonctions exercées."},
            {"source_id": "META-1", "content_kind": "METADATA",
             "excerpt": "Simple résultat de recherche sans texte intégral."},
        ],
    )

    documents = json.loads(captured["payload"]["messages"][1]["content"])["documents"]
    assert [item["source_id"] for item in documents] == ["DOC-1"]
    assert "fonctions exercées" in documents[0]["body"]
    assert result == {"DOC-1": "DIRECT"}


@pytest.mark.asyncio
async def test_source_relevance_evaluator_raises_provider_error_on_http_failure(monkeypatch):
    import httpx
    from app.ai_provider import evaluate_source_relevance, AIProviderUnavailable

    monkeypatch.setattr(settings, "ai_api_key", "test-key")
    monkeypatch.setattr(settings, "ai_model", "test-model")
    monkeypatch.setattr(settings, "ai_api_base_url", "https://example.test/v1")

    def handler(request):
        return httpx.Response(503, request=request)

    real_async_client = httpx.AsyncClient

    def fake_async_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", fake_async_client)
    with pytest.raises(AIProviderUnavailable):
        await evaluate_source_relevance(
            question="Question juridique",
            research_axes=["axe"],
            sources=[{"source_id": "DOC-1", "excerpt": "Texte officiel suffisamment renseigné."}],
        )


def test_research_plan_normalizes_whitespace_before_matching_verbatim_evidence():
    plan = _parse_research_plan(
        json.dumps({
            "queries": ["régime de remplacement temporaire"],
            "legal_issues": ["Conditions du remplacement temporaire"],
            "extracted_facts": [
                {
                    "fact": "Remplacement effectué pendant une période prolongée.",
                    "evidence_quote": "titulaire de la FPT. Je remplace un collègue pendant un an et 11 mois",
                },
                {
                    "fact": "Même fait avec une mise en page différente.",
                    "evidence_quote": "titulaire de la FPT.\nJe remplace   un collègue\tpendant un an et 11 mois",
                },
                {
                    "fact": "Fait non présent dans la question.",
                    "evidence_quote": "je remplace un collègue depuis trois ans",
                },
            ],
        }, ensure_ascii=False),
        question=(
            "Je suis titulaire de la FPT.\n"
            "Je remplace   un collègue\tpendant un an et 11 mois."
        ),
    )
    assert plan is not None
    assert len(plan.extracted_facts) == 1
    assert plan.extracted_facts[0]["fact"] == "Remplacement effectué pendant une période prolongée."
    assert plan.extracted_facts[0]["evidence_quote"] == (
        "titulaire de la FPT. Je remplace un collègue pendant un an et 11 mois"
    )


def test_research_plan_extracts_only_facts_with_verbatim_question_evidence():
    plan = _parse_research_plan(
        json.dumps({
            "queries": ["régime indemnitaire territorial fonctions supplémentaires"],
            "legal_issues": ["Conditions de réexamen du régime indemnitaire"],
            "extracted_facts": [
                {"fact": "L'agent est titulaire.", "evidence_quote": "je suis titulaire"},
                {"fact": "Le remplacement a duré 23 mois.", "evidence_quote": "pendant un an et 11 mois"},
                {"fact": "L'agent a travaillé la nuit.", "evidence_quote": "travail de nuit"},
                {"fact": "L'agent est titulaire.", "evidence_quote": "je suis titulaire"},
            ],
            "clarification_needed": None,
        }, ensure_ascii=False),
        question=(
            "Je suis titulaire de la fonction publique territoriale, "
            "suite à l'absence d'un collègue pendant un an et 11 mois "
            "j'ai dû prendre en charge ses fonctions en plus des miennes."
        ),
    )
    assert plan is not None
    assert len(plan.extracted_facts) == 2
    assert plan.extracted_facts[0]["evidence_quote"] == "je suis titulaire"
    assert plan.extracted_facts[1]["evidence_quote"] == "pendant un an et 11 mois"


def test_research_plan_facts_are_empty_without_verbatim_evidence():
    plan = _parse_research_plan(
        json.dumps({
            "queries": ["régime indemnitaire territorial"],
            "legal_issues": ["Régime indemnitaire"],
            "extracted_facts": [
                {"fact": "La durée est de deux ans.", "evidence_quote": "deux ans"},
                {"fact": "L'agent est titulaire.", "evidence_quote": "titulaire"},
            ],
        }, ensure_ascii=False),
        question="Je remplace un collègue depuis plusieurs mois.",
    )
    assert plan is not None
    assert plan.extracted_facts == []



def test_entailment_verifier_keeps_individually_supported_claim_indices():
    from app.ai_provider import validate_entailment_verdicts

    claims = [
        {
            "source_id": "LEGIARTI000000000001",
            "text": "L'agent peut bénéficier d'un repos compensateur selon les conditions prévues.",
        },
        {
            "source_id": "LEGIARTI000000000002",
            "text": "La collectivité doit verser une indemnité supplémentaire.",
        },
    ]
    sources = [
        {
            "source_id": claims[0]["source_id"],
            "text": "L'agent peut bénéficier d'un repos compensateur selon les conditions prévues.",
        },
        {
            "source_id": claims[1]["source_id"],
            "text": "La collectivité organise le service et veille à la santé des agents.",
        },
    ]
    result = validate_entailment_verdicts({
        "verdicts": [
            {
                "claim_index": 0,
                "source_id": claims[0]["source_id"],
                "verdict": "SUPPORTED",
                "support_quote": sources[0]["text"],
            },
            {
                "claim_index": 1,
                "source_id": claims[1]["source_id"],
                "verdict": "INSUFFICIENT",
                "support_quote": "",
            },
        ]
    }, claims, sources)

    assert result["valid"] is False
    assert result["supported_claim_indices"] == [0]
    assert "verdict_1:not_supported" in result["invalid"]



def test_undated_non_normative_guidance_can_reach_ai_as_context_only():
    from app.ai_provider import _usable_document_sources

    guidance = {
        "source_type": "INSTITUTIONAL_GUIDANCE",
        "source_id": "cfdt-guide-2026",
        "title": "Guide syndical",
        "publisher": "CFDT",
        "excerpt": "Les agents peuvent consulter les représentants du personnel.",
        "content_kind": "FULL_TEXT",
        "claim_eligible": False,
        "reference_role": "NON_NORMATIVE_CONTEXT_ONLY",
        "legal_assurance": {
            "reference_role": "NON_NORMATIVE_CONTEXT_ONLY",
            "usable_for_interpretation": True,
            "authority_level": "PROFESSIONAL_GUIDANCE",
            "publisher_type": "TRADE_UNION",
        },
        "citation_integrity": {"valid": True},
    }
    assert _usable_document_sources([guidance]) == [{**guidance, "excerpt": guidance["excerpt"]}]

    unsafe = {
        **guidance,
        "legal_assurance": {"reference_role": "NON_NORMATIVE_CONTEXT_ONLY"},
    }
    assert _usable_document_sources([unsafe]) == []


@pytest.mark.asyncio
async def test_gemini_availability_check_reports_http_failure_without_exposing_api_key(monkeypatch, caplog):
    import httpx
    import logging
    from app.ai_provider import check_provider_availability

    secret = "test-gemini-secret-never-log"
    monkeypatch.setattr(settings, "ai_api_key", secret)
    monkeypatch.setattr(settings, "ai_model", "gemini-2.5-flash")
    monkeypatch.setattr(
        settings, "ai_api_base_url",
        "https://generativelanguage.googleapis.com/v1beta/openai",
    )

    def handler(request):
        assert request.url.path.endswith("/v1beta/models/gemini-2.5-flash")
        return httpx.Response(
            403, request=request,
            json={"error": {"message": "API key not authorized"}},
        )

    caplog.set_level(logging.WARNING, logger="app.ai_provider")
    result = await check_provider_availability(transport=httpx.MockTransport(handler))

    assert result == {"status": "AUTH_ERROR", "http_status": 403}
    assert "AI_PROVIDER_REQUEST_FAILED" in caplog.text
    assert "http_status=403" in caplog.text
    assert secret not in caplog.text


@pytest.mark.asyncio
async def test_gemini_availability_check_distinguishes_quota_from_generic_http_error(monkeypatch):
    import httpx
    from app.ai_provider import check_provider_availability

    monkeypatch.setattr(settings, "ai_api_key", "test-key")
    monkeypatch.setattr(settings, "ai_model", "gemini-2.5-flash")
    monkeypatch.setattr(
        settings, "ai_api_base_url",
        "https://generativelanguage.googleapis.com/v1beta/openai",
    )

    def handler(request):
        return httpx.Response(429, request=request, json={"error": {"message": "quota exceeded"}})

    result = await check_provider_availability(transport=httpx.MockTransport(handler))
    assert result == {"status": "QUOTA_OR_RATE_LIMIT", "http_status": 429}


@pytest.mark.asyncio
async def test_chat_completion_retries_once_after_transient_503(monkeypatch):
    import httpx
    from app import ai_provider

    calls = {"count": 0}

    def handler(request):
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(503, request=request, json={"error": {"message": "temporarily overloaded"}})
        return httpx.Response(200, request=request, json={"choices": [{"message": {"content": "ok"}}]})

    async def no_wait(_seconds):
        return None

    monkeypatch.setattr(ai_provider.asyncio, "sleep", no_wait)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        response = await ai_provider._post_chat_completion(
            client, "https://example.test/v1/chat/completions",
            headers={"Authorization": "Bearer test"}, payload={"model": "test"},
        )

    assert response.status_code == 200
    assert calls["count"] == 2


@pytest.mark.asyncio
async def test_gemini_503_uses_flash_lite_fallback_after_primary_retry(monkeypatch):
    import httpx
    from app import ai_provider

    monkeypatch.setattr(settings, "ai_api_key", "test-key")
    monkeypatch.setattr(settings, "ai_model", "gemini-2.5-flash")
    monkeypatch.setattr(settings, "ai_api_base_url", "https://generativelanguage.googleapis.com/v1beta/openai")
    monkeypatch.setattr(settings, "ai_fallback_models", "gemini-2.5-flash-lite")

    calls = []
    def handler(request):
        body = json.loads(request.content)
        calls.append(body["model"])
        if body["model"] == "gemini-2.5-flash":
            return httpx.Response(503, request=request, json={"error": {"message": "high demand"}})
        return httpx.Response(200, request=request, json={"choices": [{"message": {"content": "ok"}}]})

    async def no_wait(_seconds):
        return None

    monkeypatch.setattr(ai_provider.asyncio, "sleep", no_wait)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        response = await ai_provider._post_chat_completion(
            client, "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
            headers={"Authorization": "Bearer test"}, payload={"model": "gemini-2.5-flash"},
        )

    assert response.status_code == 200
    assert calls == ["gemini-2.5-flash", "gemini-2.5-flash", "gemini-2.5-flash-lite"]


@pytest.mark.asyncio
async def test_gemini_503_fallback_is_not_used_for_non_gemini_provider(monkeypatch):
    import httpx
    from app import ai_provider

    monkeypatch.setattr(settings, "ai_api_base_url", "https://example.test/v1")
    monkeypatch.setattr(settings, "ai_fallback_models", "gemini-2.5-flash-lite")

    calls = []
    def handler(request):
        calls.append(json.loads(request.content)["model"])
        return httpx.Response(503, request=request)

    async def no_wait(_seconds):
        return None

    monkeypatch.setattr(ai_provider.asyncio, "sleep", no_wait)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await ai_provider._post_chat_completion(
                client, "https://example.test/v1/chat/completions",
                headers={}, payload={"model": "configured-model"},
            )
    assert calls == ["configured-model", "configured-model"]


@pytest.mark.asyncio
async def test_chat_completion_does_not_retry_auth_or_quota_errors(monkeypatch):
    import httpx
    from app import ai_provider

    calls = {"count": 0}

    def handler(request):
        calls["count"] += 1
        return httpx.Response(429, request=request, json={"error": {"message": "quota exceeded"}})

    async def no_wait(_seconds):
        return None

    monkeypatch.setattr(ai_provider.asyncio, "sleep", no_wait)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await ai_provider._post_chat_completion(
                client, "https://example.test/v1/chat/completions",
                headers={"Authorization": "Bearer test"}, payload={"model": "test"},
            )

    assert calls["count"] == 1


@pytest.mark.asyncio
async def test_provider_availability_caches_successful_read_only_probe(monkeypatch):
    from types import SimpleNamespace
    import app.ai_provider as ai_provider

    monkeypatch.setattr(
        ai_provider,
        "settings",
        SimpleNamespace(
            ai_api_base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            ai_model="gemini-3.8-flash",
            ai_api_key="test-key",
        ),
    )
    calls = 0

    async def fake_probe(*, transport=None):
        nonlocal calls
        calls += 1
        return {"status": "AVAILABLE"}

    monkeypatch.setattr(ai_provider, "_check_provider_availability_uncached", fake_probe)
    ai_provider._clear_provider_availability_cache()

    first = await ai_provider.check_provider_availability()
    second = await ai_provider.check_provider_availability()

    assert first == second == {"status": "AVAILABLE"}
    assert calls == 1


@pytest.mark.asyncio
async def test_provider_availability_cache_expires_after_success_ttl(monkeypatch):
    from types import SimpleNamespace
    import app.ai_provider as ai_provider

    monkeypatch.setattr(
        ai_provider,
        "settings",
        SimpleNamespace(
            ai_api_base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            ai_model="gemini-3.8-flash",
            ai_api_key="test-key",
        ),
    )
    now = [100.0]
    monkeypatch.setattr(ai_provider, "_provider_cache_now", lambda: now[0])
    calls = 0

    async def fake_probe(*, transport=None):
        nonlocal calls
        calls += 1
        return {"status": "AVAILABLE"}

    monkeypatch.setattr(ai_provider, "_check_provider_availability_uncached", fake_probe)
    ai_provider._clear_provider_availability_cache()

    await ai_provider.check_provider_availability()
    await ai_provider.check_provider_availability()
    now[0] += 61.0
    await ai_provider.check_provider_availability()

    assert calls == 2


@pytest.mark.asyncio
async def test_provider_availability_explicit_transport_bypasses_cache(monkeypatch):
    from types import SimpleNamespace
    import app.ai_provider as ai_provider

    monkeypatch.setattr(
        ai_provider,
        "settings",
        SimpleNamespace(
            ai_api_base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            ai_model="gemini-3.8-flash",
            ai_api_key="test-key",
        ),
    )
    calls = 0

    async def fake_probe(*, transport=None):
        nonlocal calls
        calls += 1
        return {"status": "AVAILABLE"}

    monkeypatch.setattr(ai_provider, "_check_provider_availability_uncached", fake_probe)
    ai_provider._clear_provider_availability_cache()

    await ai_provider.check_provider_availability(transport=object())
    await ai_provider.check_provider_availability(transport=object())

    assert calls == 2



@pytest.mark.asyncio
async def test_entailment_verifier_accepts_strictly_fenced_json_without_relaxing_verdict_checks(monkeypatch):
    import httpx
    import json
    from app.ai_provider import verify_claim_entailment

    monkeypatch.setattr(settings, "ai_api_key", "test-token")
    monkeypatch.setattr(settings, "ai_model", "test-model")
    monkeypatch.setattr(settings, "ai_api_base_url", "https://gateway.example/v1")
    source = {
        "source_id": "SRC-IHTS-FENCE",
        "title": "Règles relatives aux heures supplémentaires",
        "text": "Les heures supplémentaires peuvent ouvrir droit à compensation selon les règles applicables.",
    }
    claim = {
        "source_id": "SRC-IHTS-FENCE",
        "text": "Les heures supplémentaires peuvent ouvrir droit à compensation.",
    }

    def handler(request):
        payload = {
            "verdicts": [{
                "claim_index": 0,
                "source_id": "SRC-IHTS-FENCE",
                "verdict": "SUPPORTED",
                "support_quote": "Les heures supplémentaires peuvent ouvrir droit à compensation",
            }]
        }
        fence = chr(96) * 3
        return httpx.Response(200, json={
            "choices": [{"message": {"content": fence + "json\n" + json.dumps(payload) + "\n" + fence}}]
        })

    real_async_client = httpx.AsyncClient
    def fake_async_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_async_client(*args, **kwargs)
    monkeypatch.setattr(httpx, "AsyncClient", fake_async_client)

    result = await verify_claim_entailment(
        question="Les heures supplémentaires peuvent-elles être compensées ?",
        claims=[claim],
        sources=[source],
    )
    assert result["valid"] is True
    assert result["supported_claim_indices"] == [0]



def test_research_plan_parser_accepts_strictly_fenced_json():
    payload = """```json
    {"queries": ["recherche juridique ciblée sur le mécanisme applicable"],
     "legal_issues": ["Fondement et conditions du mécanisme"]}
    ```"""
    plan = _parse_research_plan(payload)
    assert plan is not None
    assert len(plan.queries) == 1


@pytest.mark.asyncio
async def test_source_relevance_evaluator_accepts_fenced_json(monkeypatch):
    import httpx
    from app.ai_provider import evaluate_source_relevance

    monkeypatch.setattr(settings, "ai_api_key", "test-key")
    monkeypatch.setattr(settings, "ai_model", "test-model")
    monkeypatch.setattr(settings, "ai_api_base_url", "https://example.test/v1")

    def handler(request):
        return httpx.Response(200, json={"choices": [{
            "message": {"content": ' ```json\n{"items":[{"source_id":"DOC-FENCE","verdict":"DIRECT"}]}\n``` '}
        }]})

    real_async_client = httpx.AsyncClient
    def fake_async_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_async_client(*args, **kwargs)
    monkeypatch.setattr(httpx, "AsyncClient", fake_async_client)

    result = await evaluate_source_relevance(
        question="Question sur le régime juridique",
        research_axes=["fondement juridique"],
        sources=[{"source_id":"DOC-FENCE","source_type":"LEGIFRANCE_API",
                  "title":"Texte officiel","excerpt":"Le texte fixe les conditions applicables."}],
    )
    assert result == {"DOC-FENCE":"DIRECT"}


def test_usable_sources_reject_malformed_citation_integrity_metadata():
    from app.ai_provider import _usable_document_sources

    base = {
        "source_type": "LEGIFRANCE_API",
        "source_id": "LEGIARTI000012345678",
        "requested_effective_date": "2026-11-21",
        "excerpt": "Extrait officiel daté suffisamment long pour une analyse documentaire.",
    }
    malformed = [
        {**base, "citation_integrity": "valid"},
        {**base, "citation_integrity": ["valid"]},
        {**base, "citation_integrity": 1},
    ]
    assert _usable_document_sources(malformed) == []


def test_entailment_verdict_validation_fails_closed_on_malformed_inputs():
    from app.ai_provider import validate_entailment_verdicts

    valid_claim = {
        "source_id": "SRC-123456",
        "text": "Les heures supplémentaires ouvrent droit à compensation.",
    }
    valid_verdict = {
        "claim_index": 0,
        "source_id": "SRC-123456",
        "verdict": "SUPPORTED",
        "support_quote": "Les heures supplémentaires ouvrent droit à compensation.",
    }
    assert validate_entailment_verdicts(
        {"verdicts": [valid_verdict]}, [None], [],
    )["invalid"] == ["missing_or_invalid_claims"]
    assert validate_entailment_verdicts(
        {"verdicts": [valid_verdict]}, [valid_claim], [None, "bad-source"],
    )["invalid"] == ["verdict_0:source_missing_or_ambiguous"]
    assert validate_entailment_verdicts(
        {"verdicts": [valid_verdict]}, [valid_claim], None,
    )["invalid"] == ["verdict_0:source_missing_or_ambiguous"]


@pytest.mark.asyncio
async def test_entailment_verifier_rejects_malformed_claim_and_source_collections(monkeypatch):
    from app.ai_provider import verify_claim_entailment

    monkeypatch.setattr(settings, "ai_api_key", "test-token")
    monkeypatch.setattr(settings, "ai_model", "test-model")
    monkeypatch.setattr(settings, "ai_api_base_url", "https://gateway.example/v1")
    assert (await verify_claim_entailment(
        question="Question", claims=[None], sources=[],
    ))["invalid"] == ["missing_or_invalid_claims"]
    assert (await verify_claim_entailment(
        question="Question", claims=[{"source_id": "SRC-123"}], sources=None,
    ))["invalid"] == ["missing_or_invalid_sources"]


def test_source_relevance_verdict_parser_ignores_unhashable_and_malformed_values():
    from app.ai_provider import validate_source_relevance_verdicts

    result = validate_source_relevance_verdicts(
        {"items": [
            {"source_id": ["SRC-1"], "verdict": "DIRECT"},
            {"source_id": "SRC-1", "verdict": ["DIRECT"]},
            {"source_id": "SRC-1", "verdict": "DIRECT"},
        ]},
        [{"source_id": "SRC-1"}],
    )
    assert result == {"SRC-1": "DIRECT"}
    assert validate_source_relevance_verdicts({"items": []}, None) == {}


@pytest.mark.asyncio
async def test_ai_payload_ignores_malformed_nested_source_metadata(monkeypatch):
    import json
    import httpx

    monkeypatch.setattr(settings, "ai_api_key", "test-key")
    monkeypatch.setattr(settings, "ai_model", "test-model")
    monkeypatch.setattr(settings, "ai_api_base_url", "https://example.test/v1")
    captured = {}

    def handler(request):
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json={
            "choices": [{"message": {"content": json.dumps({"claims": []})}}],
            "usage": {},
        })

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.ai_provider.httpx.AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    await analyze_question(
        question="Question sur un agent territorial",
        employer="NATIONAL",
        facts_date="2026-01-01",
        sources=[{
            "source_type": "LEGIFRANCE_API",
            "source_id": "LEGIARTI000012345678",
            "requested_effective_date": "2026-01-01",
            "excerpt": "Extrait officiel suffisamment long pour l'analyse documentaire.",
            "raw_metadata": "not-json-object",
            "legal_assurance": "malformed",
        }],
    )
    source = json.loads(
        captured["payload"]["messages"][1]["content"]
    )["extraits_documentaires_valides"][0]
    assert source["code_publication_jurisprudentielle"] is None
    assert source["numero_ecli"] is None
    assert source["niveau_autorite"] is None


@pytest.mark.asyncio
async def test_research_planner_sanitizes_malformed_optional_context(monkeypatch):
    import httpx
    from app.ai_provider import plan_legal_research

    monkeypatch.setattr(settings, "ai_api_key", "test-key")
    monkeypatch.setattr(settings, "ai_model", "test-model")
    monkeypatch.setattr(settings, "ai_api_base_url", "https://example.test/v1")

    def handler(request):
        return httpx.Response(200, json={
            "choices": [{
                "message": {"content": json.dumps({
                    "queries": ["droit au congé annuel fonction publique territoriale"],
                    "legal_issues": ["conditions du congé annuel"],
                    "extracted_facts": [],
                })}
            }],
            "usage": {},
        })

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.ai_provider.httpx.AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    result = await plan_legal_research(
        question="Quels sont mes droits aux congés annuels ?",
        employer="NATIONAL",
        facts_period="malformed",
        legal_context="malformed",
        conversation_history=[None, "bad-history-record", {"role": "user", "content": "Question précédente"}],
        previous_queries="not-a-list",
        retrieved_evidence={"not": "a-list"},
    )
    assert result is not None
    assert result.queries == ["droit au congé annuel fonction publique territoriale"]


@pytest.mark.asyncio
async def test_metadata_only_retrieval_cannot_suppress_required_research_queries(monkeypatch):
    import httpx
    from app.ai_provider import plan_legal_research, AIProviderUnavailable

    monkeypatch.setattr(settings, "ai_api_key", "test-key")
    monkeypatch.setattr(settings, "ai_model", "test-model")
    monkeypatch.setattr(settings, "ai_api_base_url", "https://example.test/v1")

    def handler(request):
        return httpx.Response(200, json={
            "choices": [{
                "message": {"content": json.dumps({
                    "queries": [],
                    "legal_issues": ["conditions d'application"],
                    "extracted_facts": [],
                })}
            }],
            "usage": {},
        })

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.ai_provider.httpx.AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    with pytest.raises(AIProviderUnavailable):
        await plan_legal_research(
            question="Quels sont mes droits ?",
            employer="NATIONAL",
            retrieved_evidence=[{
                "source_id": "SEARCH-HIT-001",
                "title": "Résultat de recherche",
                "content_kind": "METADATA",
            }],
        )


def test_entailment_verdict_validation_rejects_unhashable_claim_source_ids():
    from app.ai_provider import validate_entailment_verdicts

    result = validate_entailment_verdicts(
        {"verdicts": [{
            "claim_index": 0,
            "source_id": ["SRC-123"],
            "verdict": "SUPPORTED",
            "support_quote": "Une citation suffisamment longue pour le contrôle documentaire.",
        }]},
        [{"source_id": ["SRC-123"], "text": "Une citation suffisamment longue pour le contrôle documentaire."}],
        [{"source_id": "SRC-123", "excerpt": "Une citation suffisamment longue pour le contrôle documentaire."}],
    )
    assert result["valid"] is False
    assert result["invalid"] == ["verdict_0:invalid_claim_source_id"]


@pytest.mark.asyncio
async def test_entailment_verifier_rejects_unhashable_claim_source_id_before_http(monkeypatch):
    from app.ai_provider import verify_claim_entailment

    monkeypatch.setattr(settings, "ai_api_key", "test-token")
    monkeypatch.setattr(settings, "ai_model", "test-model")
    monkeypatch.setattr(settings, "ai_api_base_url", "https://gateway.example/v1")
    result = await verify_claim_entailment(
        question="Question",
        claims=[{"source_id": ["SRC-123"], "text": "Une affirmation juridique suffisamment longue."}],
        sources=[{"source_id": "SRC-123", "excerpt": "Une citation suffisamment longue pour le contrôle documentaire."}],
        facts_period="malformed",
    )
    assert result["valid"] is False
    assert result["invalid"] == ["claim_0:invalid_source_id"]


@pytest.mark.parametrize("versant", ["FPT", "FPE", "FPH"])
def test_research_planner_does_not_infer_versant_from_profession_or_workplace(versant):
    import inspect
    from app.ai_provider import plan_legal_research

    source = inspect.getsource(plan_legal_research)
    assert "N'infère jamais le versant juridique à partir du seul métier ou lieu de travail" in source
    assert "Distingue le lieu d'exercice de l'employeur juridique" in source
    assert "clarification_needed" in source
    assert "infirmière à l'hôpital" in source
    assert "professeur dans un lycée" in source



@pytest.mark.asyncio
async def test_research_planner_records_provider_tokens_and_latency(monkeypatch):
    import httpx
    from app.ai_provider import plan_legal_research

    monkeypatch.setattr(settings, "ai_api_key", "test-key")
    monkeypatch.setattr(settings, "ai_model", "configured-model")
    monkeypatch.setattr(settings, "ai_api_base_url", "https://example.test/v1")

    def handler(request):
        return httpx.Response(200, json={
            "model": "actual-model",
            "choices": [{
                "message": {"content": json.dumps({
                    "queries": ["congé annuel fonction publique territoriale"],
                    "legal_issues": ["conditions du congé annuel"],
                    "extracted_facts": [],
                })}
            }],
            "usage": {"prompt_tokens": 120, "completion_tokens": 35, "total_tokens": 155},
        })

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.ai_provider.httpx.AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    events = []
    result = await plan_legal_research(
        question="Quels sont mes droits aux congés annuels ?",
        employer="NATIONAL",
        usage_events=events,
    )

    assert result is not None
    assert len(events) == 1
    event = events[0]
    assert event["operation"] == "research_planning"
    assert event["provider"] == "openai_compatible"
    assert event["model"] == "actual-model"
    assert event["prompt_tokens"] == 120
    assert event["completion_tokens"] == 35
    assert event["total_tokens"] == 155
    assert event["latency_ms"] >= 0
    assert event["outcome"] == "COMPLETED"


@pytest.mark.asyncio
async def test_research_planner_records_provider_failure_with_unknown_usage(monkeypatch):
    import httpx
    from app.ai_provider import plan_legal_research, AIProviderUnavailable

    monkeypatch.setattr(settings, "ai_api_key", "test-key")
    monkeypatch.setattr(settings, "ai_model", "configured-model")
    monkeypatch.setattr(settings, "ai_api_base_url", "https://example.test/v1")

    def handler(request):
        return httpx.Response(503, json={"error": "unavailable"})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.ai_provider.httpx.AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    events = []
    with pytest.raises(AIProviderUnavailable):
        await plan_legal_research(
            question="Quels sont mes droits ?",
            employer="NATIONAL",
            usage_events=events,
        )

    assert len(events) == 1
    event = events[0]
    assert event["operation"] == "research_planning"
    assert event["provider"] == "openai_compatible"
    assert event["model"] == "configured-model"
    assert event["prompt_tokens"] is None
    assert event["completion_tokens"] is None
    assert event["total_tokens"] is None
    assert event["latency_ms"] >= 0
    assert event["outcome"] == "PROVIDER_ERROR"

@pytest.mark.asyncio
async def test_ai_analysis_payload_prefers_expanded_analysis_excerpt(monkeypatch):
    import json
    import httpx
    from app.ai_provider import analyze_question

    monkeypatch.setattr(settings, "ai_api_key", "test-key")
    monkeypatch.setattr(settings, "ai_model", "test-model")
    monkeypatch.setattr(settings, "ai_api_base_url", "https://example.test/v1")
    captured = {}

    def handler(request):
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"claims": []}'}}], "usage": {}},
        )

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.ai_provider.httpx.AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    display_excerpt = "Extrait court destiné à l'affichage."
    analysis_excerpt = (
        display_excerpt + " " +
        "Clause complémentaire, condition et exception juridique conservées dans le dossier d'analyse."
    )

    await analyze_question(
        question="Question de test sur une disposition",
        employer="NATIONAL",
        facts_date="2026-11-24",
        sources=[{
            "source_type": "LEGIFRANCE_API",
            "source_id": "LEGIARTI000012345678",
            "requested_effective_date": "2026-11-24",
            "excerpt": display_excerpt,
            "analysis_excerpt": analysis_excerpt,
        }],
    )

    payload = json.loads(captured["payload"]["messages"][1]["content"])
    source = payload["extraits_documentaires_valides"][0]
    assert source["extrait"] == analysis_excerpt

@pytest.mark.asyncio
async def test_ai_answer_payload_keeps_prior_assistant_context_separate_from_legal_evidence(monkeypatch):
    import json
    import httpx
    from app.ai_provider import analyze_question

    monkeypatch.setattr(settings, "ai_api_key", "test-key")
    monkeypatch.setattr(settings, "ai_model", "test-model")
    monkeypatch.setattr(settings, "ai_api_base_url", "https://example.test/v1")
    captured = {}

    def handler(request):
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"claims": []}'}}], "usage": {}},
        )

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.ai_provider.httpx.AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    previous_user = "Mon employeur refuse mes heures supplémentaires."
    previous_assistant = "Le deuxième point concerne les conditions de récupération."
    await analyze_question(
        question="Peux-tu détailler le deuxième point ?\n" + previous_user,
        employer="NATIONAL",
        facts_date="2026-11-24",
        conversation_history=[
            {"role": "user", "content": previous_user},
            {"role": "assistant", "content": previous_assistant},
        ],
        sources=[{
            "source_type": "LEGIFRANCE_API",
            "source_id": "LEGIARTI000012345678",
            "requested_effective_date": "2026-11-24",
            "excerpt": "Extrait officiel suffisamment long pour l'analyse documentaire.",
        }],
    )

    payload = json.loads(captured["payload"]["messages"][1]["content"])
    assert payload["contexte_questions_utilisateur"] == [{"content": previous_user}]
    assert payload["contexte_reponse_precedente_non_source"] == [{"content": previous_assistant}]
    assert previous_assistant not in json.dumps(payload["extraits_documentaires_valides"], ensure_ascii=False)


@pytest.mark.asyncio
async def test_research_planner_payload_keeps_prior_assistant_context_non_evidentiary(monkeypatch):
    import json
    import httpx
    from app.ai_provider import plan_legal_research

    monkeypatch.setattr(settings, "ai_api_key", "test-key")
    monkeypatch.setattr(settings, "ai_model", "test-model")
    monkeypatch.setattr(settings, "ai_api_base_url", "https://example.test/v1")
    captured = {}

    def handler(request):
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{
            "message": {"content": json.dumps({
                "queries": ["heures supplémentaires fonction publique"],
                "legal_issues": ["Conditions de récupération des heures supplémentaires"],
                "extracted_facts": [],
                "clarification_needed": None,
            })}
        }], "usage": {}})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.ai_provider.httpx.AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    previous_assistant = "Le deuxième point concerne les conditions de récupération."
    await plan_legal_research(
        question="Peux-tu détailler le deuxième point ?\nMon employeur refuse mes heures supplémentaires.",
        employer="NATIONAL",
        conversation_history=[
            {"role": "user", "content": "Mon employeur refuse mes heures supplémentaires."},
            {"role": "assistant", "content": previous_assistant},
        ],
    )

    payload = json.loads(captured["payload"]["messages"][1]["content"])
    assert payload["previous_assistant_answer_context_not_legal_evidence"] == [
        {"content": previous_assistant}
    ]

@pytest.mark.asyncio
async def test_ai_analysis_payload_uses_full_text_beyond_display_excerpt(monkeypatch):
    import json
    import httpx
    from app.ai_provider import analyze_question

    monkeypatch.setattr(settings, "ai_api_key", "test-key")
    monkeypatch.setattr(settings, "ai_model", "test-model")
    monkeypatch.setattr(settings, "ai_api_base_url", "https://example.test/v1")
    captured = {}
    display_excerpt = "Début du texte officiel. " + ("Disposition générale. " * 1000)
    late_exception = (
        "Toutefois, par dérogation, l'autorité territoriale peut accorder une mesure "
        "après consultation préalable de l'instance compétente."
    )
    full_text = display_excerpt + late_exception

    def handler(request):
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json={
            "choices": [{"message": {"content": '{"claims": []}'}}],
            "usage": {},
        })

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.ai_provider.httpx.AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    await analyze_question(
        question="Quelles sont les conditions et dérogations applicables ?",
        employer="NATIONAL",
        facts_date="2026-11-24",
        sources=[{
            "source_type": "LEGIFRANCE_API",
            "source_id": "LEGIARTI000012345678",
            "excerpt": display_excerpt,
            "full_text": full_text,
            "requested_effective_date": "2026-11-24",
        }],
    )
    payload = json.loads(captured["payload"]["messages"][1]["content"])
    analysis_evidence = payload["extraits_documentaires_valides"][0]["extrait"]
    assert len(analysis_evidence) <= 12000
    assert "Passage intermédiaire non transmis" in analysis_evidence
    assert late_exception in analysis_evidence


@pytest.mark.asyncio
async def test_entailment_verifier_receives_full_text_beyond_display_excerpt(monkeypatch):
    import json
    import httpx
    from app.ai_provider import verify_claim_entailment

    monkeypatch.setattr(settings, "ai_api_key", "test-key")
    monkeypatch.setattr(settings, "ai_model", "test-model")
    monkeypatch.setattr(settings, "ai_api_base_url", "https://example.test/v1")
    display_excerpt = "Début du texte officiel. " + ("Disposition générale. " * 1000)
    late_exception = (
        "Toutefois, par dérogation, l'autorité territoriale peut accorder une mesure "
        "après consultation préalable de l'instance compétente."
    )
    full_text = display_excerpt + late_exception
    captured = {}

    def handler(request):
        payload = json.loads(request.content)
        captured["payload"] = payload
        return httpx.Response(200, json={"choices": [{
            "message": {"content": json.dumps({"verdicts": [{
                "claim_index": 0,
                "source_id": "SRC-LATE-EXCEPTION",
                "verdict": "SUPPORTED",
                "support_quote": late_exception,
            }]})}
        }], "usage": {}})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.ai_provider.httpx.AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    result = await verify_claim_entailment(
        question="La dérogation est-elle possible ?",
        claims=[{
            "source_id": "SRC-LATE-EXCEPTION",
            "text": late_exception,
        }],
        sources=[{
            "source_id": "SRC-LATE-EXCEPTION",
            "source_type": "LEGIFRANCE_API",
            "excerpt": display_excerpt,
            "full_text": full_text,
        }],
    )
    evidence = json.loads(captured["payload"]["messages"][1]["content"])["items_to_verify"][0]
    assert len(evidence["official_text"]) <= 12000
    assert "Passage intermédiaire non transmis" in evidence["official_text"]
    assert late_exception in evidence["official_text"]
    assert result["valid"] is True


def test_claim_validation_uses_full_text_beyond_display_excerpt():
    from app.legal_assurance import validate_claim_evidence

    display_excerpt = "Début du texte officiel. " + ("Disposition générale. " * 1000)
    late_exception = (
        "Toutefois, par dérogation, l'autorité territoriale peut accorder une mesure "
        "après consultation préalable de l'instance compétente."
    )
    source = _claim_source(excerpt=display_excerpt, full_text=display_excerpt + late_exception)
    result = validate_claim_evidence({
        "claims": [{
            "text": late_exception,
            "source_id": source["source_id"],
            "quote": late_exception,
        }]
    }, [source])
    assert result["valid"] is True

def test_bounded_legal_evidence_keeps_retrieved_passage_and_document_ending():
    from app.evidence_text import build_legal_evidence_text

    opening = "OUVERTURE_DU_TEXTE " + ("Disposition initiale. " * 250)
    selected = "PASSAGE_CENTRAL_PERTINENT " + ("Règle et conditions détaillées. " * 80)
    ending = "EXCEPTION_FINALE_IMPORTANTE : sauf dérogation expresse prévue au dernier alinéa."
    full_text = opening + ("Disposition intermédiaire. " * 900) + selected + ("Autres dispositions. " * 500) + ending

    evidence = build_legal_evidence_text(full_text, selected)

    assert len(evidence) <= 12000
    assert "OUVERTURE_DU_TEXTE" in evidence
    assert "PASSAGE_CENTRAL_PERTINENT" in evidence
    assert ending in evidence
    assert "Autres passages du texte officiel" in evidence

@pytest.mark.asyncio
async def test_provider_completion_retries_one_transient_server_error(monkeypatch):
    import httpx
    from app.ai_provider import _post_chat_completion

    responses = [
        httpx.Response(503, request=httpx.Request("POST", "https://provider.test/chat/completions")),
        httpx.Response(200, json={"choices": []}, request=httpx.Request("POST", "https://provider.test/chat/completions")),
    ]

    class FakeClient:
        calls = 0

        async def post(self, url, *, headers, json):
            self.calls += 1
            return responses.pop(0)

    async def no_sleep(_):
        return None

    monkeypatch.setattr("app.ai_provider.asyncio.sleep", no_sleep)
    client = FakeClient()
    response = await _post_chat_completion(
        client, "https://provider.test/chat/completions", headers={}, payload={}
    )

    assert response.status_code == 200
    assert client.calls == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [401, 403, 429, 400])
async def test_provider_completion_does_not_retry_auth_quota_or_client_errors(status_code):
    import httpx
    from app.ai_provider import _post_chat_completion

    class FakeClient:
        calls = 0

        async def post(self, url, *, headers, json):
            self.calls += 1
            return httpx.Response(
                status_code,
                request=httpx.Request("POST", "https://provider.test/chat/completions"),
            )

    client = FakeClient()
    with pytest.raises(httpx.HTTPStatusError):
        await _post_chat_completion(
            client, "https://provider.test/chat/completions", headers={}, payload={}
        )

    assert client.calls == 1

@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [500, 502, 504])
async def test_provider_completion_retries_transient_server_errors_without_model_fallback(
    monkeypatch, status_code,
):
    import httpx
    from app.ai_provider import _post_chat_completion

    monkeypatch.setattr(settings, "ai_api_base_url", "https://provider.test/v1")
    calls = []
    request = httpx.Request("POST", "https://provider.test/chat/completions")

    class FakeClient:
        async def post(self, url, *, headers, json):
            calls.append(json.get("model"))
            return httpx.Response(status_code, request=request)

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr("app.ai_provider.asyncio.sleep", no_sleep)
    with pytest.raises(httpx.HTTPStatusError):
        await _post_chat_completion(
            FakeClient(), "https://provider.test/chat/completions",
            headers={}, payload={"model": "primary-model"},
        )

    # 500/502/504 get one bounded retry; unlike a capacity-only 503, they
    # must not silently switch to a different model.
    assert calls == ["primary-model", "primary-model"]

@pytest.mark.asyncio
async def test_gemini_model_not_found_uses_only_configured_fallback_model(monkeypatch):
    import httpx
    from app import ai_provider

    monkeypatch.setattr(settings, "ai_api_base_url", "https://generativelanguage.googleapis.com/v1beta/openai")
    monkeypatch.setattr(settings, "ai_fallback_models", "gemini-fallback-model")
    calls = []

    def handler(request):
        model = json.loads(request.content)["model"]
        calls.append(model)
        if model == "gemini-primary-model":
            return httpx.Response(
                404, request=request,
                json={"error": {"status": "NOT_FOUND", "message": "models/gemini-primary-model is not found"}},
            )
        return httpx.Response(
            200, request=request,
            json={"choices": [{"message": {"content": "ok"}}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        response = await ai_provider._post_chat_completion(
            client,
            "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
            headers={"Authorization": "Bearer test"},
            payload={"model": "gemini-primary-model"},
        )

    assert response.status_code == 200
    assert calls == ["gemini-primary-model", "gemini-fallback-model"]


@pytest.mark.asyncio
async def test_gemini_unrelated_404_does_not_try_another_model(monkeypatch):
    import httpx
    from app import ai_provider

    monkeypatch.setattr(settings, "ai_api_base_url", "https://generativelanguage.googleapis.com/v1beta/openai")
    monkeypatch.setattr(settings, "ai_fallback_models", "gemini-fallback-model")
    calls = []

    def handler(request):
        calls.append(json.loads(request.content)["model"])
        return httpx.Response(404, request=request, json={"error": {"message": "route not found"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await ai_provider._post_chat_completion(
                client,
                "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                headers={"Authorization": "Bearer test"},
                payload={"model": "gemini-primary-model"},
            )

    assert calls == ["gemini-primary-model"]

