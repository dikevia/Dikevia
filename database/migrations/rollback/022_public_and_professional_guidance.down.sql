-- Refuse rollback if any guidance records use the new enum-like values.
-- Export or deliberately remove those records before applying this rollback.
BEGIN;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM legal_documents
        WHERE source_type IN ('SERVICE_PUBLIC_PART','INSTITUTIONAL_GUIDANCE')
           OR document_kind IN ('ADMIN_GUIDANCE','PROFESSIONAL_GUIDANCE')
    ) THEN
        RAISE EXCEPTION 'Cannot rollback corpus guidance constraints while guidance records exist';
    END IF;
END $$;

ALTER TABLE legal_documents
    DROP CONSTRAINT IF EXISTS legal_documents_source_type_check;
ALTER TABLE legal_documents
    ADD CONSTRAINT legal_documents_source_type_check
    CHECK (source_type IN (
        'LEGIFRANCE_LEGI','LEGIFRANCE_LODA','LEGIFRANCE_CETAT',
        'DILA_CIRCULAIRES','LEGIFRANCE_JORF','OTHER_OFFICIAL','CGFP_SNAPSHOT'
    ));

ALTER TABLE legal_documents
    DROP CONSTRAINT IF EXISTS legal_documents_document_kind_check;
ALTER TABLE legal_documents
    ADD CONSTRAINT legal_documents_document_kind_check
    CHECK (document_kind IN (
        'CODE','LAW','ORDONNANCE','DECREE','ORDER','CIRCULAR',
        'ADMIN_CASELAW','JOURNAL_OFFICIEL','OTHER'
    ));

COMMIT;
