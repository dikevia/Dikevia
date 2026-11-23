from app.orchestrator import _build_targeted_regulatory_queries


def test_fpt_overtime_adds_territorial_and_ihts_official_searches():
    question = (
        "Je suis titulaire de la FPT. Mon chef me demande deux heures "
        "supplémentaires, non payées mais récupérées. Peut-il refuser les IHTS ?"
    )

    queries = _build_targeted_regulatory_queries(question, "FPT")
    joined = " ".join(queries).casefold()

    assert any("2001-623" in query for query in queries)
    assert any("2002-60" in query and "repos compensateur" in query for query in queries)
    assert any("91-875" in query and "délibération" in query for query in queries)
    assert "repos compensateur" in joined
    assert "ihts" in joined


def test_fpt_overtime_templates_are_not_applied_to_other_public_service_branches():
    question = "Je suis agent et j'effectue des heures supplémentaires avec récupération."

    assert _build_targeted_regulatory_queries(question, "FPE") == []
    assert _build_targeted_regulatory_queries(question, "FPH") == []
