import pytest

from app.cross_encoder_reranker import (
    CrossEncoderUnavailable,
    _rank_with_scores,
    _source_passage,
    rerank_sources_with_cross_encoder,
)


def test_cross_encoder_ranking_reorders_without_dropping_or_upgrading_sources():
    sources = [
        {"source_id": "first", "excerpt": "Passage A"},
        {"source_id": "second", "excerpt": "Passage B"},
        {"source_id": "third", "excerpt": "Passage C"},
    ]

    ranked = _rank_with_scores(sources, [0, 1, 2], [0.2, 0.9, 0.4])

    assert [source["source_id"] for source in ranked] == [
        "second", "third", "first",
    ]
    assert {source["source_id"] for source in ranked} == {
        source["source_id"] for source in sources
    }
    assert all(
        ranked_source is original
        for ranked_source in ranked
        for original in sources
        if ranked_source["source_id"] == original["source_id"]
    )


def test_cross_encoder_keeps_uncored_sources_after_the_scored_candidates():
    sources = [
        {"source_id": "candidate-a", "excerpt": "Passage A"},
        {"source_id": "no-text"},
        {"source_id": "candidate-b", "excerpt": "Passage B"},
        {"source_id": "outside-top-k", "excerpt": "Passage C"},
    ]

    ranked = _rank_with_scores(sources, [0, 2], [0.1, 0.8])

    assert [source["source_id"] for source in ranked] == [
        "candidate-b", "candidate-a", "no-text", "outside-top-k",
    ]


def test_cross_encoder_uses_title_and_article_as_passage_context():
    passage = _source_passage({
        "title": "Décret relatif à la NBI",
        "article": "Article 3",
        "excerpt": "Les fonctions éligibles sont définies par décret.",
    })

    assert passage.startswith("Décret relatif à la NBI")
    assert "Article 3" in passage
    assert "fonctions éligibles" in passage


def test_cross_encoder_requires_explicit_local_model_files():
    with pytest.raises(CrossEncoderUnavailable):
        rerank_sources_with_cross_encoder(
            [{"excerpt": "Premier passage"}, {"excerpt": "Deuxième passage"}],
            question="Question juridique",
            onnx_model_path="",
            tokenizer_path="",
        )


def test_cross_encoder_is_disabled_by_default():
    from app.config import Settings

    config = Settings(_env_file=None)

    assert config.legal_cross_encoder_enabled is False
    assert config.legal_cross_encoder_top_k == 30
    assert config.legal_cross_encoder_max_length == 384
