from app.legal_search_plan import (
    build_official_research_axes,
    build_official_search_query,
    build_official_search_queries,
)


def test_annual_evaluation_contestation_targets_cgfp_and_territorial_implementing_decree():
    question = "Mon agent de maîtrise m'as fait une évaluation annuelle à charge, puis-je la contester ?"
    query = build_official_search_query(question)
    queries = build_official_search_queries(question)
    assert "L521-1" in query
    assert "L521-5" in query
    assert "décret 2014-1526" in query
    assert any("CGFP L521-1 L521-3 L521-5" in item for item in queries)
    assert any("décret 2014-1526 articles 2 3 4 5 6 7" in item for item in queries)
    assert any("révision" in item or "revision" in item for item in queries)


def test_overtime_query_targets_fpt_ihts_decrees_and_local_deliberation():
    query = build_official_search_query("On ne me paie pas mes heures supplémentaires")
    assert "heures supplémentaires" in query
    assert "décret 2002-60" in query
    assert "décret 91-875" in query
    assert "délibération" in query


def test_contract_agent_query_targets_the_territorial_contractual_regime():
    query = build_official_search_query("Mon employeur ne renouvelle pas mon CDD")
    assert "agents contractuels territoriaux" in query
    assert "décret 88-145" in query


def test_disciplinary_query_targets_fpt_procedure_and_case_law():
    query = build_official_search_query("Je conteste une sanction disciplinaire")
    assert "fonction publique territoriale" in query
    assert "décret 89-677" in query
    assert "jurisprudence administrative" in query


def test_exact_article_lookup_is_not_broadened():
    question = "Que prévoit l'article L999-999 du CGFP ?"
    assert build_official_search_query(question) == question


def test_query_respects_official_connector_length_limit():
    question = "heures supplémentaires " + ("situation détaillée " * 40)
    assert len(build_official_search_query(question)) <= 500


def test_substantive_question_with_article_reference_still_searches_related_fpt_sources():
    question = "L'article L123-4 n'est pas respecté : mes heures supplémentaires restent impayées."
    query = build_official_search_query(question)
    assert query.startswith(question)
    assert "décret 2002-60" in query
    assert "décret 91-875" in query


def test_short_follow_up_keeps_prior_context_but_expands_current_topic():
    query = build_official_search_query(
        "Et pour les contractuels ?\nQue prévoit l'article L999-999 du CGFP ?"
    )
    assert query.startswith("Et pour les contractuels ?")
    assert "décret 88-145" in query


def test_union_rights_query_targets_current_cgfp_book_ii_and_local_rules():
    query = build_official_search_query(
        "Quels sont les droits syndicaux des représentants du personnel ?"
    )
    assert "CGFP livre II" in query
    assert "exercice du droit syndical" in query
    assert "crédit temps syndical" in query
    assert "délibération" in query
    # The 1985 implementing decree was repealed from 1 February 2025;
    # it must not be promoted as the current legal framework.
    assert "décret 85-397" not in query


def test_union_rights_search_expansion_is_applied_to_short_follow_up():
    query = build_official_search_query("Et pour les locaux syndicaux ?")
    assert query.startswith("Et pour les locaux syndicaux ?")
    assert "CGFP livre II" in query


def test_union_rights_search_expansion_recognizes_asa_and_union_time_credit():
    asa_query = build_official_search_query("Mon ASA syndicale est refusée.")
    credit_query = build_official_search_query("On me retire mon crédit d'heures syndical.")
    assert "CGFP livre II" in asa_query
    assert "CGFP livre II" in credit_query

 
def test_contractual_status_does_not_mask_working_time_search_expansion():
    query = build_official_search_query(
        "Je suis contractuel et mon employeur refuse de payer mes heures supplémentaires."
    )
    assert "décret 2002-60" in query
    assert "décret 88-145" not in query



def test_union_rights_builds_distinct_bounded_research_axes():
    queries = build_official_search_queries(
        "Quels sont les droits syndicaux des représentants du personnel ?"
    )
    assert 2 <= len(queries) <= 3
    assert len(queries) == len(set(queries))
    assert "CGFP livre II" in queries[1]
    assert "autorisations speciales absence syndicale" in queries[2]
    assert all(len(query) <= 500 for query in queries)


def test_unclassified_question_still_searches_the_fpt_framework_and_case_law():
    question = "Est-ce que mon employeur peut me convoquer demain ?"
    queries = build_official_search_queries(question)
    assert len(queries) == 3
    assert queries[0].startswith(question)
    assert "fonction publique territoriale" in queries[0]
    assert "CGFP" in queries[1]
    assert "agent territorial" in queries[2]
    assert "jurisprudence administrative" in queries[2]
    assert all(len(query) <= 500 for query in queries)


def test_research_axis_count_can_be_reduced_by_caller():
    queries = build_official_search_queries(
        "Quels sont les droits syndicaux des représentants du personnel ?",
        max_queries=2,
    )
    assert len(queries) == 2



def test_overtime_builds_fpt_ihts_and_local_implementation_axes():
    queries = build_official_search_queries(
        "Je suis contractuel et mes heures supplémentaires ne sont pas payées."
    )
    assert len(queries) == 3
    assert "décret 2002-60" in queries[0]
    assert "décret 91-875" in queries[1]
    assert "décret 2001-623" in queries[2]
    assert all(len(query) <= 500 for query in queries)


def test_contract_question_builds_specific_territorial_contract_axes():
    queries = build_official_search_queries("Mon employeur ne renouvelle pas mon CDD")
    assert len(queries) == 3
    assert "décret 88-145" in queries[1]
    assert "non renouvellement" in queries[2]


def test_working_time_question_builds_fpt_framework_axes():
    queries = build_official_search_queries("Comment fonctionne l annualisation du temps de travail ?")
    assert len(queries) == 3
    assert "décret 2001-623" in queries[1]
    assert "décret 2000-815" in queries[2]



def test_exact_article_request_does_not_trigger_additional_research_axes():
    question = "Que prévoit l'article L123-4 du CGFP sur les droits syndicaux ?"
    assert build_official_search_queries(question) == [question]



def test_short_follow_up_keeps_previous_legal_topic_for_official_research():
    contextual_question = (
        "Et pour les contractuels ?\n"
        "Quels sont les droits syndicaux des représentants du personnel ?"
    )
    queries = build_official_search_queries(contextual_question)
    assert len(queries) == 3
    assert "Et pour les contractuels ?" in queries[0]
    assert "CGFP livre II" in queries[0]
    assert "droit syndical" in queries[1]
    assert "autorisations speciales absence syndicale" in queries[2]



def test_overtime_does_not_count_as_a_second_generic_working_time_topic():
    queries = build_official_search_queries(
        "Je suis contractuel et mon employeur refuse de payer mes heures supplémentaires."
    )
    assert len(queries) == 3
    assert "IHTS" in " ".join(queries)
    assert "décret 2002-60" in " ".join(queries)
    assert "décret 2000-815" not in " ".join(queries)


def test_compound_question_keeps_union_rights_and_overtime_as_separate_issues():
    question = (
        "Je suis contractuel, mes heures supplémentaires ne sont pas payées "
        "et mon ASA syndicale est refusée."
    )
    queries = build_official_search_queries(question)
    assert len(queries) == 3
    assert "CGFP livre II" in queries[0]
    assert "droit syndical" in queries[1]
    assert "IHTS" in queries[2]
    assert "décret 2002-60" in queries[2]

def test_staffing_shortage_searches_health_safety_and_work_conditions():
    question = "Ma direction ne renforce pas des équipes en manque de personnel."
    queries = build_official_search_queries(question)
    assert len(queries) == 3
    assert "sante securite" in queries[1]
    assert "decret 85-603" in queries[1]
    assert "charge de travail" in queries[2]


def test_titular_termination_searches_radiation_and_cessation_of_functions():
    question = "Je suis titulaire, ma collectivité peut-elle me virer ?"
    queries = build_official_search_queries(question)
    assert len(queries) == 3
    assert "radiation des cadres" in queries[1]
    assert "insuffisance professionnelle" in queries[2]



def test_everyday_understaffing_and_termination_phrasing_builds_legal_queries():
    staffing = build_official_search_queries("Dans mon service on n'est pas assez nombreux.")
    termination = build_official_search_queries("Ma collectivité veut me mettre dehors.")
    assert len(staffing) == 3
    assert "decret 85-603" in staffing[1]
    assert "charge de travail" in staffing[2]
    assert len(termination) == 3
    assert "radiation des cadres" in termination[1]



def test_unfamiliar_plain_language_question_is_not_searched_as_private_sector_law():
    query = build_official_search_query("Mon chef me convoque sans explication.")
    assert "fonction publique territoriale" in query
    assert "agent territorial" in query
    assert "code du travail" not in query

def test_harassment_questions_build_distinct_fpt_and_case_law_search_axes():
    queries = build_official_search_queries("Je subis un harcèlement moral au travail.")
    assert len(queries) == 3
    assert "harcèlement moral" in queries[1]
    assert "agent public territorial" in queries[1]
    assert "jurisprudence administrative" in queries[2]
    assert all("fonction publique territoriale" in query or "territorial" in query for query in queries)


def test_functional_protection_question_builds_fpt_specific_axes():
    queries = build_official_search_queries("Ma collectivité refuse ma demande de protection fonctionnelle.")
    assert len(queries) == 3
    assert "protection fonctionnelle" in queries[1]
    assert "agent territorial" in queries[1]
    assert "Conseil d'État" in queries[2]


def test_disciplinary_question_builds_specific_fpt_research_axes():
    queries = build_official_search_queries("Je conteste une sanction disciplinaire.")
    assert len(queries) == 3
    assert "discipline fonction publique territoriale" in queries[1]
    assert "décret 89-677" in queries[2]


def test_citis_question_builds_specific_territorial_research_axes():
    queries = build_official_search_queries("Ma demande de CITIS après un accident de service est refusée.")
    assert len(queries) == 3
    assert "CITIS agent territorial" in queries[1]
    assert "décret 87-602" in queries[1]
    assert "imputabilité au service" in queries[2]


def test_remuneration_question_builds_fpt_and_local_deliberation_axes():
    queries = build_official_search_queries("Ma collectivité refuse de verser mon IFSE.")
    assert len(queries) == 3
    assert "régime indemnitaire" in queries[1]
    assert "délibération locale" in queries[1]
    assert "décret 91-875" in queries[2]


def test_compound_union_and_disciplinary_question_keeps_both_topics():
    queries = build_official_search_queries(
        "Mon ASA syndicale est refusée et je fais aussi l'objet d'une sanction disciplinaire."
    )
    assert len(queries) == 3
    assert "droit syndical" in queries[1]
    assert "discipline fonction publique territoriale" in queries[2]
    assert all(len(query) <= 500 for query in queries)

def test_trainee_evaluation_question_searches_its_specific_fpt_status_regime():
    question = "Je suis fonctionnaire stagiaire et je veux contester mon évaluation annuelle."
    queries = build_official_search_queries(question)
    assert any("décret 2014-1526" in item for item in queries)
    assert any("décret 92-1194" in item for item in queries)

def test_contractual_evaluation_question_uses_contractual_regime_not_civil_servant_decree():
    question = "Je suis contractuel et je veux contester mon évaluation annuelle."
    query = build_official_search_query(question)
    queries = build_official_search_queries(question)
    axes = build_official_research_axes(question)
    assert "décret 88-145" in query
    assert "CDI" in query
    assert "CDD supérieur à un an" in query
    assert "contrat de projet" in query
    assert "décret 2014-1526" not in query
    assert any("décret 88-145" in item for item in queries)
    assert all("décret 2014-1526" not in item for item in queries)
    assert len(axes) == 1
    assert "décret 88-145" in axes[0]
    assert "décret 2014-1526" not in axes[0]



def test_annual_evaluation_question_does_not_trigger_stagiaire_or_avancement_axes():
    question = (
        "Mon agent de maîtrise m'a fait une évaluation annuelle à charge, "
        "puis-je la contester ?"
    )
    queries = build_official_search_queries(question)
    axes = build_official_research_axes(question)
    joined = " ".join(queries).casefold()
    assert any("décret 2014-1526" in query for query in queries)
    assert any("révision" in query or "revision" in query for query in queries)
    assert "décret 92-1194" not in joined
    assert "reprise ancienneté" not in joined
    assert not any("décret 92-1194" in axis for axis in axes)


def test_contractual_annual_evaluation_does_not_mix_civil_servant_rules():
    question = "Je suis agent contractuel territorial et je veux contester mon évaluation annuelle."
    queries = build_official_search_queries(question)
    axes = build_official_research_axes(question)
    joined = " ".join(queries).casefold()
    assert "décret 88-145" in joined
    assert "décret 2014-1526" not in joined
    assert all("décret 2014-1526" not in axis for axis in axes)


def test_annual_evaluation_with_unknown_status_searches_both_fpt_regimes_separately():
    question = (
        "Mon agent de maîtrise m'a fait une évaluation annuelle à charge, "
        "puis-je la contester ?"
    )
    queries = build_official_search_queries(question)
    joined = " ".join(queries).casefold()

    assert any("décret 2014-1526" in query for query in queries)
    assert any("décret 88-145 article 1-3" in query for query in queries)
    assert any("quinze jours francs" in query for query in queries)
    assert any("commission administrative paritaire" in query or "cap" in query for query in queries)
    assert all(len(query) <= 500 for query in queries)
    assert "décret 92-1194" not in joined
    assert "reprise ancienneté" not in joined


def test_professional_interview_alone_does_not_trigger_career_or_trainee_research():
    queries = build_official_search_queries(
        "Je souhaite contester le compte rendu de mon entretien professionnel annuel."
    )
    joined = " ".join(queries).casefold()
    assert any("décret 2014-1526" in query for query in queries)
    assert any("décret 88-145 article 1-3" in query for query in queries)
    assert "décret 92-1194" not in joined
    assert "reprise ancienneté" not in joined
