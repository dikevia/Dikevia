-- Rollback V3.41 : retire les données vectorielles Dikévia.
-- L'extension vector est volontairement conservée pour ne pas supprimer une
-- extension potentiellement utilisée par un autre objet de la base.
BEGIN;

DROP INDEX IF EXISTS legal_chunks_embedding_hnsw;
ALTER TABLE legal_chunks
    DROP CONSTRAINT IF EXISTS legal_chunks_embedding_dimensions_check;
ALTER TABLE legal_chunks
    DROP COLUMN IF EXISTS embedding_updated_at,
    DROP COLUMN IF EXISTS embedding_dimensions,
    DROP COLUMN IF EXISTS embedding_model,
    DROP COLUMN IF EXISTS embedding;

COMMIT;
