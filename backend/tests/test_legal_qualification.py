from app.legal_qualification import qualify_legal_question


def test_union_question_is_qualified_before_research_without_inventing_agent_status():
    result = qualify_legal_question(
        "Quels sont les droits syndicaux des représentants du personnel ?",
        "VILLE_SAINT_ETIENNE",
    )
    assert result["target_legal_field"] == "FRENCH_TERRITORIAL_PUBLIC_SERVICE"
    assert result["topic"] == "UNION_RIGHTS"
    assert result["agent_status"] == "NOT_SPECIFIED"
    assert result["employer_document_scope"] == "LOCAL_EMPLOYER_SELECTED"
    assert "VALIDATED_LOCAL_COLLECTIVITY_ACTS_AND_DOCUMENTS" in result["research_priorities"]


def test_explicit_contractual_status_is_detected_but_not_assumed():
    result = qualify_legal_question(
        "Je suis agent contractuel en CDD, mon employeur refuse le renouvellement.",
        "NATIONAL",
    )
    assert result["topic"] == "CONTRACTUAL_EMPLOYMENT"
    assert result["agent_status"] == "CONTRACTUEL_EXPLICIT"
    assert result["employer_document_scope"] == "NATIONAL_CORPUS_ONLY"


def test_unknown_status_remains_unknown_for_working_time_question():
    result = qualify_legal_question("Mon chef m'impose le travail le dimanche.")
    assert result["topic"] == "WORKING_TIME"
    assert result["agent_status"] == "NOT_SPECIFIED"


def test_code_du_travail_is_never_assumed_without_verified_legal_basis():
    result = qualify_legal_question("Puis-je obtenir une prime ?")
    assert result["code_du_travail_rule"] == (
        "DO_NOT_APPLY_WITHOUT_VERIFIED_EXPRESS_LEGAL_BASIS_OR_REFERRAL"
    )
    assert any("not a determination of legal applicability" in item
               for item in result["qualification_limits"])


def test_union_rights_qualification_recognizes_common_short_forms():
    asa = qualify_legal_question("Mon ASA syndicale est refusée.")
    credit = qualify_legal_question("On me retire mon crédit d'heures syndical.")
    assert asa["topic"] == "UNION_RIGHTS"
    assert credit["topic"] == "UNION_RIGHTS"


def test_contractual_status_does_not_override_the_actual_legal_topic():
    result = qualify_legal_question(
        "Je suis contractuel et mon employeur refuse de payer mes heures supplémentaires."
    )
    assert result["topic"] == "WORKING_TIME"
    assert result["agent_status"] == "CONTRACTUEL_EXPLICIT"
