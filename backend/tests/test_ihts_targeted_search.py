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


def test_common_everyday_overtime_wording_triggers_fpt_regulatory_searches():
    questions = [
        "Mon chef me demande de faire des heures sup après mes horaires.",
        "Est-ce que mes heures en plus doivent être récupérées ?",
    ]

    for question in questions:
        queries = _build_targeted_regulatory_queries(question, "FPT")
        assert any("2002-60" in query for query in queries)

def test_fpt_overtime_search_uses_currently_relevant_article_numbers():
    queries = _build_targeted_regulatory_queries(
        "Mon chef me demande des heures supplémentaires après mon cycle de travail.",
        "FPT",
    )
    joined = " ".join(queries).casefold()

    assert any("2000-815" in query and "articles 3 et 4" in query for query in queries)
    territorial = next(query for query in queries if "2001-623" in query)
    assert "articles 1 et 4" in territorial
    assert "article 5" not in territorial
    reference = next(query for query in queries if "2002-60" in query)
    assert "articles 3 4 6 et 7" in reference
    assert any("91-875" in query and "article 2" in query for query in queries)
    assert "2002-437" not in joined

