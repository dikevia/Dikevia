import app.orchestrator as orchestrator


def test_relevant_cgfp_snapshot_is_used_when_live_search_returns_no_articles(monkeypatch):
    monkeypatch.setattr(orchestrator, "_source_relevant_for_target", lambda queries, source, target: True)
    monkeypatch.setattr(orchestrator, "_cgfp_article_fpt_eligible", lambda article, target="FPT": True)
    snapshot = {"results": [{"article": "L137-4", "source_id": "snapshot-L137-4"}]}

    assert orchestrator.should_use_cgfp_snapshot_fallback(
        live_issue=None,
        found=snapshot,
        research_queries=["accès au dossier individuel"],
        target_versant="FPT",
        live_sources=[],
    ) is True


def test_irrelevant_live_article_does_not_suppress_relevant_snapshot(monkeypatch):
    monkeypatch.setattr(orchestrator, "_source_relevant_for_target", lambda queries, source, target: source.get("relevant", False))
    monkeypatch.setattr(orchestrator, "_cgfp_article_fpt_eligible", lambda article, target="FPT": True)
    snapshot = {"results": [{"article": "L137-4", "source_id": "snapshot-L137-4", "relevant": True}]}
    live = [{"source_type": "LEGIFRANCE_API", "source_id": "live-irrelevant", "relevant": False}]

    assert orchestrator.should_use_cgfp_snapshot_fallback(
        live_issue=None,
        found=snapshot,
        research_queries=["accès au dossier individuel"],
        target_versant="FPT",
        live_sources=live,
    ) is True


def test_relevant_live_cgfp_article_suppresses_snapshot_fallback(monkeypatch):
    monkeypatch.setattr(orchestrator, "_source_relevant_for_target", lambda queries, source, target: True)
    monkeypatch.setattr(orchestrator, "_cgfp_article_fpt_eligible", lambda article, target="FPT": True)
    snapshot = {"results": [{"article": "L137-4", "source_id": "snapshot-L137-4"}]}
    live = [{"source_type": "LEGIFRANCE_API", "source_id": "live-L137-4"}]

    assert orchestrator.should_use_cgfp_snapshot_fallback(
        live_issue=None,
        found=snapshot,
        research_queries=["accès au dossier individuel"],
        target_versant="FPT",
        live_sources=live,
    ) is False
