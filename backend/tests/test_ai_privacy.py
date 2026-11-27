from app.ai_privacy import redact_direct_identifiers


def test_direct_personal_identifiers_are_masked_before_provider_transfer():
    value = (
        "Contactez-moi au 06 12 34 56 78 ou à agent@example.fr. "
        "Mon NIR est 1 85 05 42 123 456 78 et mon IBAN "
        "FR76 3000 6000 0112 3456 7890 189."
    )

    result = redact_direct_identifiers(value)

    assert "06 12 34 56 78" not in result
    assert "agent@example.fr" not in result
    assert "1 85 05 42 123 456 78" not in result
    assert "FR76 3000 6000 0112 3456 7890 189" not in result
    assert result.count("MASQU") == 4



def test_provider_payload_minimization_recurses_into_sources_metadata_and_history():
    from app.ai_privacy import redact_provider_payload

    payload = {
        "question": "Décret n° 2002-60 du 14 janvier 2002 : agent@example.fr",
        "documents": [{
            "title": "Dossier de Mme Dupont",
            "excerpt": "Contact : 06 12 34 56 78 ; décision du 24/11/2026.",
            "metadata": {"bank_account": "FR76 3000 6000 0112 3456 7890 189"},
        }],
        "facts": {"age": 42, "ongoing": True},
    }

    sanitized = redact_provider_payload(payload)

    assert "agent@example.fr" not in sanitized["question"]
    assert "06 12 34 56 78" not in sanitized["documents"][0]["excerpt"]
    assert "FR76 3000 6000 0112 3456 7890 189" not in sanitized["documents"][0]["metadata"]["bank_account"]
    assert "14 janvier 2002" in sanitized["question"]
    assert "24/11/2026" in sanitized["documents"][0]["excerpt"]
    assert sanitized["facts"] == {"age": 42, "ongoing": True}


def test_identifier_minimization_preserves_legal_references_dates_and_amounts():
    value = (
        "Le décret n° 2002-60 du 14 janvier 2002, l'article L. 123-4, "
        "la date du 24/11/2026 et un montant de 125 euros."
    )

    assert redact_direct_identifiers(value) == value


def test_identifier_minimization_handles_empty_and_non_string_values():
    assert redact_direct_identifiers(None) == ""
    assert redact_direct_identifiers("") == ""


def test_every_user_text_provider_path_applies_direct_identifier_minimization():
    import inspect

    from app import ai_provider

    provider_functions = (
        ai_provider.evaluate_source_relevance,
        ai_provider.plan_legal_research,
        ai_provider.analyze_question,
        ai_provider.verify_claim_entailment,
    )
    for function in provider_functions:
        assert "redact_direct_identifiers" in inspect.getsource(function), function.__name__
        assert "redact_provider_payload" in inspect.getsource(function), function.__name__



def test_provider_error_logs_never_include_response_body(caplog):
    import httpx

    from app.ai_provider import _log_provider_failure

    response = httpx.Response(
        400,
        request=httpx.Request("POST", "https://provider.invalid/chat/completions"),
        text="Invalid request for agent@example.fr",
    )
    error = httpx.HTTPStatusError(
        "provider rejected request", request=response.request, response=response,
    )

    with caplog.at_level("WARNING", logger="app.ai_provider"):
        _log_provider_failure("privacy_test", error)

    assert "agent@example.fr" not in caplog.text
    assert "http_status=400" in caplog.text
    assert "Invalid request" not in caplog.text


def test_personal_documents_are_excluded_from_ai_without_explicit_opt_in():
    from app.ai_provider import _usable_document_sources, SYSTEM_PROMPT

    source = {
        "source_type": "PERSONAL_DOCUMENT",
        "source_id": "personal-doc-123456",
        "excerpt": "Règlement interne de temps de travail du service.",
        "content_kind": "EXCERPT",
        "reference_role": "PERSONAL_CONTEXT_ONLY",
        "claim_eligible": False,
        "official_source": False,
    }
    assert _usable_document_sources([source]) == []
    assert _usable_document_sources([source], allow_local_documents=True) == [source]
    assert "PERSONAL_DOCUMENT" in SYSTEM_PROMPT
    assert "Ne traite jamais un PERSONAL_DOCUMENT comme un texte normatif" in SYSTEM_PROMPT
