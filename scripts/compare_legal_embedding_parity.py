#!/usr/bin/env python3
"""Generate FastEmbed reference vectors and compare them with browser vectors.

Input JSON: {"items": [{"id": "case-1", "text": "question juridique"}]}
The browser export must use the same ids and texts. No database is accessed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import unicodedata
from pathlib import Path
from typing import Any

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
BROWSER_MODEL_NAME = "Xenova/paraphrase-multilingual-MiniLM-L12-v2"
DIMENSIONS = 384
MAX_QUERY_CHARS = 5000


def text_hash(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value[:MAX_QUERY_CHARS])
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def validate_items(items: Any, label: str) -> dict[str, dict[str, Any]]:
    if not isinstance(items, list) or not items:
        raise ValueError(f"{label}: 'items' doit être une liste non vide.")
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            raise ValueError(f"{label}: chaque élément doit être un objet.")
        identifier, text = item.get("id"), item.get("text")
        if not isinstance(identifier, str) or not identifier.strip():
            raise ValueError(f"{label}: identifiant manquant ou invalide.")
        if identifier in result:
            raise ValueError(f"{label}: identifiant dupliqué: {identifier}.")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"{label}: texte absent pour {identifier}.")
        digest = text_hash(text)
        supplied_hash = item.get("text_sha256")
        if supplied_hash is not None and supplied_hash != digest:
            raise ValueError(f"{label}: hash du texte incohérent pour {identifier}.")
        vector = item.get("embedding")
        if vector is not None:
            if not isinstance(vector, list) or len(vector) != DIMENSIONS:
                raise ValueError(f"{label}: vecteur {identifier} doit avoir {DIMENSIONS} dimensions.")
            if any(not isinstance(value, (int, float)) or isinstance(value, bool)
                   or not math.isfinite(value) for value in vector):
                raise ValueError(f"{label}: vecteur {identifier} contient une valeur invalide.")
            norm = math.sqrt(sum(float(value) ** 2 for value in vector))
            if norm == 0:
                raise ValueError(f"{label}: vecteur nul pour {identifier}.")
        result[identifier] = {"id": identifier, "text": text, "text_sha256": digest, "embedding": vector}
    return result


def cosine_similarity(left: list[float], right: list[float]) -> float:
    dot = sum(float(a) * float(b) for a, b in zip(left, right))
    left_norm = math.sqrt(sum(float(value) ** 2 for value in left))
    right_norm = math.sqrt(sum(float(value) ** 2 for value in right))
    if not left_norm or not right_norm:
        raise ValueError("Un vecteur nul ne peut pas être comparé.")
    return dot / (left_norm * right_norm)


def compare_payloads(browser: dict[str, Any], reference: dict[str, Any]) -> dict[str, Any]:
    if browser.get("dimensions") != DIMENSIONS or reference.get("dimensions") != DIMENSIONS:
        raise ValueError("Les deux exports doivent déclarer 384 dimensions.")
    if browser.get("model") != BROWSER_MODEL_NAME:
        raise ValueError("Modèle navigateur inattendu.")
    if reference.get("model") != MODEL_NAME:
        raise ValueError("Modèle FastEmbed inattendu.")
    if browser.get("engine") != "transformers.js" or reference.get("engine") != "fastembed":
        raise ValueError("Moteur d'embedding inattendu.")
    browser_items = validate_items(browser.get("items"), "Navigateur")
    reference_items = validate_items(reference.get("items"), "FastEmbed")
    if browser_items.keys() != reference_items.keys():
        missing_browser = sorted(reference_items.keys() - browser_items.keys())
        missing_reference = sorted(browser_items.keys() - reference_items.keys())
        raise ValueError(f"Identifiants différents. Navigateur absent={missing_browser}; FastEmbed absent={missing_reference}.")
    comparisons = []
    for identifier in sorted(browser_items):
        left, right = browser_items[identifier], reference_items[identifier]
        if left["text_sha256"] != right["text_sha256"]:
            raise ValueError(f"Les textes normalisés diffèrent pour {identifier}.")
        a, b = left["embedding"], right["embedding"]
        if a is None or b is None:
            raise ValueError(f"Vecteur manquant pour {identifier}.")
        cosine = cosine_similarity(a, b)
        comparisons.append({
            "id": identifier,
            "cosine_similarity": round(cosine, 8),
            "mean_absolute_error": round(sum(abs(float(x) - float(y)) for x, y in zip(a, b)) / DIMENSIONS, 10),
            "max_absolute_error": round(max(abs(float(x) - float(y)) for x, y in zip(a, b)), 10),
        })
    cosines = [item["cosine_similarity"] for item in comparisons]
    return {
        "status": "MEASURED_NOT_CERTIFIED",
        "model_pair": {"browser": BROWSER_MODEL_NAME, "fastembed": MODEL_NAME},
        "count": len(comparisons),
        "cosine_min": min(cosines),
        "cosine_mean": round(sum(cosines) / len(cosines), 8),
        "cosine_max": max(cosines),
        "items": comparisons,
        "interpretation": "Mesure numérique descriptive uniquement. La similarité des vecteurs ne démontre pas la pertinence juridique du retrieval.",
    }


def load_json(path: str) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: racine JSON attendue de type objet.")
    return value


def generate_fastembed(input_path: str, output_path: str) -> None:
    payload = load_json(input_path)
    items = validate_items(payload.get("items"), "Entrée")
    try:
        from fastembed import TextEmbedding
    except ImportError as exc:
        raise RuntimeError("FastEmbed absent. Installer backend/requirements-embeddings.txt.") from exc
    model = TextEmbedding(model_name=MODEL_NAME)
    ids = list(items)
    texts = [items[key]["text"][:MAX_QUERY_CHARS] for key in ids]
    vectors = list(model.embed(texts))
    if len(vectors) != len(ids):
        raise RuntimeError("FastEmbed a retourné un nombre inattendu de vecteurs.")
    output_items = []
    for identifier, vector in zip(ids, vectors):
        values = [float(value) for value in vector]
        if len(values) != DIMENSIONS or any(not math.isfinite(value) for value in values):
            raise RuntimeError(f"Vecteur FastEmbed invalide pour {identifier}.")
        output_items.append({
            "id": identifier,
            "text": items[identifier]["text"],
            "text_sha256": items[identifier]["text_sha256"],
            "embedding": values,
        })
    output = {"engine": "fastembed", "model": MODEL_NAME, "dimensions": DIMENSIONS, "items": output_items}
    Path(output_path).write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    generate = sub.add_parser("generate-fastembed", help="Générer les vecteurs de référence locaux.")
    generate.add_argument("--input", required=True)
    generate.add_argument("--output", required=True)
    compare = sub.add_parser("compare", help="Comparer un export navigateur et un export FastEmbed.")
    compare.add_argument("--browser", required=True)
    compare.add_argument("--fastembed", required=True)
    compare.add_argument("--output")
    args = parser.parse_args()
    try:
        if args.command == "generate-fastembed":
            generate_fastembed(args.input, args.output)
            print(f"Export FastEmbed écrit : {args.output}")
        else:
            result = compare_payloads(load_json(args.browser), load_json(args.fastembed))
            rendered = json.dumps(result, ensure_ascii=False, indent=2)
            if args.output:
                Path(args.output).write_text(rendered + "\n", encoding="utf-8")
            print(rendered)
        return 0
    except Exception as exc:
        print(f"ERREUR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
