"""Optional local ONNX cross-encoder for multilingual legal-source reranking.

The model is never downloaded by the application. Operators must provision the
public model files locally and explicitly enable the feature. Any failure is
handled by the caller, which keeps the deterministic ranking.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import threading
from typing import Any

_RUNTIME_LOCK = threading.Lock()


class CrossEncoderUnavailable(RuntimeError):
    """Raised when the optional local cross-encoder cannot be used."""


@lru_cache(maxsize=2)
def _load_runtime(
    onnx_model_path: str,
    tokenizer_path: str,
    intra_op_threads: int,
):
    try:
        import onnxruntime as ort
        from tokenizers import Tokenizer
    except ImportError as exc:
        raise CrossEncoderUnavailable(
            "onnxruntime et tokenizers doivent être installés pour le cross-encoder."
        ) from exc

    model_file = Path(onnx_model_path)
    tokenizer_file = Path(tokenizer_path)
    if not model_file.is_file() or not tokenizer_file.is_file():
        raise CrossEncoderUnavailable(
            "Fichiers ONNX/tokenizer du cross-encoder introuvables."
        )

    try:
        options = ort.SessionOptions()
        options.intra_op_num_threads = max(1, int(intra_op_threads))
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        session = ort.InferenceSession(
            str(model_file),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        tokenizer = Tokenizer.from_file(str(tokenizer_file))
        pad_id = tokenizer.token_to_id("[PAD]")
        if pad_id is None:
            raise CrossEncoderUnavailable(
                "Le tokenizer du cross-encoder ne déclare pas de token [PAD]."
            )
        return session, tokenizer, pad_id
    except CrossEncoderUnavailable:
        raise
    except Exception as exc:
        raise CrossEncoderUnavailable(
            "Impossible de charger le modèle local de reranking."
        ) from exc


def _source_passage(source: dict[str, Any]) -> str:
    title = str(source.get("title") or "").strip()
    article = str(source.get("article") or source.get("article_id") or "").strip()
    excerpt = ""
    for key in ("analysis_excerpt", "excerpt", "text", "full_text"):
        value = source.get(key)
        if isinstance(value, str) and value.strip():
            excerpt = value.strip()
            break
    if not excerpt:
        return ""
    return "\n".join(part for part in (title, article, excerpt) if part)


def _rank_with_scores(
    sources: list[dict[str, Any]],
    candidate_indices: list[int],
    scores: list[float],
) -> list[dict[str, Any]]:
    if len(candidate_indices) != len(scores):
        raise CrossEncoderUnavailable("Nombre de scores incohérent avec les documents.")
    ranked_indices = [
        index for _, index in sorted(
            zip(scores, candidate_indices),
            key=lambda item: (-float(item[0]), item[1]),
        )
    ]
    selected = set(candidate_indices)
    ordered_indices = ranked_indices + [
        index for index in range(len(sources)) if index not in selected
    ]
    return [sources[index] for index in ordered_indices]


def rerank_sources_with_cross_encoder(
    sources: list[dict[str, Any]],
    *,
    question: str,
    onnx_model_path: str,
    tokenizer_path: str,
    top_k: int = 30,
    max_length: int = 384,
    intra_op_threads: int = 1,
) -> list[dict[str, Any]]:
    """Rerank only the first top_k text-bearing candidates; never filter evidence."""
    if not isinstance(sources, (list, tuple)):
        return []
    records = [source for source in sources if isinstance(source, dict)]
    if len(records) < 2 or not str(question or "").strip():
        return list(records)
    if not onnx_model_path or not tokenizer_path:
        raise CrossEncoderUnavailable("Chemins du modèle et du tokenizer non configurés.")

    limit = max(2, min(100, int(top_k)))
    max_tokens = max(64, min(512, int(max_length)))
    candidate_indices: list[int] = []
    passages: list[str] = []
    for index, source in enumerate(records):
        passage = _source_passage(source)
        if not passage:
            continue
        candidate_indices.append(index)
        passages.append(passage)
        if len(candidate_indices) >= limit:
            break
    if len(candidate_indices) < 2:
        return list(records)

    with _RUNTIME_LOCK:
        session, tokenizer, pad_id = _load_runtime(
            str(onnx_model_path), str(tokenizer_path), max(1, int(intra_op_threads))
        )
        try:
            tokenizer.enable_truncation(max_length=max_tokens)
            tokenizer.enable_padding(pad_id=pad_id, pad_token="[PAD]")
            encodings = tokenizer.encode_batch(
                [(str(question), passage) for passage in passages]
            )
        except Exception as exc:
            raise CrossEncoderUnavailable(
                "Échec de la tokenisation des paires question-document."
            ) from exc

    try:
        import numpy as np

        inputs = {item.name: item for item in session.get_inputs()}
        feed: dict[str, Any] = {}
        values = {
            "input_ids": [encoding.ids for encoding in encodings],
            "attention_mask": [encoding.attention_mask for encoding in encodings],
            "token_type_ids": [encoding.type_ids for encoding in encodings],
        }
        for name, value in values.items():
            if name in inputs:
                feed[name] = np.asarray(value, dtype=np.int64)
        if "input_ids" not in feed or "attention_mask" not in feed:
            raise CrossEncoderUnavailable(
                "Le modèle ONNX ne présente pas les entrées attendues."
            )
        outputs = session.run(None, feed)
        if not outputs:
            raise CrossEncoderUnavailable("Le modèle ONNX n'a retourné aucun score.")
        scores = np.asarray(outputs[0], dtype=np.float32).reshape(-1).tolist()
        if len(scores) != len(candidate_indices):
            raise CrossEncoderUnavailable("Le modèle ONNX a retourné un nombre de scores inattendu.")
    except CrossEncoderUnavailable:
        raise
    except Exception as exc:
        raise CrossEncoderUnavailable("Échec de l'inférence ONNX du cross-encoder.") from exc

    return _rank_with_scores(records, candidate_indices, scores)
