-- V3.41 — Stockage vectoriel pour la recherche sémantique hybride du corpus juridique.
-- Dimension initiale 1536 : compatible avec les modèles d'embeddings OpenAI
-- text-embedding-3-small. Le modèle reste configurable côté application.
-- Les embeddings restent facultatifs tant qu'un fournisseur n'est pas configuré.
-- Le texte intégral et l'index lexical existant restent la voie de secours.
BEGIN;

CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE legal_chunks
    ADD COLUMN IF NOT EXISTS embedding vector(1536),
    ADD COLUMN IF NOT EXISTS embedding_model text,
    ADD COLUMN IF NOT EXISTS embedding_dimensions integer,
    ADD COLUMN IF NOT EXISTS embedding_updated_at timestamptz;

CREATE INDEX IF NOT EXISTS legal_chunks_embedding_hnsw
    ON legal_chunks USING hnsw (embedding vector_cosine_ops)
    WHERE embedding IS NOT NULL;

ALTER TABLE legal_chunks
    ADD CONSTRAINT legal_chunks_embedding_dimensions_check
    CHECK (
        (embedding IS NULL AND embedding_model IS NULL AND embedding_dimensions IS NULL)
        OR
        (embedding IS NOT NULL AND embedding_model IS NOT NULL
         AND embedding_dimensions = vector_dims(embedding))
    );

GRANT SELECT ON legal_chunks TO cfdt_juris_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON legal_chunks TO cfdt_juris_ingest;

COMMIT;
