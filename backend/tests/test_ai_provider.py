import pytest
from app.ai_provider import analyze_question, SYSTEM_PROMPT, answer_references_are_grounded, _nonnegative_token_count, check_provider_availability
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
async def test_orchestrator_asks_for_situation_period_instead_of_assuming_today():
    from app.schemas import AskRequest
    from app.orchestrator import LegalOrchestrator

    request = AskRequest(employer="NATIONAL", question="Question juridique suffisamment longue")
    response = await LegalOrchestrator().ask(request, organization_id="00000000-0000-0000-0000-000000000001")
    assert response.clarification_question
    assert any("date d'entrée en vigueur" in item for item in response.missing_information)
    assert response.clarification_question


@pytest.mark.asyncio
async def test_orchestrator_requires_end_or_ongoing_for_new_start_date():
    from app.schemas import AskRequest
    from app.orchestrator import LegalOrchestrator

    request = AskRequest(employer="NATIONAL", facts_start_date="2024-01-01",
                         question="Question juridique suffisamment longue")
    response = await LegalOrchestrator().ask(request, organization_id="00000000-0000-0000-0000-000000000001")
    assert response.verification_status == "NON_VERIFIE"
    assert "date de fin" in response.missing_information[0]


@pytest.mark.asyncio
async def test_orchestrator_requires_start_when_only_end_date_is_given():
    from app.schemas import AskRequest
    from app.orchestrator import LegalOrchestrator

    request = AskRequest(employer="NATIONAL", facts_end_date="2024-06-30",
                         question="Question juridique suffisamment longue")
    response = await LegalOrchestrator().ask(request, organization_id="00000000-0000-0000-0000-000000000001")
    assert response.verification_status == "NON_VERIFIE"
    assert "début de la situation" in response.missing_information[0]


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
        assert request.url.query == ""
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

    result = await analyze_question(
        question="Question de test suffisamment longue", employer="NATIONAL",
        facts_date="2026-01-01", sources=[],
    )
    assert result is None  # no network transport is injected in this guard test

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        response = await client.post(
            "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
            headers={"Authorization": "Bearer test-gemini-key"},
            json={"model": "gemini-3.8-flash", "messages": [{"role": "user", "content": "test"}]},
        )
    assert response.status_code == 200


def test_runtime_configuration_accepts_gemini_openai_compatible_endpoint():
    from app.config import Settings, validate_runtime_configuration

    cfg = Settings(
        app_env="test",
        ai_api_base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        ai_api_key="test-gemini-key",
        ai_model="gemini-3.8-flash",
    )
    validate_runtime_configuration(cfg)
