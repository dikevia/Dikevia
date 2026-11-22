-- À exécuter uniquement après suppression/migration des lignes CGFP_SNAPSHOT.
BEGIN;
ALTER TABLE legal_documents DROP CONSTRAINT IF EXISTS legal_documents_source_type_check;
ALTER TABLE legal_documents ADD CONSTRAINT legal_documents_source_type_check
  CHECK (source_type IN (
    'LEGIFRANCE_LEGI','LEGIFRANCE_LODA','LEGIFRANCE_CETAT',
    'DILA_CIRCULAIRES','LEGIFRANCE_JORF','OTHER_OFFICIAL'
  ));
COMMIT;
