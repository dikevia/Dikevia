from app.legal_search_plan import (
    build_official_research_axes,
    build_official_search_query,
    build_official_search_queries,
    merge_ai_and_fallback_research_queries,
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
    assert any("jurisprudence administrative" in item for item in queries)
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
    assert any("jurisprudence administrative" in query for query in queries)
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


def test_unknown_evaluation_status_keeps_both_regimes_as_conditional_axes():
    axes = build_official_research_axes(
        "Mon agent de maîtrise m'a fait une évaluation annuelle à charge, puis-je la contester ?"
    )
    assert len(axes) == 2
    assert any("décret 2014-1526" in axis for axis in axes)
    assert any("décret 88-145 article 1-3" in axis for axis in axes)
    assert any("CDD supérieur à un an" in axis for axis in axes)


def test_titular_evaluation_does_not_create_a_contractual_axis():
    question = "Je suis fonctionnaire titulaire et je veux contester mon évaluation annuelle."
    axes = build_official_research_axes(question)
    queries = build_official_search_queries(question)
    assert len(axes) == 1
    assert "décret 2014-1526" in axes[0]
    assert "décret 88-145" not in axes[0]
    assert all("décret 88-145" not in query for query in queries)
    assert any("jurisprudence administrative" in query for query in queries)


def test_six_year_contract_question_does_not_inject_preselected_article_numbers():
    question = (
        "Un agent contractuel de la fonction publique territoriale en CDD peut-il "
        "bénéficier d’un renouvellement au-delà de 6 ans et obtenir un CDI ? "
        "Précise les conditions, l’ancienneté et les interruptions entre contrats."
    )
    query = build_official_search_query(question)
    queries = build_official_search_queries(question)
    axes = build_official_research_axes(question)

    # The deterministic fallback may preserve the subject and broad legal field,
    # but the article selection must come from the live AI research planner and
    # verified official retrieval, not a problem-specific hardcoded article list.
    for article in ("L332-9", "L332-10", "L332-11", "L332-23", "L452-44"):
        assert article not in query
        assert all(article not in item for item in queries)
        assert all(article not in item for item in axes)
    assert "contractuel" in query.casefold()
    assert "CDI" in query



def test_gemini_plan_keeps_independent_fallback_axes_for_compound_health_case():
    question = (
        "Je suis fonctionnaire territorial titulaire dans une mairie. "
        "J’ai été victime d’un accident sur mon lieu de travail, reconnu comme imputable au service. "
        "Après plusieurs mois d’arrêt, le médecin estime que mon état nécessite une reprise "
        "à temps partiel thérapeutique. Mon employeur envisage une disponibilité d’office "
        "et je m’interroge aussi sur le maintien dans l’emploi, le reclassement et les recours."
    )
    fallback_queries = build_official_search_queries(question)
    fallback_axes = build_official_research_axes(question)
    assert len(fallback_axes) >= 2
    assert len(fallback_queries) >= 3

    # Simulate a plausible Gemini plan that identifies the return-to-work and
    # availability issues but omits one of the explicit legal mechanisms.
    ai_queries = [
        "temps partiel thérapeutique fonctionnaire territorial",
        "disponibilité d’office raison de santé fonction publique territoriale",
        "reclassement inaptitude physique agent territorial",
        "recours décision administrative agent public",
        "maintien dans l’emploi collectivité territoriale",
    ]
    merged = merge_ai_and_fallback_research_queries(
        ai_queries, fallback_queries, fallback_axes, max_queries=5,
    )

    assert len(merged) == 5
    assert len(merged) == len(set(merged))
    # Both independent fallback axes survive even when Gemini already
    # supplied the maximum number of queries.
    assert fallback_queries[1] in merged
    assert fallback_queries[2] in merged
    assert merged[:3] == ai_queries[:3]


def test_gemini_plan_is_not_replaced_by_fallback_for_single_topic():
    question = "Ma demande de CITIS après un accident de service est refusée."
    fallback_queries = build_official_search_queries(question)
    fallback_axes = build_official_research_axes(question)
    assert fallback_axes == []

    ai_queries = [
        "CITIS imputabilité au service fonctionnaire territorial",
        "congé invalidité temporaire accident de service",
    ]
    merged = merge_ai_and_fallback_research_queries(
        ai_queries, fallback_queries, fallback_axes, max_queries=5,
    )
    assert merged[:len(ai_queries)] == ai_queries
    assert fallback_queries[1] in merged
    assert len(merged) <= 5


def test_merged_research_queries_respect_the_five_query_budget():
    merged = merge_ai_and_fallback_research_queries(
        [f"axe IA {index}" for index in range(1, 8)],
        [f"recherche de secours {index}" for index in range(1, 5)],
        ["axe de secours A", "axe de secours B", "axe de secours C"],
        max_queries=5,
    )
    assert len(merged) == 5
    assert merged[:3] == ["axe IA 1", "axe IA 2", "axe IA 3"]
    assert "recherche de secours 2" in merged
    assert "recherche de secours 3" in merged

def test_therapeutic_part_time_after_citis_has_a_dedicated_cgfp_and_fpt_decree_axis():
    question = (
        "Je suis fonctionnaire territorial titulaire. Après un CITIS pour accident de service, "
        "je souhaite reprendre à temps partiel pour raison thérapeutique. "
        "Quelles conditions et quelles conséquences sur ma rémunération ?"
    )
    query = build_official_search_query(question)
    queries = build_official_search_queries(question)
    axes = build_official_research_axes(question)

    # The TPT route must retrieve its own CGFP chapter and FPT implementing
    # decree; it must not be diluted into ordinary part-time/IHTS research.
    assert "L823-1" in query
    assert "L823-6" in query
    assert "décret 87-602" in query
    assert any("L823-1" in item and "décret 87-602" in item for item in queries)
    assert any("CITIS" in item and "décret 87-602" in item for item in queries)
    assert not any("heures supplémentaires IHTS" in item for item in queries)
    assert any("L823-1" in item for item in axes)
    assert any("CITIS" in item for item in axes)


def test_plain_language_mi_temps_therapeutique_uses_the_specific_tpt_axis():
    question = "Après mon accident de service, je peux reprendre à mi-temps thérapeutique ?"
    query = build_official_search_query(question)
    queries = build_official_search_queries(question)
    assert "L823-1" in query
    assert any("L823-1" in item for item in queries)
    assert not any("heures supplémentaires IHTS" in item for item in queries)



def test_personal_convenience_availability_targets_decree_86_68_article_21():
    question = "Un agent titulaire peut-il demander une disponibilité pour convenances personnelles ?"
    query = build_official_search_query(question)
    queries = build_official_search_queries(question)

    assert "décret 86-68" in query
    assert "article 21" in query
    assert "convenances personnelles" in query
    assert len(queries) == 3
    assert "décret 86-68" in queries[1]
    assert "article 21" in queries[1]
    assert "réintégration" in queries[2]
    assert all("radiation des cadres" not in item for item in queries)
    assert all("suivi conjoint" not in item for item in queries)
    assert all(len(item) <= 500 for item in queries)


def test_personal_convenience_availability_does_not_get_diluted_by_generic_mobility_route():
    question = "Je souhaite une disponibilité pour convenances personnelles."
    queries = build_official_search_queries(question)
    assert len(queries) == 3
    assert "décret 86-68" in queries[0]
    assert "décret 86-68" in queries[1]
    assert "CGFP positions statutaires" in queries[2]
    assert all("suivi conjoint" not in item for item in queries)


def test_ambiguous_hierarchical_convocation_with_union_support_does_not_assume_procedure():
    question = (
        "Je suis titulaire de la fonction publique territoriale, "
        "puis-je être accompagné d'un syndicat lors d'une convocation par ma hiérarchie ?"
    )

    # The question does not establish whether this is an ordinary interview,
    # an administrative inquiry or disciplinary proceedings. Ask for context
    # before selecting competing legal research routes.
    assert build_official_research_axes(question) == []


def test_explicit_disciplinary_hierarchical_convocation_keeps_both_research_axes():
    question = (
        "Je suis titulaire de la fonction publique territoriale. "
        "Puis-je être accompagné d'un syndicat lors d'une convocation "
        "par ma hiérarchie pour un entretien disciplinaire ?"
    )
    axes = build_official_research_axes(question)
    joined = " ".join(axes).casefold()

    assert any("entretien hiérarchique ordinaire" in axis for axis in axes)
    assert any("procédure disciplinaire" in axis for axis in axes)
    assert "droits de la défense" in joined


def test_agent_assaulted_by_service_user_retrieves_protection_and_workplace_safety_axes():
    question = (
        "Je suis titulaire de la FPT. J'ai été agressé par un usager "
        "et mon chef ne veut pas que je fasse de rapport car il connaît l'usager."
    )
    axes = build_official_research_axes(question)
    joined = " ".join(axes).casefold()

    assert any("protection fonctionnelle" in axis for axis in axes)
    assert any("santé sécurité travail" in axis for axis in axes)
    assert any("rapport circonstancié" in axis for axis in axes)
    assert len(axes) >= 2


def test_required_research_axes_are_deduplicated_and_bounded():
    from app.legal_search_plan import select_required_research_axes

    axes = select_required_research_axes([
        "  axe juridique A   ",
        "axe juridique A",
        "axe juridique B",
        "",
        None,
    ])
    assert axes == ["axe juridique A", "axe juridique B"]


def test_required_research_axes_never_depend_on_model_generated_issue_labels():
    from app.legal_search_plan import select_required_research_axes

    # The orchestrator supplies only deterministic axes derived from the
    # user's wording; LLM planning labels are intentionally not accepted here.
    deterministic_axes = build_official_research_axes(
        "Je suis titulaire. Je suis agressé par un usager et mon chef refuse le rapport."
    )
    selected = select_required_research_axes(deterministic_axes)
    assert selected == deterministic_axes
    assert all(axis in deterministic_axes for axis in selected)


def test_orchestrator_does_not_promote_llm_refinement_labels_to_required_axes():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "app" / "orchestrator.py").read_text()
    assert "refinement.legal_issues" not in source
    assert "research_axes = select_required_research_axes(fallback_axes)" in source
