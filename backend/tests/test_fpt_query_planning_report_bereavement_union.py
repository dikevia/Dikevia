from app.legal_search_plan import (
    build_official_research_axes,
    build_official_search_queries,
    clarification_for_union_assistance_summons,
)


def test_hierarchical_report_question_gets_three_independent_research_axes():
    question = "Mon chef a fait un rapport contre moi, puis-je le contester ?"
    axes = build_official_research_axes(question)
    queries = build_official_search_queries(question)

    assert len(axes) == 3
    assert any("L137-1" in axis and "L137-4" in axis for axis in axes)
    assert any("L532-4" in axis and "L532-9" in axis for axis in axes)
    assert len(queries) >= 3
    assert any("dossier individuel" in query for query in queries)


def test_bereavement_question_gets_separate_leave_and_proof_research_axes():
    question = "Un agent demande une autorisation d'absence après le décès de son grand-père."
    axes = build_official_research_axes(question)
    queries = build_official_search_queries(question)

    assert len(axes) == 2
    assert any("autorisation speciale absence" in axis for axis in axes)
    assert any("justificatif deces" in axis for axis in axes)
    assert len(queries) >= 2


def test_colloquial_union_assistance_at_hierarchical_summons_requests_clarification():
    question = "Je suis convoqué par sa hiérarchie, puis-je avoir un accompagnement syndical ?"

    clarification = clarification_for_union_assistance_summons(question)

    assert clarification
    assert "entretien hiérarchique ordinaire" in clarification
    assert build_official_research_axes(question) == []


def test_union_assistance_without_a_summons_is_not_misclassified_as_a_convocation():
    question = "Comment fonctionne l'accompagnement syndical dans ma collectivité ?"

    assert clarification_for_union_assistance_summons(question) is None
