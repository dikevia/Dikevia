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
