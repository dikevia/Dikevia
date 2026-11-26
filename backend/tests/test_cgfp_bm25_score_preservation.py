import app.cgfp_relevance as cgfp_relevance


def test_conceptual_absence_does_not_multiply_down_bm25_score(monkeypatch):
    base_results = [
        {"article": "L100-1", "score": 10.0, "excerpt": "Texte A"},
        {"article": "L100-2", "score": 8.0, "excerpt": "Texte B"},
    ]
    monkeypatch.setattr(
        cgfp_relevance,
        "_matching_topics",
        lambda query: [{
            "key": "test_topic",
            "expansion": "terme juridique complémentaire",
            "anchors": ["ancrage absent"],
            "exclude_unless_anchor": [],
            "boosts": {},
        }],
    )
    calls = {"count": 0}

    def fake_lexical_search(query, limit=20):
        calls["count"] += 1
        return {"results": base_results if calls["count"] == 1 else []}

    monkeypatch.setattr(cgfp_relevance, "lexical_search", fake_lexical_search)
    monkeypatch.setattr(cgfp_relevance, "get_cgfp_article", lambda ref: {"text": "Texte sans ancrage conceptuel"})

    result = cgfp_relevance.search_cgfp("question juridique de test", limit=8)

    assert [item["article"] for item in result["results"]] == ["L100-1", "L100-2"]
    assert [item["score"] for item in result["results"]] == [10.0, 8.0]
    assert all(not item["matched_concepts"] for item in result["results"])


def test_exclusion_hint_does_not_destroy_original_bm25_score(monkeypatch):
    base_results = [{"article": "L200-1", "score": 7.5, "excerpt": "Texte avec terme exclu"}]
    monkeypatch.setattr(
        cgfp_relevance,
        "_matching_topics",
        lambda query: [{
            "key": "test_topic",
            "expansion": "terme juridique complémentaire",
            "anchors": ["ancrage absent"],
            "exclude_unless_anchor": ["terme exclu"],
            "boosts": {},
        }],
    )
    calls = {"count": 0}

    def fake_lexical_search(query, limit=20):
        calls["count"] += 1
        return {"results": base_results if calls["count"] == 1 else []}

    monkeypatch.setattr(cgfp_relevance, "lexical_search", fake_lexical_search)
    monkeypatch.setattr(cgfp_relevance, "get_cgfp_article", lambda ref: {"text": "Texte avec terme exclu mais sans ancrage"})

    result = cgfp_relevance.search_cgfp("question juridique de test", limit=8)

    assert len(result["results"]) == 1
    assert result["results"][0]["score"] == 7.5
    assert result["results"][0]["relevance_label"] == "Correspondance lexicale — pertinence à vérifier"
