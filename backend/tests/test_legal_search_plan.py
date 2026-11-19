from app.legal_search_plan import build_official_search_query


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
