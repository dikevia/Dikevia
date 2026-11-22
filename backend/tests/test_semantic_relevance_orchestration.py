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
