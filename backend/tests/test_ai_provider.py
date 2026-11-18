import pytest
from app.ai_provider import analyze_question, SYSTEM_PROMPT, answer_references_are_grounded, _nonnegative_token_count
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

