from app.legal_search_plan import build_official_search_query, build_official_search_queries


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


def test_non_union_question_keeps_existing_single_query_behavior():
    question = "Mon employeur ne renouvelle pas mon CDD"
    assert build_official_search_queries(question) == [
        build_official_search_query(question)
    ]


def test_research_axis_count_can_be_reduced_by_caller():
    queries = build_official_search_queries(
        "Quels sont les droits syndicaux des représentants du personnel ?",
        max_queries=2,
    )
    assert len(queries) == 2
