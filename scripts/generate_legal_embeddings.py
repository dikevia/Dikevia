#!/usr/bin/env python3
"""Generate local multilingual embeddings for legal_chunks on a dedicated staging DB.

No external embedding API is called. The model is downloaded from its public model
repository on first use; document/query text is processed locally by FastEmbed.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
import unicodedata

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DIMENSIONS = 384
SEGMENT_CHARS = 500
SEGMENT_OVERLAP = 60


def split_for_embedding(text: str) -> list[str]:
    text = unicodedata.normalize("NFC", str(text or "")).strip()
    if not text:
        return []
    segments: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + SEGMENT_CHARS)
        if end < len(text):
            boundary = max(text.rfind("\n", start + SEGMENT_CHARS // 2, end),
                           text.rfind(". ", start + SEGMENT_CHARS // 2, end))
            if boundary > start:
                end = boundary + 1
        piece = re.sub(r"\s+", " ", text[start:end]).strip()
        if piece:
            segments.append(piece)
        if end >= len(text):
            break
        start = max(start + 1, end - SEGMENT_OVERLAP)
    return segments


def normalized_mean(vectors) -> list[float]:
    import math

    vectors = list(vectors)
    if not vectors:
        raise ValueError("Aucun segment vectorisé.")
    dimensions = len(vectors[0])
    if dimensions < 1 or any(len(vector) != dimensions for vector in vectors):
        raise ValueError("Dimensions incohérentes entre les segments.")
    values = [
        sum(float(vector[index]) for vector in vectors) / len(vectors)
        for index in range(dimensions)
    ]
    norm = math.sqrt(sum(value * value for value in values))
    if not norm:
        raise ValueError("Le modèle a produit un vecteur nul.")
    return [value / norm for value in values]

async def run(args: argparse.Namespace) -> int:
    database_url = os.environ.get("LEGAL_CORPUS_INGEST_DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("LEGAL_CORPUS_INGEST_DATABASE_URL absent.")
    from urllib.parse import urlparse
    if urlparse(database_url).username != "cfdt_juris_ingest":
        raise RuntimeError("Le script exige le rôle dédié cfdt_juris_ingest.")

    try:
        import asyncpg
        from fastembed import TextEmbedding
    except ImportError as exc:
        raise RuntimeError(
            "Dépendances absentes. Installer backend/requirements-embeddings.txt."
        ) from exc

    conn = await asyncpg.connect(database_url, command_timeout=120)
    try:
        identity = await conn.fetchval("SELECT current_user")
        if identity != "cfdt_juris_ingest":
            raise RuntimeError("Connexion PostgreSQL non autorisée pour l'ingestion vectorielle.")
        total = await conn.fetchval(
            "SELECT count(*) FROM legal_chunks WHERE embedding_384 IS NULL"
        )
        print(f"Fragments sans vecteur : {total}")
        if args.dry_run:
            print("Dry-run : aucune écriture effectuée.")
            return 0
        if total == 0:
            print("Tous les fragments possèdent déjà un embedding.")
            return 0

        model = TextEmbedding(model_name=MODEL_NAME)
        processed = 0
        while processed < args.max_chunks:
            rows = await conn.fetch(
                """SELECT id, content
                   FROM legal_chunks
                   WHERE embedding_384 IS NULL
                   ORDER BY created_at, id
                   LIMIT $1""",
                min(args.batch_size, args.max_chunks - processed),
            )
            if not rows:
                break

            all_segments: list[str] = []
            segment_counts: list[int] = []
            for row in rows:
                segments = split_for_embedding(row["content"])
                segment_counts.append(len(segments))
                all_segments.extend(segments)

            generated = list(model.embed(all_segments)) if all_segments else []
            vectors = []
            offset = 0
            for row, count in zip(rows, segment_counts):
                if count < 1:
                    raise RuntimeError("Fragment vide ou non exploitable : " + str(row["id"]))
                combined = normalized_mean(generated[offset:offset + count])
                offset += count
                if len(combined) != DIMENSIONS:
                    raise RuntimeError(
                        f"Dimension inattendue : {len(combined)} au lieu de {DIMENSIONS}."
                    )
                vector_literal = "[" + ",".join(f"{value:.8f}" for value in combined) + "]"
                vectors.append((row["id"], vector_literal))

            updates = [
                (chunk_id, vector)
                for chunk_id, vector in vectors
                if vector is not None
            ]
            if updates:
                await conn.executemany(
                    """UPDATE legal_chunks
                       SET embedding_384 = $2::vector,
                           embedding_384_model = $3,
                           embedding_384_dimensions = $4,
                           embedding_384_updated_at = now()
                       WHERE id = $1 AND embedding_384 IS NULL""",
                    [(chunk_id, vector, MODEL_NAME, DIMENSIONS) for chunk_id, vector in updates],
                )
            processed += len(rows)
            print(f"Traités : {processed}/{min(total, args.max_chunks)}")
        remaining = await conn.fetchval(
            "SELECT count(*) FROM legal_chunks WHERE embedding_384 IS NULL"
        )
        embedded = await conn.fetchval(
            "SELECT count(*) FROM legal_chunks WHERE embedding_384 IS NOT NULL"
        )
        print(f"Vecteurs présents : {embedded}; restants : {remaining}")
        return 0 if remaining == 0 or processed >= args.max_chunks else 1
    finally:
        await conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--max-chunks", type=int, default=100000)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 64:
        parser.error("--batch-size doit être compris entre 1 et 64.")
    if not 1 <= args.max_chunks <= 1000000:
        parser.error("--max-chunks doit être compris entre 1 et 1000000.")
    try:
        return asyncio.run(run(args))
    except Exception as exc:
        print(f"ERREUR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
