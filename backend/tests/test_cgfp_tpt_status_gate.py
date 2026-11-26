from app.fpt_scope import classify_public_service_scope


def _tpt_source():
    return {
        "source_type": "LEGIFRANCE_API",
        "title": "Code général de la fonction publique — article L823-1",
        "article": "L823-1",
        "text": "Le fonctionnaire en activité peut être autorisé à accomplir un service à temps partiel pour raison thérapeutique.",
    }


def test_tpt_claim_requires_functionary_and_full_time_status():
    result = classify_public_service_scope(
        _tpt_source(),
        target_versant="FPT",
        agent_status="TITULAIRE_EXPLICIT",
        agent_working_time_status="FULL_TIME_EXPLICIT",
    )
    assert result["claim_eligible"] is True


def test_tpt_claim_is_not_made_for_non_complete_functionary():
    result = classify_public_service_scope(
        _tpt_source(),
        target_versant="FPT",
        agent_status="TITULAIRE_EXPLICIT",
        agent_working_time_status="NON_COMPLETE_EXPLICIT",
    )
    assert result["claim_eligible"] is False


def test_tpt_claim_is_not_made_when_working_time_is_unknown():
    result = classify_public_service_scope(
        _tpt_source(),
        target_versant="FPT",
        agent_status="TITULAIRE_EXPLICIT",
        agent_working_time_status="NOT_SPECIFIED",
    )
    assert result["claim_eligible"] is False
