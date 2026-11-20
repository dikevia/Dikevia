-- V3.30 — Identifier explicitement les snapshots CGFP non vérifiés.
-- Cette source documentaire ne doit pas être confondue avec un texte Légifrance
-- récupéré et vérifié. Son statut et ses dates d'effet restent UNKNOWN.
BEGIN;
ALTER TABLE legal_documents DROP CONSTRAINT IF EXISTS legal_documents_source_type_check;
ALTER TABLE legal_documents ADD CONSTRAINT legal_documents_source_type_check
  CHECK (source_type IN (
    'LEGIFRANCE_LEGI','LEGIFRANCE_LODA','LEGIFRANCE_CETAT',
    'DILA_CIRCULAIRES','LEGIFRANCE_JORF','OTHER_OFFICIAL','CGFP_SNAPSHOT'
  ));
COMMIT;
