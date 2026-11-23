-- V3.40: allow non-normative public and professional guidance in the national corpus.
-- These source types are contextual documentation only; they are not legal authorities.
BEGIN;

ALTER TABLE legal_documents
    DROP CONSTRAINT IF EXISTS legal_documents_source_type_check;
ALTER TABLE legal_documents
    ADD CONSTRAINT legal_documents_source_type_check
    CHECK (source_type IN (
        'LEGIFRANCE_LEGI','LEGIFRANCE_LODA','LEGIFRANCE_CETAT',
        'DILA_CIRCULAIRES','LEGIFRANCE_JORF','OTHER_OFFICIAL','CGFP_SNAPSHOT',
        'SERVICE_PUBLIC_PART','INSTITUTIONAL_GUIDANCE'
    ));

ALTER TABLE legal_documents
    DROP CONSTRAINT IF EXISTS legal_documents_document_kind_check;
ALTER TABLE legal_documents
    ADD CONSTRAINT legal_documents_document_kind_check
    CHECK (document_kind IN (
        'CODE','LAW','ORDONNANCE','DECREE','ORDER','CIRCULAR',
        'ADMIN_CASELAW','JOURNAL_OFFICIEL','OTHER',
        'ADMIN_GUIDANCE','PROFESSIONAL_GUIDANCE'
    ));

COMMIT;
