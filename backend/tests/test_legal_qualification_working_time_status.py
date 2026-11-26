from app.legal_qualification import qualify_legal_question


def test_explicit_non_complete_working_time_is_detected():
    result = qualify_legal_question(
        "Je suis fonctionnaire territorial à temps non complet.",
        public_service="FPT",
    )
    assert result["agent_status"] == "FONCTIONNAIRE_STATUS_UNSPECIFIED"
    assert result["agent_working_time_status"] == "NON_COMPLETE_EXPLICIT"


def test_explicit_full_time_working_time_is_detected():
    result = qualify_legal_question(
        "Je suis fonctionnaire territorial à temps complet.",
        public_service="FPT",
    )
    assert result["agent_status"] == "FONCTIONNAIRE_STATUS_UNSPECIFIED"
    assert result["agent_working_time_status"] == "FULL_TIME_EXPLICIT"


def test_working_time_is_not_inferred_when_not_stated():
    result = qualify_legal_question(
        "Je suis fonctionnaire territorial et je demande un temps partiel thérapeutique.",
        public_service="FPT",
    )
    assert result["agent_working_time_status"] == "NOT_SPECIFIED"

def test_explicit_working_time_is_preserved_across_a_follow_up():
    from app.legal_qualification import build_contextual_research_context

    context = build_contextual_research_context(
        "Et pour le TPT ?",
        prior_user_questions=["Je suis fonctionnaire territorial à temps non complet."],
        prior_assistant_messages=["Voici les règles générales applicables."],
    )
    result = qualify_legal_question(context.question, public_service="FPT")

    assert context.is_followup is True
    assert result["agent_status"] == "FONCTIONNAIRE_STATUS_UNSPECIFIED"
    assert result["agent_working_time_status"] == "NON_COMPLETE_EXPLICIT"
