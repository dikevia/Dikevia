from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "compare_legal_embedding_parity.py"
SPEC = importlib.util.spec_from_file_location("compare_legal_embedding_parity", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def _payload(engine: str, model: str, vector: list[float], text: str = "Question juridique") -> dict:
    return {
        "engine": engine,
        "model": model,
        "dimensions": 384,
        "items": [{
            "id": "case-1",
            "text": text,
            "text_sha256": MODULE.text_hash(text),
            "embedding": vector,
        }],
    }


def test_text_hash_normalizes_unicode_and_limits_query_length():
    assert MODULE.text_hash("e\u0301") == MODULE.text_hash("é")
    assert MODULE.text_hash("a" * 5000 + "x") == MODULE.text_hash("a" * 5000 + "y")


def test_query_segmentation_matches_the_corpus_embedding_contract():
    from importlib.util import spec_from_file_location, module_from_spec

    corpus_script = Path(__file__).resolve().parents[2] / "scripts" / "generate_legal_embeddings.py"
    spec = spec_from_file_location("generate_legal_embeddings_for_parity", corpus_script)
    corpus = module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(corpus)
    text = ("Une question juridique avec plusieurs conditions et exceptions.\\n" * 40)[:5000]
    assert MODULE.split_for_query_embedding(text) == corpus.split_for_embedding(text)


def test_query_embedding_averages_segment_vectors_before_normalizing():
    class FakeModel:
        def __init__(self):
            self.seen = []

        def embed(self, segments):
            self.seen.extend(segments)
            return iter([[3.0] + [0.0] * 383, [0.0, 4.0] + [0.0] * 382])

    model = FakeModel()
    vector = MODULE.embed_query_text(model, "x" * 501)
    assert len(model.seen) == 2
    assert vector[0] == pytest.approx(0.6)
    assert vector[1] == pytest.approx(0.8)


def test_cosine_similarity_of_identical_vectors_is_one():
    vector = [1.0] + [0.0] * 383
    assert MODULE.cosine_similarity(vector, vector) == pytest.approx(1.0)


def test_compare_reports_cosine_and_absolute_errors():
    left = [1.0] + [0.0] * 383
    right = [0.99, 0.01] + [0.0] * 382
    result = MODULE.compare_payloads(
        _payload("transformers.js", MODULE.BROWSER_MODEL_NAME, left),
        _payload("fastembed", MODULE.MODEL_NAME, right),
    )
    assert result["status"] == "MEASURED_NOT_CERTIFIED"
    assert result["count"] == 1
    assert result["cosine_min"] == pytest.approx(MODULE.cosine_similarity(left, right))
    assert result["items"][0]["max_absolute_error"] == pytest.approx(0.01)


def test_compare_rejects_different_texts_even_when_ids_match():
    left = _payload("transformers.js", MODULE.BROWSER_MODEL_NAME, [1.0] + [0.0] * 383)
    right = _payload("fastembed", MODULE.MODEL_NAME, [1.0] + [0.0] * 383, "Autre question")
    with pytest.raises(ValueError, match="textes normalisés diffèrent"):
        MODULE.compare_payloads(left, right)


def test_compare_rejects_model_or_engine_mismatch():
    vector = [1.0] + [0.0] * 383
    browser = _payload("transformers.js", "wrong-model", vector)
    reference = _payload("fastembed", MODULE.MODEL_NAME, vector)
    with pytest.raises(ValueError, match="Modèle navigateur inattendu"):
        MODULE.compare_payloads(browser, reference)


def test_compare_rejects_non_finite_or_wrong_dimension_vectors():
    bad = _payload("transformers.js", MODULE.BROWSER_MODEL_NAME, [1.0] * 383)
    good = _payload("fastembed", MODULE.MODEL_NAME, [1.0] * 384)
    with pytest.raises(ValueError, match="384 dimensions"):
        MODULE.compare_payloads(bad, good)
