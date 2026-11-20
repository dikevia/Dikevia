import pytest
from app.ai_provider import analyze_question, SYSTEM_PROMPT, answer_references_are_grounded, _nonnegative_token_count, check_provider_availability, AIAnalysisRefusedNoSources
from app.config import settings

@pytest.mark.asyncio
async def test_ai_provider_is_disabled_without_credentials(monkeypatch):
    monkeypatch.setattr(settings, "ai_api_key", "")
    monkeypatch.setattr(settings, "ai_model", "")
    assert await analyze_question(question="Question suffisamment longue", employer="NATIONAL",
        facts_date=None, sources=[]) is None

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
    assert "Ne bloque pas toute réponse au seul motif que la date des faits manque" in SYSTEM_PROMPT
    assert "source_id" in SYSTEM_PROMPT and "quote" in SYSTEM_PROMPT

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


def test_claim_evidence_accepts_later_administrative_case_law_as_interpretative_source():
    from app.legal_assurance import validate_claim_evidence

    source = _claim_source(
        source_type="LEGIFRANCE_CETAT_FULL_TEXT",
        source_id="CETATEXT000012345678",
        decision_date="2025-02-10",
        temporal_status="DECISION_POSTERIOR_TO_FACTS",
    )
    result = validate_claim_evidence({
        "claims": [{
            "text": "L'agent peut bénéficier d'un repos compensateur selon les conditions fixées.",
            "source_id": source["source_id"],
            "quote": source["excerpt"],
        }]
    }, [source])
    assert result["valid"] is True


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
    assert "Ne transforme pas cette demande en simple exposé général" in SYSTEM_PROMPT


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


def test_system_prompt_requires_conversational_legal_explanations_and_practical_conclusions():
    assert "Tu t'adresses directement à l'agent" in SYSTEM_PROMPT
    assert "explique immédiatement, en langage courant" in SYSTEM_PROMPT
    assert "prends une position juridique explicite et nuancée" in SYSTEM_PROMPT
    assert "Termine par des démarches concrètes" in SYSTEM_PROMPT
    assert "ne présente pas un conseil pratique comme une obligation légale" in SYSTEM_PROMPT


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

    verifier_question = json.loads(captured["payload"]["messages"][1]["content"])["question_actuelle"]
    assert verifier_question == "Mon employeur peut-il refuser de compenser mes heures supplémentaires ?"
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
            "raw_metadata": {"publication_code": "B", "ecli": "ECLI:FR:TA38:2024:2400001", "decision_type": "décision", "recourse_type": "Excès de pouvoir"},
        }],
    )
    payload_sources = json.loads(captured["payload"]["messages"][1]["content"])["extraits_documentaires_valides"]
    assert payload_sources[0]["code_publication_jurisprudentielle"] == "B"
    assert payload_sources[0]["numero_ecli"] == "ECLI:FR:TA38:2024:2400001"
    assert payload_sources[0]["portee_extrait"] == "TOP_RELEVANT_PASSAGE_AND_FINAL_CHUNK_FROM_HASH_VERIFIED_FULL_TEXT"
