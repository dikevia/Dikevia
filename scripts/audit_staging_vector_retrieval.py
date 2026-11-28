#!/usr/bin/env python3
"""Read-only vector-only retrieval benchmark against the Neon staging corpus.

The 100 FPT questions come from docs/quality/fpt_chatbot_eval_v1.json. Candidate
sources in that fixture are explicitly unvalidated; this script reports retrieval
evidence for human review and never certifies legal relevance or correctness.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import asyncpg
from fastembed import TextEmbedding
from generate_legal_embeddings import DIMENSIONS, MODEL_NAME, normalized_mean, split_for_embedding

STAGING_MARKER = "br-billowing-haze-bd5a1cns"
FIXTURE_PATH = Path(__file__).resolve().parents[1] / "docs" / "quality" / "fpt_chatbot_eval_v1.json"


def load_evaluation_cases(limit: int = 100) -> list[dict]:
    """Load bounded, uniquely identified questions from the reviewed eval fixture."""
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    cases = payload.get("cases")
    if payload.get("case_count") != 100 or not isinstance(cases, list) or len(cases) != 100:
        raise RuntimeError("The FPT evaluation fixture must contain exactly 100 cases.")
    ids = [case.get("id") for case in cases if isinstance(case, dict)]
    if len(ids) != 100 or len(set(ids)) != 100:
        raise RuntimeError("The FPT evaluation fixture contains missing or duplicate case IDs.")
    selected = cases[:limit]
    for case in selected:
        if not isinstance(case.get("question"), str) or not case["question"].strip():
            raise RuntimeError(f"Empty question in evaluation case {case.get('id')}.")
    return selected


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


async def main(limit: int = 100, top_k: int = 5) -> int:
    database_url = os.environ.get("LEGAL_CORPUS_INGEST_DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("LEGAL_CORPUS_INGEST_DATABASE_URL is required.")
    if urlparse(database_url).username != "cfdt_juris_ingest":
        raise RuntimeError("This read-only benchmark requires the dedicated staging ingestion role.")

    cases = load_evaluation_cases(limit)
    conn = await asyncpg.connect(database_url, command_timeout=300)
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
            for case in cases:
                question = case["question"]
                vector = _query_vector(model, question)
                vector_literal = "[" + ",".join(f"{value:.8f}" for value in vector) + "]"
                rows = await conn.fetch(
                    """
                    SELECT d.source_type, d.source_id, d.title, left(c.content, 700) AS excerpt,
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
                    LIMIT $5
                    """,
                    vector_literal, MODEL_NAME, DIMENSIONS, date.today(), top_k,
                )
                if len(rows) < top_k:
                    raise RuntimeError(
                        f"Vector-only retrieval returned {len(rows)} rows for case {case['id']}."
                    )
                hits = []
                for row in rows:
                    distance = float(row["cosine_distance"])
                    if not math.isfinite(distance) or not 0.0 <= distance <= 2.0:
                        raise RuntimeError("Invalid cosine distance in staging vector results.")
                    if (
                        row["embedding_384_model"] != MODEL_NAME
                        or row["embedding_384_dimensions"] != DIMENSIONS
                        or not row["source_type"] or not row["title"]
                    ):
                        raise RuntimeError("Incomplete or incompatible vector retrieval result.")
                    hits.append({
                        "source_type": row["source_type"],
                        "source_id": row["source_id"],
                        "title": str(row["title"])[:200],
                        "cosine_similarity": round(1.0 - distance, 6),
                        "excerpt": " ".join(str(row["excerpt"] or "").split())[:700],
                    })
                candidates = [
                    {
                        "title": str(source.get("title") or "")[:250],
                        "url": str(source.get("url") or "")[:500],
                        "verification_status": source.get("verification_status"),
                    }
                    for source in case.get("candidate_sources", [])
                    if isinstance(source, dict)
                ]
                results.append({
                    "case_id": case["id"],
                    "category": case.get("category"),
                    "question": question,
                    "expected_intent": case.get("expected_intent"),
                    "candidate_sources_for_human_review_only": candidates,
                    "top_hits": hits,
                })

        print(json.dumps({
            "status": "PASS",
            "method": "vector_only",
            "model": MODEL_NAME,
            "dimensions": DIMENSIONS,
            "evaluation_fixture": str(FIXTURE_PATH.name),
            "queries": len(results),
            "results_per_query": top_k,
            "database_writes": 0,
            "database_transaction": "READ ONLY",
            "candidate_sources_are_human_validated": False,
            "semantic_relevance_certified": False,
            "scope_note": (
                "This benchmark measures vector retrieval structure and exposes top hits. "
                "It does not certify source relevance, FPT applicability, legal accuracy, "
                "hybrid retrieval, reranker quality, or final answer quality."
            ),
            "results": results,
        }, ensure_ascii=False, sort_keys=True))
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=100, help="Number of evaluation questions (1-100).")
    parser.add_argument("--top-k", type=int, default=5, help="Number of vector hits per question (1-20).")
    args = parser.parse_args()
    if not 1 <= args.limit <= 100:
        parser.error("--limit must be between 1 and 100.")
    if not 1 <= args.top_k <= 20:
        parser.error("--top-k must be between 1 and 20.")
    raise SystemExit(asyncio.run(main(args.limit, args.top_k)))
