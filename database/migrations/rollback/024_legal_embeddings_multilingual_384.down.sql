-- Rollback V3.42 : retire uniquement les embeddings multilingues 384 dimensions.
-- Les vecteurs 1536 dimensions de la migration 023 sont conservés.
-- La colonne embedding_384 et ses métadonnées sont supprimées : toute donnée
-- vectorielle 384 dimensions présente est donc perdue lors de ce rollback.
-- L'extension vector est volontairement conservée, car la migration 023 l'utilise.
BEGIN;

DROP INDEX IF EXISTS legal_chunks_embedding_384_hnsw;
ALTER TABLE legal_chunks
    DROP CONSTRAINT IF EXISTS legal_chunks_embedding_384_dimensions_check;
ALTER TABLE legal_chunks
    DROP COLUMN IF EXISTS embedding_384_updated_at,
    DROP COLUMN IF EXISTS embedding_384_dimensions,
    DROP COLUMN IF EXISTS embedding_384_model,
    DROP COLUMN IF EXISTS embedding_384;

COMMIT;
