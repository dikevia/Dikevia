#!/usr/bin/env python3
"""Read-only vector-only retrieval smoke test against the Neon staging corpus."""
from __future__ import annotations

import asyncio
import json
import math
import os
from datetime import date
from urllib.parse import urlparse

import asyncpg
from fastembed import TextEmbedding
from generate_legal_embeddings import DIMENSIONS, MODEL_NAME, normalized_mean, split_for_embedding

STAGING_MARKER = "br-billowing-haze-bd5a1cns"
QUERIES = (
    "Quelles sont les règles de report des congés annuels d'un agent territorial ?",
    "Quelles conditions permettent à un fonctionnaire territorial de bénéficier du temps partiel thérapeutique ?",
    "Comment est déterminée l'indemnisation des heures supplémentaires des agents territoriaux ?",
    "Quelles règles encadrent le temps de travail annualisé dans la fonction publique territoriale ?",
)


def _query_vector(model: TextEmbedding, question: str) -> list[float]:
    segments = split_for_embedding(question)
    if not segments:
        raise ValueError("Question vide après segmentation.")
    vector = normalized_mean(model.embed(segments))
    if len(vector) != DIMENSIONS:
        raise ValueError(f"Dimension inattendue : {len(vector)}")
    norm = math.sqrt(sum(value * value for value in vector))
    if not math.isfinite(norm) or abs(norm - 1.0) > 1e-5:
        raise ValueError("Le vecteur de requête n'est pas normalisé.")
    return vector


async def main() -> int:
    database_url = os.environ.get("LEGAL_CORPUS_INGEST_DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("LEGAL_CORPUS_INGEST_DATABASE_URL is required.")
    if urlparse(database_url).username != "cfdt_juris_ingest":
        raise RuntimeError("This read-only smoke test requires the dedicated staging ingestion role.")

    conn = await asyncpg.connect(database_url, command_timeout=120)
    try:
        async with conn.transaction(readonly=True):
            identity = await conn.fetchval("SELECT current_user")
            marker = await conn.fetchval(
                "SELECT marker FROM public.dikevia_staging_guard WHERE marker=$1",
                STAGING_MARKER,
            )
            if identity != "cfdt_juris_ingest" or marker != STAGING_MARKER:
                raise RuntimeError("Database identity or staging marker mismatch.")

            model = TextEmbedding(model_name=MODEL_NAME)
            results = []
            for question in QUERIES:
                vector = _query_vector(model, question)
                vector_literal = "[" + ",".join(f"{value:.8f}" for value in vector) + "]"
                rows = await conn.fetch(
                    """
                    SELECT d.source_type, d.source_id, d.title,
                           c.embedding_384_model, c.embedding_384_dimensions,
                           c.embedding_384 <=> $1::vector AS cosine_distance
                    FROM legal_chunks c
                    JOIN legal_document_versions v ON v.id = c.version_id
                    JOIN legal_documents d ON d.id = v.document_id
                    WHERE c.embedding_384 IS NOT NULL
                      AND c.embedding_384_model = $2
                      AND c.embedding_384_dimensions = $3
                      AND c.content_kind = 'FULL_TEXT'
                      AND (v.valid_from IS NULL OR v.valid_from <= $4::date)
                      AND (v.valid_to IS NULL OR v.valid_to >= $4::date)
                    ORDER BY c.embedding_384 <=> $1::vector
                    LIMIT 5
                    """,
                    vector_literal,
                    MODEL_NAME,
                    DIMENSIONS,
                    date.today(),
                )
                if len(rows) < 5:
                    raise RuntimeError(
                        f"Vector-only retrieval returned {len(rows)} rows for query: {question}"
                    )
                hits = []
                for row in rows:
                    distance = float(row["cosine_distance"])
                    if not math.isfinite(distance) or not 0.0 <= distance <= 2.0:
                        raise RuntimeError("Invalid cosine distance in staging vector results.")
                    if (
                        row["embedding_384_model"] != MODEL_NAME
                        or row["embedding_384_dimensions"] != DIMENSIONS
                        or not row["source_type"]
                        or not row["title"]
                    ):
                        raise RuntimeError("Incomplete or incompatible vector retrieval result.")
                    hits.append({
                        "source_type": row["source_type"],
                        "source_id": row["source_id"],
                        "title": str(row["title"])[:120],
                        "cosine_similarity": round(1.0 - distance, 6),
                    })
                results.append({"query": question, "top_hits": hits})

        print(json.dumps({
            "status": "PASS",
            "method": "vector_only",
            "model": MODEL_NAME,
            "dimensions": DIMENSIONS,
            "queries": len(results),
            "results_per_query": 5,
            "database_writes": 0,
            "semantic_relevance_certified": False,
            "results": results,
        }, ensure_ascii=False, sort_keys=True))
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
