-- Dikévia — stockage des embeddings multilingues gratuits (384 dimensions).
-- Ajoute une colonne distincte : ne détruit ni ne convertit les éventuels vecteurs 1536 existants.
BEGIN;

ALTER TABLE legal_chunks
    ADD COLUMN IF NOT EXISTS embedding_384 vector(384),
    ADD COLUMN IF NOT EXISTS embedding_384_model text,
    ADD COLUMN IF NOT EXISTS embedding_384_dimensions integer,
    ADD COLUMN IF NOT EXISTS embedding_384_updated_at timestamptz;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'legal_chunks_embedding_384_dimensions_check'
          AND conrelid = 'legal_chunks'::regclass
    ) THEN
        ALTER TABLE legal_chunks
            ADD CONSTRAINT legal_chunks_embedding_384_dimensions_check
            CHECK (
                (embedding_384 IS NULL AND embedding_384_model IS NULL AND embedding_384_dimensions IS NULL)
                OR
                (embedding_384 IS NOT NULL AND embedding_384_model IS NOT NULL
                 AND embedding_384_dimensions = vector_dims(embedding_384))
            );
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS legal_chunks_embedding_384_hnsw
    ON legal_chunks USING hnsw (embedding_384 vector_cosine_ops)
    WHERE embedding_384 IS NOT NULL;

GRANT SELECT ON legal_chunks TO cfdt_juris_app;
GRANT SELECT, UPDATE ON legal_chunks TO cfdt_juris_ingest;

COMMIT;
