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
