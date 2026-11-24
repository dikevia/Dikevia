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


def test_browser_worker_matches_python_preprocessing_and_aggregation_contract():
    import json
    import shutil
    import subprocess

    import pytest

    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required to execute the browser worker contract test.")

    root = Path(__file__).resolve().parents[2]
    worker = (root / "frontend" / "legal-embedding-worker.js").read_text(encoding="utf-8")
    worker = "\\n".join(
        line for line in worker.splitlines()
        if not line.startswith('import { env, pipeline }')
    )
    sample = (
        "Le fonctionnaire bénéficie des congés annuels.\\n"
        "L’administration doit motiver sa décision, conformément au code général. "
        "Éléments de situation : temps partiel thérapeutique, agent contractuel. "
    ) * 35
    harness = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(0, 'utf8');
const messages = [];
const seen = [];
const self = { postMessage: value => messages.push(value) };
const pipeline = async (task, model, options) => {
  if (task !== 'feature-extraction' || model !== 'Xenova/paraphrase-multilingual-MiniLM-L12-v2' || options.quantized !== true) {
    throw new Error('Unexpected model contract');
  }
  return async (segment, settings) => {
    if (settings.pooling !== 'mean' || settings.normalize !== true) throw new Error('Unexpected pooling contract');
    seen.push(segment);
    const seed = [...segment].reduce((sum, char) => sum + char.codePointAt(0), 0);
    return { data: Float32Array.from({ length: 384 }, (_, i) => ((seed + i * 17) % 101) / 101 + 0.01) };
  };
};
vm.runInNewContext(source, { self, pipeline, Float32Array, Math, String, Number, Array });
(async () => {
  await self.onmessage({ data: { id: 17, text: process.argv[1] } });
  process.stdout.write(JSON.stringify({ seen, message: messages[0] }));
})().catch(error => { process.stderr.write(String(error)); process.exit(1); });
"""
    result = subprocess.run(
        [node, "-e", harness, sample],
        input=worker,
        text=True,
        capture_output=True,
        check=True,
        timeout=15,
    )
    payload = json.loads(result.stdout)
    expected_segments = MODULE.split_for_embedding(sample[:5000])
    assert payload["seen"] == expected_segments

    vectors = []
    for segment in expected_segments:
        seed = sum(ord(char) for char in segment)
        vectors.append([
            float(__import__("struct").unpack("f", __import__("struct").pack("f", ((seed + i * 17) % 101) / 101 + 0.01))[0])
            for i in range(384)
        ])
    expected = MODULE.normalized_mean(vectors)
    actual = payload["message"]["embedding"]
    assert payload["message"]["id"] == 17
    assert len(actual) == 384
    assert max(abs(left - right) for left, right in zip(actual, expected)) < 1e-6
