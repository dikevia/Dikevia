from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "generate_legal_embeddings.py"
SPEC = importlib.util.spec_from_file_location("generate_legal_embeddings", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_embedding_segments_are_prefixed_and_cover_long_text():
    text = ("Le fonctionnaire bénéficie des garanties prévues par le code.\n" * 90).strip()
    segments = MODULE.split_for_embedding(text)
    assert len(segments) > 1
    assert all(segment.strip() for segment in segments)
    assert all(len(segment) <= MODULE.SEGMENT_CHARS for segment in segments)


def test_embedding_segments_reject_empty_text():
    assert MODULE.split_for_embedding("") == []
    assert MODULE.split_for_embedding("   ") == []


def test_normalized_mean_returns_unit_vector():
    vector = MODULE.normalized_mean([[3.0, 0.0], [0.0, 4.0]])
    assert len(vector) == 2
    assert abs(sum(value * value for value in vector) - 1.0) < 1e-9


def test_model_dimensions_are_explicit():
    assert MODULE.MODEL_NAME == "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    assert MODULE.DIMENSIONS == 384

def test_browser_query_embedding_uses_the_same_segmenting_and_aggregation_contract():
    worker = (Path(__file__).resolve().parents[2] / "frontend" / "legal-embedding-worker.js").read_text(encoding="utf-8")
    assert 'const SEGMENT_CHARS = 500;' in worker
    assert 'const SEGMENT_OVERLAP = 60;' in worker
    assert '.normalize("NFC")' in worker
    assert 'pooling: "mean", normalize: true' in worker
    assert 'const embedding = normalizedMean(vectors);' in worker
    assert 'const embedding = await extractor(text.slice(0, 5000)' not in worker
