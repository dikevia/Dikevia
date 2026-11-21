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

def test_staffing_shortage_is_qualified_as_work_conditions_not_unclassified():
    result = qualify_legal_question("Ma direction ne renforce pas des équipes en manque de personnel.")
    assert result["topic"] == "STAFFING_AND_WORK_CONDITIONS"


def test_titular_asking_if_the_collectivity_can_fire_them_is_qualified():
    result = qualify_legal_question("Je suis titulaire, ma collectivité peut-elle me virer ?")
    assert result["topic"] == "TERMINATION_OF_TITULAR"
    assert result["agent_status"] == "TITULAIRE_EXPLICIT"



def test_everyday_understaffing_and_termination_phrasing_is_understood():
    staffing = qualify_legal_question("Dans mon service on n'est pas assez nombreux.")
    termination = qualify_legal_question("Ma collectivité veut me mettre dehors.")
    assert staffing["topic"] == "STAFFING_AND_WORK_CONDITIONS"
    assert termination["topic"] == "TERMINATION_OF_TITULAR"


def test_fpe_and_fph_are_flagged_as_outside_the_product_scope():
    fpe = qualify_legal_question("Je suis fonctionnaire de l'État, puis-je obtenir cette prime ?")
    fph = qualify_legal_question("Je suis agent hospitalier, quels sont mes droits ?")
    assert fpe["scope_status"] == "OUT_OF_SCOPE_FPE"
    assert fph["scope_status"] == "OUT_OF_SCOPE_FPH"
    assert fpe["scope_evidence"]
    assert fph["scope_evidence"]


def test_private_sector_is_flagged_without_transposing_fpt_rules():
    result = qualify_legal_question("Je suis salarié du privé, mon employeur peut-il me sanctionner ?")
    assert result["scope_status"] == "OUT_OF_SCOPE_PRIVATE"


def test_bare_cdd_or_cdi_does_not_prove_fpt_contractual_agent_status():
    cdd = qualify_legal_question("Je suis en CDD, quels sont mes droits ?")
    cdi = qualify_legal_question("Je travaille en CDI.")
    assert cdd["agent_status"] == "EMPLOYMENT_STATUS_AMBIGUOUS"
    assert cdi["agent_status"] == "EMPLOYMENT_STATUS_AMBIGUOUS"


def test_explicit_territorial_contractual_status_remains_recognized():
    result = qualify_legal_question("Je suis agent contractuel en CDD dans une mairie.")
    assert result["agent_status"] == "CONTRACTUEL_EXPLICIT"
    assert result["scope_status"] == "FPT_PRODUCT_SCOPE"


def test_mentioning_private_law_as_a_question_does_not_reclassify_the_agent():
    result = qualify_legal_question("Le Code du travail s'applique-t-il aux agents territoriaux ?")
    assert result["scope_status"] == "FPT_PRODUCT_SCOPE"


def test_everyday_french_wording_routes_common_fpt_topics():
    cases = (
        ("On me refuse mes heures sup.", "WORKING_TIME"),
        ("Je voudrais poser des congés, comment ça marche ?", "LEAVE"),
        ("Mon chef me demande de venir le dimanche.", "WORKING_TIME"),
        ("Je suis en arrêt maladie après un accident de service.", "SICK_LEAVE_AND_SERVICE_INJURY"),
        ("La mairie refuse ma protection fonctionnelle.", "HARASSMENT_AND_PROTECTION"),
        ("On me retire mes heures de décharge syndicale.", "UNION_RIGHTS"),
    )
    for question, expected_topic in cases:
        assert qualify_legal_question(question)["topic"] == expected_topic


def test_status_detection_is_independent_from_topic_and_handles_accents():
    cases = (
        ("Je suis fonctionnaire titulaire et on me sanctionne.", "DISCIPLINE", "TITULAIRE_EXPLICIT"),
        ("Je suis stagiaire et mon congé maladie est refusé.", "SICK_LEAVE_AND_SERVICE_INJURY", "STAGIAIRE_EXPLICIT"),
        ("Je suis agent contractuel, on ne me paie pas mes heures sup.", "WORKING_TIME", "CONTRACTUEL_EXPLICIT"),
    )
    for question, expected_topic, expected_status in cases:
        result = qualify_legal_question(question)
        assert result["topic"] == expected_topic
        assert result["agent_status"] == expected_status


def test_fpe_scope_detection_does_not_trigger_on_a_generic_ministry_mention():
    result = qualify_legal_question(
        "Ma collectivité échange avec le ministère sur les règles applicables aux agents territoriaux."
    )
    assert result["scope_status"] == "FPT_PRODUCT_SCOPE"


def test_fpe_scope_detects_state_agent_wording_without_accents():
    result = qualify_legal_question("Je suis fonctionnaire de l'Etat.")
    assert result["scope_status"] == "OUT_OF_SCOPE_FPE"



def test_short_followup_inherits_only_the_immediately_relevant_prior_question():
    from app.legal_qualification import build_contextual_research_question

    resolved = build_contextual_research_question(
        "Et pour les contractuels ?",
        ["Mon chef refuse de payer mes heures supplémentaires."],
    )
    assert resolved.startswith("Et pour les contractuels ?")
    assert "heures supplémentaires" in resolved


def test_new_independent_question_does_not_inherit_unrelated_history():
    from app.legal_qualification import build_contextual_research_question

    resolved = build_contextual_research_question(
        "Quels sont les droits à congés annuels ?",
        ["Mon chef refuse de payer mes heures supplémentaires."],
    )
    assert resolved == "Quels sont les droits à congés annuels ?"


def test_short_followup_without_prior_question_stays_unchanged():
    from app.legal_qualification import build_contextual_research_question

    assert build_contextual_research_question("Et pour les contractuels ?") == "Et pour les contractuels ?"



def test_followup_context_preserves_topic_and_updates_explicit_agent_status():
    from app.legal_qualification import build_contextual_research_question

    resolved = build_contextual_research_question(
        "Et pour les contractuels ?",
        ["Mon chef refuse de payer mes heures supplémentaires."],
    )
    result = qualify_legal_question(resolved)
    assert result["topic"] == "WORKING_TIME"
    assert result["agent_status"] == "CONTRACTUEL_EXPLICIT"



def test_independent_question_starting_with_et_does_not_inherit_previous_topic():
    from app.legal_qualification import build_contextual_research_question

    question = "Et ensuite, quels sont les délais pour les congés annuels ?"
    assert build_contextual_research_question(
        question,
        ["Mon chef refuse de payer mes heures supplémentaires."],
    ) == question



def test_plural_contractual_status_is_recognized_in_followup_wording():
    assert qualify_legal_question("Et pour les contractuels ?")["agent_status"] == "CONTRACTUEL_EXPLICIT"
    assert qualify_legal_question("Et pour les agentes contractuelles ?")["agent_status"] == "CONTRACTUEL_EXPLICIT"
