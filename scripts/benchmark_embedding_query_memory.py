#!/usr/bin/env python3
"""Measure FastEmbed memory for one query embedding, without a database connection."""
from fastembed import TextEmbedding

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
model = TextEmbedding(model_name=MODEL_NAME)
vector = next(model.embed([
    "Question juridique : quelles sont les conditions du temps partiel thérapeutique dans la fonction publique territoriale ?"
]))
if len(vector) != 384:
    raise SystemExit(f"Dimension inattendue : {len(vector)}")
print(f"Single-query embedding dimension verified: {len(vector)}")
