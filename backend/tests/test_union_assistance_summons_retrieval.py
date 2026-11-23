from app.legal_search_plan import (
    build_official_research_axes,
    build_official_search_queries,
    build_official_search_query,
)


QUESTION = (
    "Je suis titulaire de la fonction publique territoriale, je voudrais savoir "
    "si je peux être accompagné d'un syndicat lors d'une convocation par ma hiérarchie"
)


def test_union_assistance_summons_uses_specific_legal_mechanisms():
    primary = build_official_search_query(QUESTION)
    queries = build_official_search_queries(QUESTION)
    axes = build_official_research_axes(QUESTION)

    assert "droits de la défense" in primary.lower()
    assert "défenseur de son choix" in primary.lower()
    assert any("procédure disciplinaire" in query.lower() for query in queries)
    assert any("entretien ordinaire" in query.lower() for query in queries)
    assert any("défenseur de son choix" in axis.lower() for axis in axes)
    assert not any("autorisations speciales absence syndicale" in query.lower() for query in queries)
    assert not any("crédit temps syndical" in query.lower() for query in queries)


def test_general_union_rights_question_keeps_union_rights_route():
    question = "Quels sont les droits syndicaux dans une collectivité territoriale ?"
    queries = build_official_search_queries(question)

    assert any("CGFP livre II droit syndical" in query for query in queries)
    assert not any("défenseur de son choix" in query.lower() for query in queries)


def test_summons_without_union_assistance_does_not_force_disciplinary_route():
    question = "Ma hiérarchie me convoque pour faire un point sur mon organisation de travail."
    primary = build_official_search_query(question)

    assert "droits de la défense" not in primary.lower()
