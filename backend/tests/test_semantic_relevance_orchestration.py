import pytest

from app import orchestrator as orchestrator_module
from app.ai_provider import AIProviderUnavailable
from app.orchestrator import apply_semantic_source_relevance


@pytest.mark.asyncio
async def test_semantic_verdicts_exclude_irrelevant_and_keep_contextual_sources(monkeypatch):
    async def fake_evaluator(**kwargs):
        assert kwargs["question"] == "Question juridique"
        assert kwargs["research_axes"] == ["axe juridique"]
        return {"source-irrelevant": "IRRELEVANT", "source-contextual": "CONTEXTUAL"}

    monkeypatch.setattr(orchestrator_module, "_source_relevant_to_any_research_axis",
                        lambda axes, source: source["lexical"])
    monkeypatch.setattr(orchestrator_module, "evaluate_source_relevance", fake_evaluator)
    sources = [
        {"source_id": "source-irrelevant", "lexical": True},
        {"source_id": "source-contextual", "lexical": False},
    ]

    await apply_semantic_source_relevance(
        question="Question juridique", research_axes=["axe juridique"], sources=sources,
    )

    assert sources[0]["research_axis_relevant"] is False
    assert sources[0]["semantic_relevance"] == "IRRELEVANT"
    assert sources[1]["research_axis_relevant"] is True
    assert sources[1]["semantic_relevance"] == "CONTEXTUAL"


@pytest.mark.asyncio
async def test_semantic_provider_failure_preserves_lexical_fallback(monkeypatch):
    async def unavailable(**kwargs):
        raise AIProviderUnavailable("provider unavailable")

    monkeypatch.setattr(orchestrator_module, "_source_relevant_to_any_research_axis",
                        lambda axes, source: source["lexical"])
    monkeypatch.setattr(orchestrator_module, "evaluate_source_relevance", unavailable)
    sources = [
        {"source_id": "lexically-relevant", "lexical": True},
        {"source_id": "lexically-unrelated", "lexical": False},
    ]

    await apply_semantic_source_relevance(
        question="Question juridique", research_axes=["axe juridique"], sources=sources,
    )

    assert [item["research_axis_relevant"] for item in sources] == [True, False]
    assert all("semantic_relevance" not in item for item in sources)



@pytest.mark.asyncio
async def test_uncertain_semantic_verdict_does_not_override_lexical_exclusion(monkeypatch):
    async def fake_evaluator(**kwargs):
        return {"source-uncertain": "UNCERTAIN"}

    monkeypatch.setattr(orchestrator_module, "_source_relevant_to_any_research_axis",
                        lambda axes, source: source["lexical"])
    monkeypatch.setattr(orchestrator_module, "evaluate_source_relevance", fake_evaluator)
    sources = [{"source_id": "source-uncertain", "lexical": False}]

    await apply_semantic_source_relevance(
        question="Question juridique", research_axes=["axe juridique"], sources=sources,
    )

    assert sources[0]["research_axis_relevant"] is False
    assert sources[0]["semantic_relevance"] == "UNCERTAIN"


def test_targeted_regulatory_queries_include_current_fpt_citis_and_tpt_texts():
    from app.orchestrator import _build_targeted_regulatory_queries

    citis = _build_targeted_regulatory_queries(
        "Je suis fonctionnaire territorial et je suis en CITIS après un accident de service."
    )
    assert any("87-602" in query and "37-2" in query for query in citis)
    assert any("2026-705" in query for query in citis)

    tpt = _build_targeted_regulatory_queries(
        "Je souhaite demander un temps partiel thérapeutique."
    )
    assert any("87-602" in query and "13-2" in query for query in tpt)
    assert any("2026-705" in query for query in tpt)
    assert any("88-145" in query and "9-1" in query for query in tpt)

    assert _build_targeted_regulatory_queries("Je souhaite un temps partiel à 80 %.") == []


def test_followup_questions_keep_citis_context_for_targeted_regulatory_search():
    from app.legal_qualification import build_contextual_research_question
    from app.orchestrator import _build_targeted_regulatory_queries

    contextual = build_contextual_research_question(
        "Et pour les contractuels ?",
        ["Je suis fonctionnaire territorial et je suis en CITIS après un accident de service."],
    )
    queries = _build_targeted_regulatory_queries(contextual)
    assert any("87-602" in query and "37-2" in query for query in queries)
    assert any("2026-705" in query for query in queries)


def test_targeted_regulatory_queries_name_the_exact_modified_articles():
    from app.orchestrator import _build_targeted_regulatory_queries

    citis = _build_targeted_regulatory_queries("Je suis en CITIS après un accident de service.")
    assert any("article 3 modifie articles 37-2 et 37-9-1" in query for query in citis)

    tpt = _build_targeted_regulatory_queries("Je demande un temps partiel thérapeutique.")
    assert any("article 3 modifie articles 13-2 et 13-5" in query for query in tpt)


def test_targeted_citis_and_therapeutic_part_time_queries_are_branch_specific():
    from app.orchestrator import _build_targeted_regulatory_queries

    fpe_citis = _build_targeted_regulatory_queries(
        "Je demande un CITIS après un accident de service imputable au service.",
        "FPE",
    )
    assert any("86-442" in query and "47-1" in query and "CITIS" in query for query in fpe_citis)
    assert not any("87-602" in query or "88-386" in query for query in fpe_citis)

    fpe_tpt = _build_targeted_regulatory_queries(
        "Je souhaite un temps partiel thérapeutique.",
        "FPE",
    )
    assert any("86-442" in query and "23-1" in query and "23-14" in query for query in fpe_tpt)
    assert not any("87-602" in query or "88-386" in query for query in fpe_tpt)

    fph_citis = _build_targeted_regulatory_queries(
        "Je demande un CITIS après un accident de service imputable au service.",
        "FPH",
    )
    assert any("88-386" in query and "35-2" in query and "35-3" in query for query in fph_citis)
    assert not any("87-602" in query or "86-442" in query for query in fph_citis)

    fph_tpt = _build_targeted_regulatory_queries(
        "Je souhaite un temps partiel thérapeutique.",
        "FPH",
    )
    assert any("88-386" in query and "13-1" in query and "13-14" in query for query in fph_tpt)
    assert not any("87-602" in query or "86-442" in query for query in fph_tpt)


def test_targeted_fpt_health_queries_do_not_inherit_fpe_or_fph_decrees():
    from app.orchestrator import _build_targeted_regulatory_queries

    fpt_citis = _build_targeted_regulatory_queries(
        "Je demande un CITIS après un accident de service imputable au service.",
        "FPT",
    )
    assert any("87-602" in query for query in fpt_citis)
    assert not any("86-442" in query or "88-386" in query for query in fpt_citis)

    fpt_tpt = _build_targeted_regulatory_queries(
        "Je souhaite un temps partiel thérapeutique.",
        "FPT",
    )
    assert any("87-602" in query and "13-2" in query for query in fpt_tpt)
    assert not any("86-442" in query or "88-386" in query for query in fpt_tpt)
